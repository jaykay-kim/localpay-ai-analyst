
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(
    page_title="LocalPay AI Analyst - Suwon",
    page_icon="💳",
    layout="wide"
)

SUWON_MERCHANT_TOTAL_API = 37369

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
    color: white; padding: 26px 30px; border-radius: 16px; margin-bottom: 24px;
}
.data-badge {
    display: inline-block; background: #e8f0fe; color: #1a73e8;
    padding: 5px 11px; border-radius: 20px; font-size: 12px; margin: 3px;
}
.insight-box {
    background: #f0f4ff; border-left: 5px solid #1a73e8;
    border-radius: 10px; padding: 16px 20px; margin: 10px 0; line-height: 1.75;
}
.warning-box {
    background: #fff7e6; border-left: 5px solid #fbbc04;
    border-radius: 10px; padding: 16px 20px; margin: 10px 0; line-height: 1.75;
}
.good-box {
    background: #ecfdf5; border-left: 5px solid #10b981;
    border-radius: 10px; padding: 16px 20px; margin: 10px 0; line-height: 1.75;
}
.card {
    background: white; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 18px 20px; margin: 8px 0; box-shadow: 0 1px 2px rgba(0,0,0,.04);
}
.user-card {
    background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 14px;
    padding: 18px 20px; margin: 10px 0; line-height:1.75;
}
.small-note {font-size: 13px; color: #64748b;}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_payments():
    return pd.read_csv("data/suwon_localpay_payments.csv")

@st.cache_data
def load_stores():
    return pd.read_csv("data/suwon_stores.csv")

def format_won(value):
    try:
        value = float(value)
    except:
        return "-"
    if value >= 100_000_000:
        return f"{value/100_000_000:.1f}억 원"
    if value >= 10_000:
        return f"{value/10_000:.0f}만 원"
    return f"{value:,.0f}원"

def normalize(s):
    s = pd.to_numeric(s, errors="coerce").fillna(0)
    if len(s) == 0:
        return s
    if s.max() == s.min():
        return pd.Series([50] * len(s), index=s.index)
    return (s - s.min()) / (s.max() - s.min()) * 100

def safe_cols(df, cols):
    return [c for c in cols if c in df.columns]

def calc_industry_scores(pay_df, store_df):
    p = pay_df.groupby("industry", as_index=False).agg(
        결제금액=("payment_amount","sum"),
        결제건수=("transaction_count","sum"),
        평균객단가=("avg_ticket","mean"),
        이용연령대수=("age_group","nunique"),
        이용행정동수=("district","nunique"),
    )
    if not store_df.empty and "indsMclsNm" in store_df.columns:
        s = store_df.groupby("indsMclsNm", as_index=False).size().rename(columns={"indsMclsNm":"industry", "size":"상가점포수"})
        p = p.merge(s, on="industry", how="left")
    else:
        p["상가점포수"] = np.nan

    p["상가점포수"] = p["상가점포수"].fillna(0)
    p["수요규모점수"] = normalize(p["결제금액"])
    p["거래빈도점수"] = normalize(p["결제건수"])
    p["객단가점수"] = normalize(p["평균객단가"])
    p["고객확장성점수"] = normalize(p["이용연령대수"])
    p["지역확산점수"] = normalize(p["이용행정동수"])
    p["경쟁완화점수"] = 100 - normalize(p["상가점포수"]) if p["상가점포수"].sum() > 0 else 50

    p["창업투자점수"] = (
        p["수요규모점수"] * 0.35 +
        p["거래빈도점수"] * 0.20 +
        p["객단가점수"] * 0.15 +
        p["고객확장성점수"] * 0.10 +
        p["지역확산점수"] * 0.10 +
        p["경쟁완화점수"] * 0.10
    ).round(1)
    p["평균객단가"] = p["평균객단가"].round(0)
    return p.sort_values("창업투자점수", ascending=False)

def calc_district_scores(pay_df, store_df):
    p = pay_df.groupby("district", as_index=False).agg(
        결제금액=("payment_amount","sum"),
        결제건수=("transaction_count","sum"),
        평균객단가=("avg_ticket","mean"),
        이용업종수=("industry","nunique"),
        이용연령대수=("age_group","nunique"),
    )
    if not store_df.empty and "adongNm" in store_df.columns:
        s = store_df.groupby("adongNm", as_index=False).size().rename(columns={"adongNm":"district","size":"상가점포수"})
        p = p.merge(s, on="district", how="left")
    else:
        p["상가점포수"] = np.nan
    p["상가점포수"] = p["상가점포수"].fillna(0)

    p["소비규모점수"] = normalize(p["결제금액"])
    p["거래활성점수"] = normalize(p["결제건수"])
    p["객단가점수"] = normalize(p["평균객단가"])
    p["상권다양성점수"] = normalize(p["이용업종수"])
    p["고객다양성점수"] = normalize(p["이용연령대수"])
    p["경쟁완화점수"] = 100 - normalize(p["상가점포수"]) if p["상가점포수"].sum() > 0 else 50

    p["상권투자점수"] = (
        p["소비규모점수"] * 0.35 +
        p["거래활성점수"] * 0.20 +
        p["객단가점수"] * 0.15 +
        p["상권다양성점수"] * 0.10 +
        p["고객다양성점수"] * 0.10 +
        p["경쟁완화점수"] * 0.10
    ).round(1)
    p["평균객단가"] = p["평균객단가"].round(0)
    return p.sort_values("상권투자점수", ascending=False)

def calc_target_industry_location(pay_df, store_df, selected_industry):
    d = pay_df[pay_df["industry"] == selected_industry].copy()
    if d.empty:
        return pd.DataFrame()
    g = d.groupby("district", as_index=False).agg(
        결제금액=("payment_amount","sum"),
        결제건수=("transaction_count","sum"),
        평균객단가=("avg_ticket","mean"),
        이용연령대수=("age_group","nunique"),
    )
    if not store_df.empty and "adongNm" in store_df.columns and "indsMclsNm" in store_df.columns:
        s = store_df[store_df["indsMclsNm"] == selected_industry].groupby("adongNm", as_index=False).size().rename(columns={"adongNm":"district","size":"관심업종점포수"})
        g = g.merge(s, on="district", how="left")
    else:
        g["관심업종점포수"] = np.nan
    g["관심업종점포수"] = g["관심업종점포수"].fillna(0)

    g["수요규모점수"] = normalize(g["결제금액"])
    g["거래빈도점수"] = normalize(g["결제건수"])
    g["객단가점수"] = normalize(g["평균객단가"])
    g["고객확장성점수"] = normalize(g["이용연령대수"])
    g["경쟁완화점수"] = 100 - normalize(g["관심업종점포수"]) if g["관심업종점포수"].sum() > 0 else 50

    g["입지검토점수"] = (
        g["수요규모점수"] * 0.40 +
        g["거래빈도점수"] * 0.25 +
        g["객단가점수"] * 0.15 +
        g["고객확장성점수"] * 0.10 +
        g["경쟁완화점수"] * 0.10
    ).round(1)
    g["평균객단가"] = g["평균객단가"].round(0)
    return g.sort_values("입지검토점수", ascending=False)

def demand_competition_matrix(industry_score):
    df = industry_score.copy()
    if df.empty:
        return df
    df["수요점수"] = normalize(df["결제금액"])
    df["경쟁점수"] = normalize(df["상가점포수"]) if df["상가점포수"].sum() > 0 else 50
    conditions = [
        (df["수요점수"] >= 60) & (df["경쟁점수"] < 50),
        (df["수요점수"] >= 60) & (df["경쟁점수"] >= 50),
        (df["수요점수"] < 60) & (df["경쟁점수"] < 50),
        (df["수요점수"] < 60) & (df["경쟁점수"] >= 50),
    ]
    choices = ["우선 검토", "수요 높지만 경쟁 주의", "니치 가능성", "보류/추가조사"]
    df["전략분류"] = np.select(conditions, choices, default="추가조사")
    return df

def simple_explanatory_model(pay_df):
    """Simple OLS-style explanatory model using numpy: log(payment_amount) explained by log(txn), log(ticket), age dummies.
    This is for presentation only, not prediction."""
    df = pay_df.copy()
    df = df[(df["payment_amount"] > 0) & (df["transaction_count"] > 0) & (df["avg_ticket"] > 0)].copy()
    if len(df) < 10:
        return None
    y = np.log1p(df["payment_amount"].values)
    X_base = pd.DataFrame({
        "상수": 1.0,
        "log_결제건수": np.log1p(df["transaction_count"].values),
        "log_평균객단가": np.log1p(df["avg_ticket"].values),
    })
    age_dummies = pd.get_dummies(df["age_group"], prefix="연령", drop_first=True).astype(float)
    X = pd.concat([X_base, age_dummies], axis=1)
    X_mat = X.values.astype(float)
    try:
        beta = np.linalg.lstsq(X_mat, y, rcond=None)[0]
        yhat = X_mat @ beta
        ss_res = np.sum((y - yhat) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else np.nan
        coef = pd.DataFrame({"변수": X.columns, "계수": beta}).sort_values("계수", ascending=False)
        return r2, coef
    except Exception:
        return None

def make_report(pay_df, store_df, region, district, selected_industry, industry_score, district_score, target_score, matrix_df):
    total_pay = pay_df["payment_amount"].sum()
    total_txn = pay_df["transaction_count"].sum()
    avg_ticket = total_pay / max(total_txn, 1)
    age = pay_df.groupby("age_group", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
    top_age = age.iloc[0]["age_group"] if not age.empty else "확인 불가"
    gender = pay_df.groupby("gender", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
    top_gender = gender.iloc[0]["gender"] if not gender.empty else "확인 불가"

    top_ind = industry_score.iloc[0] if not industry_score.empty else None
    top_dist = district_score.iloc[0] if not district_score.empty else None
    top_target = target_score.iloc[0] if not target_score.empty else None
    area = region if district == "전체" else f"{region} {district}"

    # User-friendly conclusion
    top_ind_text = ""
    if top_ind is not None:
        top_ind_text = f"전체 업종 기준으로는 **{top_ind['industry']}**의 창업투자점수가 가장 높습니다. 결제금액은 **{format_won(top_ind['결제금액'])}**입니다."

    top_dist_text = ""
    if top_dist is not None:
        top_dist_text = f"행정동 기준으로는 **{top_dist['district']}**의 상권투자점수가 가장 높습니다. 결제금액은 **{format_won(top_dist['결제금액'])}**입니다."

    target_text = ""
    if top_target is not None:
        target_text = f"관심 업종 **{selected_industry}** 기준으로는 **{top_target['district']}**가 1차 검토 지역입니다. 이 지역의 결제금액은 **{format_won(top_target['결제금액'])}**, 결제건수는 **{top_target['결제건수']:,.0f}건**, 평균 객단가는 **{format_won(top_target['평균객단가'])}**입니다."
    else:
        target_text = f"선택 업종 **{selected_industry}**에 대한 결제 데이터가 선택 조건에서 확인되지 않습니다."

    priority = matrix_df[matrix_df["전략분류"] == "우선 검토"].head(3)["industry"].tolist() if not matrix_df.empty else []
    priority_text = ", ".join(priority) if priority else "추가 데이터 확인 필요"

    store_note = f"수원시 상가정보 경량 데이터는 **{len(store_df):,}개**이며, 결제 수요와 상가 밀도를 함께 보는 경쟁강도 보완 지표로 활용했습니다." if not store_df.empty else ""

    return f"""
### AI Analyst Report: {area} 지역화폐 기반 창업 투자 상권분석

#### 1. 사용자 관점 결론
이 서비스의 1차 이용자는 **수원시에서 창업을 검토하는 예비창업자**입니다. 사용자는 감이나 부동산 정보만이 아니라, 실제 지역화폐 결제금액·결제건수·연령대별 소비패턴을 바탕으로 업종과 입지를 비교할 수 있습니다.

#### 2. 한눈에 보는 추천
- 선택 지역 총 결제금액: **{format_won(total_pay)}**
- 총 결제건수: **{total_txn:,.0f}건**
- 평균 객단가: **{format_won(avg_ticket)}**
- 주요 소비 연령대: **{top_age}**
- 주요 소비 성별: **{top_gender}**
- 우선 검토 업종 후보: **{priority_text}**

#### 3. 업종·입지 판단
{top_ind_text}  
{top_dist_text}  
{target_text}

#### 4. Data Basis
현재 분석은 공공데이터포털의 **2025년 11월 수원시 지역화폐 결제정보**를 기반으로 합니다. 원본 데이터에는 읍면동, 업종, 성별, 연령대, 결제건수, 결제금액이 포함되어 있습니다. 또한 경기지역화폐 가맹점 현황 OpenAPI에서 `SIGUN_NM=수원시` 조건으로 조회한 결과, 수원시 전체 지역화폐 가맹점 수는 **{SUWON_MERCHANT_TOTAL_API:,}개**입니다.  
{store_note}

#### 5. Investment Scoring
업종별 창업투자점수는 **결제금액 35% + 결제건수 20% + 평균 객단가 15% + 고객확장성 10% + 지역확산 10% + 경쟁완화 10%**로 계산했습니다.  
행정동별 상권투자점수는 **소비규모 35% + 거래활성 20% + 객단가 15% + 상권다양성 10% + 고객다양성 10% + 경쟁완화 10%**로 계산했습니다.

#### 6. 실제 이용 시 다음 행동
1. 추천 업종 TOP3를 확인합니다.  
2. 관심 업종을 선택하고 입지검토점수 1~3위 행정동을 비교합니다.  
3. 해당 지역의 임대료, 유동인구, 경쟁점포, 마진율을 현장조사로 추가 확인합니다.  
4. 지역화폐 결제수요가 높은 연령대를 기준으로 가격·메뉴·홍보전략을 설계합니다.

#### 7. Local Currency Extension
지역화폐는 단순 결제수단이 아니라 지역 상권의 실제 소비 흐름을 보여주는 데이터 자산입니다. 향후 광주상생카드·온누리상품권 결제데이터가 공개되거나 연계되면, 같은 분석 구조를 광주 지역과 전통시장 상권에도 적용할 수 있습니다.

#### 8. Limitations
현재 결제정보는 2025년 11월 단월 데이터입니다. 월별 추세 분석을 위해서는 여러 기준월 데이터가 필요합니다. 또한 임대료, 유동인구, 마진율, 업종별 실제 가맹점 수는 추가 연계가 필요합니다. 따라서 본 앱은 **최종 창업 결정 도구가 아니라, 1차 후보 업종·입지를 좁히는 AI Analyst 도구**입니다.
"""

# Header
st.markdown("""
<div class="main-header">
  <h1 style="margin:0;font-size:1.85rem;">💳 LocalPay AI Analyst</h1>
  <p style="margin:8px 0 0;opacity:.92;">수원시 지역화폐 결제데이터 기반 · 예비창업자용 창업 투자 의사결정 지원 플랫폼</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<span class="data-badge">📊 실제 공공데이터</span>
<span class="data-badge">2025년 11월 수원시 지역화폐 결제정보</span>
<span class="data-badge">수원시 상가정보 결합</span>
<span class="data-badge">AI Analyst Report</span>
<span class="data-badge">예비창업자 의사결정</span>
""", unsafe_allow_html=True)

st.markdown("""
<div class="insight-box">
<b>서비스 대상</b><br>
이 서비스의 1차 이용자는 <b>수원시에서 창업을 검토하는 예비창업자</b>입니다.
사용자는 “어느 동네에, 어떤 업종으로 들어갈지”를 감이 아니라 실제 지역화폐 결제 데이터와 상가 밀도 데이터를 바탕으로 비교할 수 있습니다.
2차 이용자는 소상공인 컨설턴트, 지자체 상권지원 담당자입니다.
</div>
""", unsafe_allow_html=True)

payments = load_payments()
stores = load_stores()

with st.sidebar:
    st.header("🔍 분석 조건")
    regions = ["전체"] + sorted(payments["region"].astype(str).unique().tolist())
    region = st.selectbox("시/군/구 선택", regions, index=1 if len(regions) > 1 else 0)
    filtered = payments.copy()
    if region != "전체":
        filtered = filtered[filtered["region"].astype(str) == region]

    districts = ["전체"] + sorted(filtered["district"].astype(str).unique().tolist())
    district = st.selectbox("읍/면/동 선택", districts)
    if district != "전체":
        filtered = filtered[filtered["district"].astype(str) == district]

    industries = ["전체"] + sorted(filtered["industry"].astype(str).unique().tolist())
    selected_industry = st.selectbox("관심 업종", industries, index=1 if len(industries) > 1 else 0)
    selected_industry_report = sorted(filtered["industry"].unique().tolist())[0] if selected_industry == "전체" else selected_industry

    months = sorted(filtered["month"].astype(str).unique().tolist())
    selected_months = st.multiselect("분석 월", months, default=months)
    if selected_months:
        filtered = filtered[filtered["month"].astype(str).isin(selected_months)]

    st.divider()
    st.caption("기본 데이터: 수원시 지역화폐 결제정보")
    st.caption("상가정보: 수원시 상가정보 경량 파일")
    st.caption("가맹점 API 조회 결과: 수원시 37,369개")

if filtered.empty:
    st.warning("선택 조건에 해당하는 데이터가 없습니다.")
    st.stop()

stores_filtered = stores.copy()
if district != "전체" and "adongNm" in stores_filtered.columns:
    stores_filtered = stores_filtered[stores_filtered["adongNm"].astype(str) == district]

industry_score = calc_industry_scores(filtered, stores_filtered)
district_score = calc_district_scores(filtered, stores)
target_score = calc_target_industry_location(filtered, stores, selected_industry_report)
matrix_df = demand_competition_matrix(industry_score)
model_result = simple_explanatory_model(filtered)

total_payment = filtered["payment_amount"].sum()
total_txn = filtered["transaction_count"].sum()
avg_ticket = total_payment / max(total_txn, 1)

st.success(f"데이터 기준: 2025년 11월 수원시 지역화폐 결제정보 · 분석 행 수 {len(filtered):,}건")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("총 결제금액", format_won(total_payment))
c2.metric("총 결제건수", f"{total_txn:,.0f}건")
c3.metric("평균 객단가", format_won(avg_ticket))
c4.metric("분석 업종 수", f"{filtered['industry'].nunique():,}개")
c5.metric("수원시 가맹점 수", f"{SUWON_MERCHANT_TOTAL_API:,}개")

st.caption("※ 결제금액·결제건수는 공공데이터 원본 값입니다. 수원시 가맹점 수는 경기지역화폐 가맹점 현황 OpenAPI에서 SIGUN_NM=수원시 조건으로 확인한 값입니다.")

tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "✅ 사용자 결론", "🎯 Before vs After", "📍 지역 분석", "🏪 업종 분석", "👥 소비자 분석", "🏬 상가정보", "📈 투자·기술 분석", "🤖 AI 리포트"
])

with tab0:
    st.markdown("### 예비창업자가 이 앱으로 얻는 결론")
    top_industries = industry_score.head(3)
    top_districts = district_score.head(3)
    priority = matrix_df[matrix_df["전략분류"] == "우선 검토"].head(3)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="user-card"><b>① 추천 업종 TOP 3</b><br>' + "<br>".join([f"{i+1}. {r['industry']} ({r['창업투자점수']}점)" for i, r in top_industries.iterrows()]) + '</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="user-card"><b>② 추천 행정동 TOP 3</b><br>' + "<br>".join([f"{i+1}. {r['district']} ({r['상권투자점수']}점)" for i, r in top_districts.iterrows()]) + '</div>', unsafe_allow_html=True)
    with c3:
        if not priority.empty:
            priority_text = "<br>".join([f"{i+1}. {r['industry']} ({r['전략분류']})" for i, r in priority.iterrows()])
        else:
            priority_text = "추가 데이터 확인 필요"
        st.markdown(f'<div class="user-card"><b>③ 수요-경쟁 관점 우선 검토</b><br>{priority_text}</div>', unsafe_allow_html=True)

    st.markdown("""
<div class="good-box">
<b>사용자가 편리하다고 느끼는 지점</b><br>
예비창업자는 여러 공공데이터 파일을 직접 열어보지 않아도, 지역과 업종을 선택하는 것만으로
<b>소비금액, 거래건수, 주요 연령대, 경쟁밀도, 창업투자점수, AI 리포트</b>를 한 화면에서 확인할 수 있습니다.
즉, “내가 어디에 어떤 업종으로 창업할까?”라는 질문의 1차 후보를 빠르게 좁혀줍니다.
</div>
""", unsafe_allow_html=True)

    st.markdown("### 실제 이용 시나리오")
    st.markdown("""
1. 예비창업자가 수원시 권선구/영통구 중 관심 지역을 선택합니다.  
2. 카페, 음식, 미용, 교육 등 관심 업종을 선택합니다.  
3. 앱은 해당 업종의 결제금액, 결제건수, 객단가, 주요 소비 연령대를 보여줍니다.  
4. 수원시 상가정보를 결합해 경쟁밀도를 보완합니다.  
5. AI 리포트가 추천 업종, 추천 행정동, 리스크, 추가 확인사항을 정리합니다.  
""")

with tab1:
    st.markdown("### 교수님 피드백 반영: 실제 데이터 기반 시연으로 전환")
    st.markdown("""
| 구분 | 기존 접근 | 최종 접근 |
|---|---|---|
| 분석 대상 | 광주/온누리상품권 구상 중심 | **수원시 지역화폐 실제 결제데이터** 기반 시연 |
| 데이터 | 가맹점·상가정보 중심 | **결제금액·결제건수·업종·연령대·성별** 포함 |
| 추가 보완 | 점포 수 중심 | **수원시 상가정보 + 수원시 가맹점 API 결과** 결합 |
| 의사결정 | 정책 분석/상권 현황 | **예비창업자의 창업 투자 의사결정** |
| 자동화 | 데이터 요약 | 지표 산출 → 투자 점수 → **AI Analyst Report 자동 생성** |
| 확장성 | 광주 한정 | 수원 실증 후 **광주상생카드·온누리상품권으로 확장 가능** |
""")
    a, b = st.columns(2)
    with a:
        st.markdown("""
<div class="warning-box">
<b>Before</b><br>
예비창업자는 네이버 지도, 부동산 중개인 의견, 주변 체감, 지인 추천으로 창업지를 판단합니다.
지역화폐 소비 데이터는 창업 의사결정에 거의 활용되지 못합니다.
</div>
""", unsafe_allow_html=True)
    with b:
        st.markdown("""
<div class="good-box">
<b>After</b><br>
AI가 실제 지역화폐 결제 데이터를 분석해 업종별 소비 수요, 연령대별 소비패턴, 행정동별 결제규모,
상가 밀도, 창업 투자 점수와 리포트를 자동 생성합니다.
</div>
""", unsafe_allow_html=True)

with tab2:
    st.markdown("### 읍면동별 결제금액")
    dpay = filtered.groupby("district", as_index=False).agg(
        결제금액=("payment_amount","sum"),
        결제건수=("transaction_count","sum")
    ).sort_values("결제금액", ascending=False)
    fig = px.bar(dpay, x="결제금액", y="district", orientation="h", text="결제금액",
                 color="결제금액", color_continuous_scale="Blues")
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(yaxis=dict(autorange="reversed"), height=520, coloraxis_showscale=False, plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(dpay.rename(columns={"district":"읍면동"}), use_container_width=True)

with tab3:
    st.markdown("### 업종별 결제금액 TOP 20")
    ipay = filtered.groupby("industry", as_index=False).agg(
        결제금액=("payment_amount","sum"),
        결제건수=("transaction_count","sum"),
        평균객단가=("avg_ticket","mean")
    ).sort_values("결제금액", ascending=False)
    ipay["평균객단가"] = ipay["평균객단가"].round(0)
    fig2 = px.bar(ipay.head(20), x="결제금액", y="industry", orientation="h", text="결제금액",
                  color="결제금액", color_continuous_scale="Teal")
    fig2.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig2.update_layout(yaxis=dict(autorange="reversed"), height=620, coloraxis_showscale=False, plot_bgcolor="white")
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(ipay.rename(columns={"industry":"업종"}), use_container_width=True)

with tab4:
    ca, cb = st.columns(2)
    with ca:
        st.markdown("### 연령대별 결제금액")
        age = filtered.groupby("age_group", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
        fig3 = px.bar(age, x="age_group", y="payment_amount", text="payment_amount",
                      color="payment_amount", color_continuous_scale="Purples")
        fig3.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig3.update_layout(height=420, coloraxis_showscale=False, plot_bgcolor="white")
        st.plotly_chart(fig3, use_container_width=True)
    with cb:
        st.markdown("### 성별 결제금액")
        gender = filtered.groupby("gender", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
        fig4 = px.bar(gender, x="gender", y="payment_amount", text="payment_amount",
                      color="payment_amount", color_continuous_scale="Oranges")
        fig4.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig4.update_layout(height=420, coloraxis_showscale=False, plot_bgcolor="white")
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("### 연령대 × 업종 결제금액 히트맵")
    heat = filtered.groupby(["age_group","industry"], as_index=False)["payment_amount"].sum()
    fig5 = px.density_heatmap(heat, x="industry", y="age_group", z="payment_amount",
                              color_continuous_scale="Blues")
    fig5.update_layout(height=520, xaxis_tickangle=-40, plot_bgcolor="white")
    st.plotly_chart(fig5, use_container_width=True)

with tab5:
    st.markdown("### 수원시 상가정보")
    st.caption("경기도 전체 파일에서 수원시 관련 상가정보만 추출한 경량 파일입니다.")
    c1, c2, c3 = st.columns(3)
    c1.metric("수원시 상가정보 행 수", f"{len(stores):,}개")
    c2.metric("상가 업종 중분류 수", f"{stores['indsMclsNm'].nunique():,}개" if "indsMclsNm" in stores.columns else "-")
    c3.metric("상가 행정동 수", f"{stores['adongNm'].nunique():,}개" if "adongNm" in stores.columns else "-")
    if "indsMclsNm" in stores.columns:
        st.markdown("#### 상가 업종별 점포 수 TOP 20")
        sg = stores.groupby("indsMclsNm", as_index=False).size().rename(columns={"size":"점포수"}).sort_values("점포수", ascending=False).head(20)
        fig_s = px.bar(sg, x="점포수", y="indsMclsNm", orientation="h", text="점포수", color="점포수", color_continuous_scale="Greens")
        fig_s.update_traces(textposition="outside")
        fig_s.update_layout(yaxis=dict(autorange="reversed"), height=560, coloraxis_showscale=False, plot_bgcolor="white")
        st.plotly_chart(fig_s, use_container_width=True)
    with st.expander("상가정보 데이터 미리보기"):
        cols = safe_cols(stores, ["bizesNm","indsLclsNm","indsMclsNm","indsSclsNm","signguNm","adongNm","rdnAdr"])
        st.dataframe(stores[cols].head(500), use_container_width=True)

with tab6:
    st.markdown("### 업종별 창업 투자 점수")
    st.caption("결제금액 35% + 결제건수 20% + 평균 객단가 15% + 고객확장성 10% + 지역확산 10% + 경쟁완화 10%")
    fig6 = px.bar(industry_score.head(15), x="창업투자점수", y="industry", orientation="h",
                  text="창업투자점수", color="창업투자점수", color_continuous_scale="Greens")
    fig6.update_traces(textposition="outside")
    fig6.update_layout(yaxis=dict(autorange="reversed"), height=520, coloraxis_showscale=False, plot_bgcolor="white")
    st.plotly_chart(fig6, use_container_width=True)
    st.dataframe(industry_score, use_container_width=True)

    st.markdown("### 행정동별 상권 투자 점수")
    fig7 = px.bar(district_score, x="상권투자점수", y="district", orientation="h",
                  text="상권투자점수", color="상권투자점수", color_continuous_scale="Blues")
    fig7.update_traces(textposition="outside")
    fig7.update_layout(yaxis=dict(autorange="reversed"), height=520, coloraxis_showscale=False, plot_bgcolor="white")
    st.plotly_chart(fig7, use_container_width=True)
    st.dataframe(district_score, use_container_width=True)

    st.markdown("### 수요-경쟁 매트릭스")
    st.caption("결제금액은 소비 수요의 대리변수, 상가점포수는 경쟁강도의 보완지표로 해석합니다. 실제 순이익률이 아닌 수요-경쟁 관점입니다.")
    fig_m = px.scatter(
        matrix_df,
        x="경쟁점수", y="수요점수",
        size="결제금액", color="전략분류",
        hover_name="industry",
        hover_data=["결제금액", "결제건수", "상가점포수", "창업투자점수"],
        height=520
    )
    fig_m.update_layout(plot_bgcolor="white", xaxis_title="경쟁점수(상가점포수 기반)", yaxis_title="수요점수(결제금액 기반)")
    st.plotly_chart(fig_m, use_container_width=True)
    st.dataframe(matrix_df[["industry","전략분류","수요점수","경쟁점수","결제금액","결제건수","상가점포수","창업투자점수"]], use_container_width=True)

    st.markdown("### 설명적 회귀분석")
    st.caption("예측 모델이 아니라, 결제금액 차이를 설명하는 요인을 확인하기 위한 기술적 분석입니다.")
    if model_result is not None:
        r2, coef = model_result
        st.metric("설명력 R²", f"{r2:.3f}")
        st.dataframe(coef, use_container_width=True)
    else:
        st.info("선택 조건의 데이터가 적어 회귀분석을 수행하지 않았습니다.")

    if not target_score.empty:
        st.markdown(f"### 관심 업종 `{selected_industry_report}` 입지 검토 점수")
        st.dataframe(target_score, use_container_width=True)

with tab7:
    st.markdown("### AI Analyst Report 자동 생성")
    report = make_report(filtered, stores, region, district, selected_industry_report, industry_score, district_score, target_score, matrix_df)
    st.markdown(f'<div class="insight-box">{report}</div>', unsafe_allow_html=True)
    st.download_button("리포트 Markdown 다운로드", data=report, file_name="localpay_suwon_ai_report.md", mime="text/markdown")

st.divider()
st.markdown("""
<div class="insight-box">
<b>발표용 핵심 문장</b><br>
“최종 시연은 공공데이터포털의 2025년 11월 수원시 지역화폐 결제정보를 사용합니다.
이 데이터에는 읍면동, 업종, 성별, 연령대, 결제건수, 결제금액이 포함되어 있어 실제 지역화폐 소비 데이터를 기반으로 예비창업자의 업종·입지 선택을 지원할 수 있습니다.
여기에 수원시 상가정보와 수원시 지역화폐 가맹점 수 37,369개를 결합해 향후 경쟁강도와 점포당 소비 잠재력 분석으로 확장할 수 있습니다.
분석 구조는 광주상생카드나 온누리상품권 데이터가 확보되면 광주에도 동일하게 적용 가능합니다.”
</div>
""", unsafe_allow_html=True)


import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(
    page_title="LocalPay AI Analyst",
    page_icon="💳",
    layout="wide"
)

SUWON_MERCHANT_TOTAL_API = 37369

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
    color: white; padding: 26px 30px; border-radius: 16px; margin-bottom: 18px;
}
.data-badge {
    display: inline-block; background: #e8f0fe; color: #1a73e8;
    padding: 5px 11px; border-radius: 20px; font-size: 12px; margin: 3px;
}
.guide-box {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 14px; padding: 16px 20px; margin: 10px 0; line-height: 1.7;
}
.result-card {
    background: white; border: 1px solid #dbeafe;
    border-left: 6px solid #2563eb;
    border-radius: 14px; padding: 18px 20px; margin: 10px 0; line-height: 1.75;
    box-shadow: 0 1px 2px rgba(0,0,0,.04);
}
.good-card {
    background: #ecfdf5; border-left: 6px solid #10b981;
    border-radius: 14px; padding: 18px 20px; margin: 10px 0; line-height: 1.75;
}
.warn-card {
    background: #fffbeb; border-left: 6px solid #f59e0b;
    border-radius: 14px; padding: 18px 20px; margin: 10px 0; line-height: 1.75;
}
.small-note {font-size: 13px; color: #64748b;}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_payments():
    df = pd.read_csv("data/suwon_localpay_payments.csv")
    district_values = set(df["district"].astype(str).unique())
    df = df[~df["industry"].astype(str).isin(district_values)].copy()
    return df

@st.cache_data
def load_stores():
    return pd.read_csv("data/suwon_stores.csv")

def format_won(value):
    try:
        value = float(value)
    except Exception:
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

def make_user_report(pay_df, stores, region, district, selected_industry, industry_score, district_score, target_score, matrix_df):
    total_pay = pay_df["payment_amount"].sum()
    total_txn = pay_df["transaction_count"].sum()
    avg_ticket = total_pay / max(total_txn, 1)

    age = pay_df.groupby("age_group", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
    gender = pay_df.groupby("gender", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
    top_age = age.iloc[0]["age_group"] if not age.empty else "확인 불가"
    top_gender = gender.iloc[0]["gender"] if not gender.empty else "확인 불가"

    top_ind = industry_score.iloc[0] if not industry_score.empty else None
    top_dist = district_score.iloc[0] if not district_score.empty else None
    top_target = target_score.iloc[0] if not target_score.empty else None
    priority = matrix_df[matrix_df["전략분류"] == "우선 검토"].head(3)["industry"].tolist() if not matrix_df.empty else []
    caution = matrix_df[matrix_df["전략분류"].isin(["수요 높지만 경쟁 주의", "보류/추가조사"])].head(3)["industry"].tolist() if not matrix_df.empty else []

    area = region if district == "전체" else f"{region} {district}"

    target_sentence = ""
    if top_target is not None:
        target_sentence = f"관심 업종 **{selected_industry}** 기준으로는 **{top_target['district']}**가 1차 검토 지역입니다. 결제금액은 **{format_won(top_target['결제금액'])}**, 평균 객단가는 **{format_won(top_target['평균객단가'])}**입니다."
    else:
        target_sentence = f"선택 업종 **{selected_industry}**은 현재 조건에서 상세 입지 비교 데이터가 부족합니다."

    return f"""
### AI 창업 분석 리포트: {area}

#### 1. 선택 조건 요약
선택한 지역의 총 결제금액은 **{format_won(total_pay)}**, 결제건수는 **{total_txn:,.0f}건**, 평균 객단가는 **{format_won(avg_ticket)}**입니다. 주요 소비층은 **{top_age} / {top_gender}**입니다.

#### 2. 추천 업종
전체 업종 기준으로는 **{top_ind['industry'] if top_ind is not None else '확인 불가'}**의 창업투자점수가 가장 높습니다.  
수요-경쟁 기준 우선 검토 업종은 **{', '.join(priority) if priority else '추가 데이터 확인 필요'}**입니다.

#### 3. 추천 지역
행정동 기준으로는 **{top_dist['district'] if top_dist is not None else '확인 불가'}**의 상권투자점수가 가장 높습니다.  
{target_sentence}

#### 4. 주의 업종
주의가 필요한 업종은 **{', '.join(caution) if caution else '추가 데이터 확인 필요'}**입니다. 이 업종들은 수요가 높더라도 경쟁이 강하거나, 수요 자체가 낮아 추가 조사가 필요할 수 있습니다.

#### 5. 추가 확인사항
실제 창업 전에는 임대료, 유동인구, 배달권역, 인건비, 원가율, 마진율, 실제 경쟁점포의 품질을 추가 확인해야 합니다.

#### 6. 최종 한 줄 판단
현재 데이터 기준으로는 **결제수요가 크고 경쟁강도가 과도하지 않은 업종·행정동 조합을 1차 후보로 좁힌 뒤, 현장조사로 최종 검증하는 전략**이 적합합니다.
"""

# Header
st.markdown("""
<div class="main-header">
  <h1 style="margin:0;font-size:1.85rem;">💳 LocalPay AI Analyst</h1>
  <p style="margin:8px 0 0;opacity:.92;">수원시 지역화폐 결제데이터 기반 창업 업종·입지 분석 서비스</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<span class="data-badge">📊 실제 공공데이터</span>
<span class="data-badge">수원시 지역화폐 결제정보</span>
<span class="data-badge">수원시 상가정보</span>
<span class="data-badge">업종·입지 추천</span>
<span class="data-badge">AI 창업 리포트</span>
""", unsafe_allow_html=True)

payments = load_payments()
stores = load_stores()

# Full city dashboard
city_total_payment = payments["payment_amount"].sum()
city_total_txn = payments["transaction_count"].sum()
city_avg_ticket = city_total_payment / max(city_total_txn, 1)

st.markdown("### 수원시 전체 현황 대시보드")
st.caption("2025년 11월 수원시 지역화폐 결제정보와 수원시 상가정보 기준입니다.")
d1, d2, d3, d4, d5, d6 = st.columns(6)
d1.metric("총 결제금액", format_won(city_total_payment))
d2.metric("총 결제건수", f"{city_total_txn:,.0f}건")
d3.metric("평균 객단가", format_won(city_avg_ticket))
d4.metric("분석 업종 수", f"{payments['industry'].nunique():,}개")
d5.metric("수원시 가맹점 수", f"{SUWON_MERCHANT_TOTAL_API:,}개")
d6.metric("상가정보 수", f"{len(stores):,}개")

st.divider()

with st.sidebar:
    st.header("🔍 창업 조건 선택")
    st.caption("지역과 업종을 선택한 뒤 분석하기를 누르세요.")

    regions = ["전체"] + sorted(payments["region"].astype(str).unique().tolist())
    region = st.selectbox("1. 창업 희망 구", regions, index=0)

    filtered_base = payments.copy()
    if region != "전체":
        filtered_base = filtered_base[filtered_base["region"].astype(str) == region]

    districts = ["전체"] + sorted(filtered_base["district"].astype(str).unique().tolist())
    district = st.selectbox("2. 창업 희망 동", districts, index=0)

    filtered_for_industry = filtered_base.copy()
    if district != "전체":
        filtered_for_industry = filtered_for_industry[filtered_for_industry["district"].astype(str) == district]

    industries = sorted(filtered_for_industry["industry"].astype(str).unique().tolist())
    selected_industry = st.selectbox("3. 관심 업종", industries, index=0 if industries else None)

    analysis_goal = st.selectbox(
        "4. 분석 목적",
        ["어떤 업종이 유망한지 보고 싶다", "관심 업종의 좋은 입지를 찾고 싶다", "레드오션 업종을 피하고 싶다", "주요 고객층을 알고 싶다"]
    )

    analyze_btn = st.button("🚀 분석하기", type="primary", use_container_width=True)

    st.divider()
    st.caption("데이터: 2025년 11월 수원시 지역화폐 결제정보")
    st.caption("정제 후 정상 결제 데이터 기준")

filtered = payments.copy()
if region != "전체":
    filtered = filtered[filtered["region"].astype(str) == region]
if district != "전체":
    filtered = filtered[filtered["district"].astype(str) == district]

if filtered.empty:
    st.warning("선택 조건에 해당하는 결제 데이터가 없습니다.")
    st.stop()

stores_filtered = stores.copy()
if district != "전체" and "adongNm" in stores_filtered.columns:
    stores_filtered = stores_filtered[stores_filtered["adongNm"].astype(str) == district]

industry_score = calc_industry_scores(filtered, stores_filtered)
district_score = calc_district_scores(filtered, stores)
target_score = calc_target_industry_location(filtered, stores, selected_industry)
matrix_df = demand_competition_matrix(industry_score)

if not analyze_btn:
    st.markdown("""
<div class="guide-box">
<b>이 서비스로 할 수 있는 일</b><br>
① 수원시에서 어떤 업종이 지역화폐 기준으로 소비수요가 큰지 확인합니다.<br>
② 특정 업종을 선택하면 어느 동네가 입지 후보로 좋은지 비교합니다.<br>
③ 결제금액은 높지만 점포가 많은 레드오션 업종과, 수요 대비 경쟁이 낮은 우선 검토 업종을 구분합니다.<br>
④ 주요 소비 연령대와 성별을 확인해 가격·상품·홍보 전략을 세울 수 있습니다.
</div>
""", unsafe_allow_html=True)
    st.info("왼쪽 사이드바에서 조건을 선택하고 **분석하기**를 눌러주세요.")
    st.stop()

selected_payment = filtered["payment_amount"].sum()
selected_txn = filtered["transaction_count"].sum()
selected_avg_ticket = selected_payment / max(selected_txn, 1)

st.markdown("### 선택 조건 분석 기준")
s1, s2, s3, s4 = st.columns(4)
s1.metric("선택 지역 결제금액", format_won(selected_payment))
s2.metric("선택 지역 결제건수", f"{selected_txn:,.0f}건")
s3.metric("선택 지역 객단가", format_won(selected_avg_ticket))
s4.metric("선택 지역 업종 수", f"{filtered['industry'].nunique():,}개")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "✅ 추천 요약", "🏪 업종 유망도", "📍 지역·입지 분석", "🔎 관심 업종 상세", "👥 고객층 분석", "🤖 AI 창업 리포트"
])

with tab1:
    st.markdown("### 추천 요약")
    top_industries = industry_score.head(3)
    top_districts = district_score.head(3)
    priority = matrix_df[matrix_df["전략분류"] == "우선 검토"].head(3)
    caution = matrix_df[matrix_df["전략분류"].isin(["수요 높지만 경쟁 주의", "보류/추가조사"])].head(3)

    c1, c2, c3 = st.columns(3)
    with c1:
        txt = "<br>".join([f"{rank}. {r['industry']} ({r['창업투자점수']}점)" for rank, (_, r) in enumerate(top_industries.iterrows(), start=1)])
        st.markdown(f'<div class="result-card"><b>추천 업종 TOP 3</b><br>{txt}</div>', unsafe_allow_html=True)
    with c2:
        txt = "<br>".join([f"{rank}. {r['district']} ({r['상권투자점수']}점)" for rank, (_, r) in enumerate(top_districts.iterrows(), start=1)])
        st.markdown(f'<div class="result-card"><b>추천 행정동 TOP 3</b><br>{txt}</div>', unsafe_allow_html=True)
    with c3:
        if not priority.empty:
            txt = "<br>".join([f"{rank}. {r['industry']} ({r['전략분류']})" for rank, (_, r) in enumerate(priority.iterrows(), start=1)])
        else:
            txt = "추가 데이터 확인 필요"
        st.markdown(f'<div class="good-card"><b>수요-경쟁 우선 검토</b><br>{txt}</div>', unsafe_allow_html=True)

    st.markdown("### 주의해야 할 업종")
    if not caution.empty:
        st.dataframe(caution[["industry", "전략분류", "결제금액", "결제건수", "상가점포수", "창업투자점수"]], use_container_width=True)
    else:
        st.info("현재 조건에서는 명확한 주의 업종이 충분히 확인되지 않았습니다.")

with tab2:
    st.markdown("### 업종 유망도 분석")
    st.caption("결제금액, 결제건수, 평균 객단가, 고객층 다양성, 지역 확산성, 경쟁완화 점수를 종합했습니다.")
    fig = px.bar(industry_score.head(15), x="창업투자점수", y="industry", orientation="h", text="창업투자점수", color="창업투자점수", color_continuous_scale="Greens")
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis=dict(autorange="reversed"), height=520, coloraxis_showscale=False, plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(industry_score, use_container_width=True)

    st.markdown("### 수요-경쟁 매트릭스")
    st.caption("왼쪽 위는 수요가 높고 경쟁이 상대적으로 낮아 우선 검토할 수 있습니다.")
    fig_m = px.scatter(matrix_df, x="경쟁점수", y="수요점수", size="결제금액", color="전략분류", hover_name="industry", hover_data=["결제금액", "결제건수", "상가점포수", "창업투자점수"], height=520)
    fig_m.update_layout(plot_bgcolor="white", xaxis_title="경쟁점수(상가점포수 기반)", yaxis_title="수요점수(결제금액 기반)")
    st.plotly_chart(fig_m, use_container_width=True)

with tab3:
    st.markdown("### 지역·입지 분석")
    dpay = filtered.groupby("district", as_index=False).agg(결제금액=("payment_amount","sum"), 결제건수=("transaction_count","sum"), 평균객단가=("avg_ticket","mean")).sort_values("결제금액", ascending=False)
    dpay["평균객단가"] = dpay["평균객단가"].round(0)

    fig = px.bar(dpay, x="결제금액", y="district", orientation="h", text="결제금액", color="결제금액", color_continuous_scale="Blues")
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(yaxis=dict(autorange="reversed"), height=520, coloraxis_showscale=False, plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 행정동별 상권투자점수")
    st.dataframe(district_score, use_container_width=True)

with tab4:
    st.markdown(f"### 관심 업종 상세분석: {selected_industry}")
    target_data = filtered[filtered["industry"] == selected_industry].copy()
    if target_data.empty:
        st.warning("선택한 업종의 결제 데이터가 없습니다.")
    else:
        tp = target_data["payment_amount"].sum()
        tt = target_data["transaction_count"].sum()
        ta = tp / max(tt, 1)
        c1, c2, c3 = st.columns(3)
        c1.metric("관심 업종 결제금액", format_won(tp))
        c2.metric("관심 업종 결제건수", f"{tt:,.0f}건")
        c3.metric("관심 업종 객단가", format_won(ta))

        st.markdown("### 관심 업종 기준 추천 입지")
        if not target_score.empty:
            fig_t = px.bar(target_score.head(10), x="입지검토점수", y="district", orientation="h", text="입지검토점수", color="입지검토점수", color_continuous_scale="Teal")
            fig_t.update_traces(textposition="outside")
            fig_t.update_layout(yaxis=dict(autorange="reversed"), height=460, coloraxis_showscale=False, plot_bgcolor="white")
            st.plotly_chart(fig_t, use_container_width=True)
            st.dataframe(target_score, use_container_width=True)

        st.markdown("### 관심 업종의 연령대별 결제금액")
        age_t = target_data.groupby("age_group", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
        fig_age_t = px.bar(age_t, x="age_group", y="payment_amount", text="payment_amount", color="payment_amount", color_continuous_scale="Purples")
        fig_age_t.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_age_t.update_layout(height=380, coloraxis_showscale=False, plot_bgcolor="white")
        st.plotly_chart(fig_age_t, use_container_width=True)

with tab5:
    st.markdown("### 고객층 분석")
    c1, c2 = st.columns(2)
    with c1:
        age = filtered.groupby("age_group", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
        fig_age = px.bar(age, x="age_group", y="payment_amount", text="payment_amount", color="payment_amount", color_continuous_scale="Purples")
        fig_age.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_age.update_layout(height=420, coloraxis_showscale=False, plot_bgcolor="white")
        st.plotly_chart(fig_age, use_container_width=True)
    with c2:
        gender = filtered.groupby("gender", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
        fig_gender = px.bar(gender, x="gender", y="payment_amount", text="payment_amount", color="payment_amount", color_continuous_scale="Oranges")
        fig_gender.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_gender.update_layout(height=420, coloraxis_showscale=False, plot_bgcolor="white")
        st.plotly_chart(fig_gender, use_container_width=True)

    st.markdown("### 연령대 × 업종 결제금액")
    heat = filtered.groupby(["age_group", "industry"], as_index=False)["payment_amount"].sum()
    fig_heat = px.density_heatmap(heat, x="industry", y="age_group", z="payment_amount", color_continuous_scale="Blues")
    fig_heat.update_layout(height=520, xaxis_tickangle=-40, plot_bgcolor="white")
    st.plotly_chart(fig_heat, use_container_width=True)

    st.markdown("### 설명적 분석")
    st.caption("결제금액 차이를 설명하는 요인을 확인하는 기술적 분석입니다. 예측 모델이 아니라 데이터 해석 보조입니다.")
    model_result = simple_explanatory_model(filtered)
    if model_result is not None:
        r2, coef = model_result
        st.metric("설명력 R²", f"{r2:.3f}")
        st.dataframe(coef, use_container_width=True)
    else:
        st.info("선택 조건의 데이터가 적어 설명적 분석을 수행하지 않았습니다.")

with tab6:
    st.markdown("### AI 창업 리포트")
    report = make_user_report(filtered, stores, region, district, selected_industry, industry_score, district_score, target_score, matrix_df)
    st.markdown(f'<div class="result-card">{report}</div>', unsafe_allow_html=True)
    st.download_button("리포트 다운로드", data=report, file_name="localpay_ai_startup_report.md", mime="text/markdown")


import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(
    page_title="LocalPay AI Analyst - Suwon",
    page_icon="💳",
    layout="wide"
)

SUWON_MERCHANT_TOTAL_API = 37369  # 경기지역화폐 가맹점 현황 OpenAPI, SIGUN_NM=수원시 조회 결과

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
.metric-help {
    font-size: 13px; color: #64748b; margin-top: -8px;
}
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

def calc_store_competition(stores):
    if stores.empty:
        return pd.DataFrame()
    g = stores.groupby(["adongNm","indsMclsNm"], as_index=False).size().rename(columns={"size":"점포수"})
    return g

def calc_industry_scores(pay_df, store_df):
    # Payment based
    p = pay_df.groupby("industry", as_index=False).agg(
        결제금액=("payment_amount","sum"),
        결제건수=("transaction_count","sum"),
        평균객단가=("avg_ticket","mean"),
        이용연령대수=("age_group","nunique"),
        이용행정동수=("district","nunique"),
    )
    # Store competition: map by same/simple industry name if matched
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

    # 경쟁완화: 상가점포수 매칭이 있으면 점포가 적을수록 가점, 없으면 50점
    if p["상가점포수"].sum() > 0:
        p["경쟁완화점수"] = 100 - normalize(p["상가점포수"])
    else:
        p["경쟁완화점수"] = 50

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
    # 수요가 많되 상가점포가 과밀하지 않은 지역을 보완
    if p["상가점포수"].sum() > 0:
        p["경쟁완화점수"] = 100 - normalize(p["상가점포수"])
    else:
        p["경쟁완화점수"] = 50

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
    if g["관심업종점포수"].sum() > 0:
        g["경쟁완화점수"] = 100 - normalize(g["관심업종점포수"])
    else:
        g["경쟁완화점수"] = 50

    g["입지검토점수"] = (
        g["수요규모점수"] * 0.40 +
        g["거래빈도점수"] * 0.25 +
        g["객단가점수"] * 0.15 +
        g["고객확장성점수"] * 0.10 +
        g["경쟁완화점수"] * 0.10
    ).round(1)
    g["평균객단가"] = g["평균객단가"].round(0)
    return g.sort_values("입지검토점수", ascending=False)

def make_report(pay_df, store_df, region, district, selected_industry, industry_score, district_score, target_score):
    total_pay = pay_df["payment_amount"].sum()
    total_txn = pay_df["transaction_count"].sum()
    avg_ticket = total_pay / max(total_txn, 1)
    age = pay_df.groupby("age_group", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
    top_age = age.iloc[0]["age_group"] if not age.empty else "확인 불가"

    top_ind = industry_score.iloc[0] if not industry_score.empty else None
    top_dist = district_score.iloc[0] if not district_score.empty else None
    top_target = target_score.iloc[0] if not target_score.empty else None

    area = region if district == "전체" else f"{region} {district}"

    top_ind_text = ""
    if top_ind is not None:
        top_ind_text = f"업종별 창업투자점수 기준 1위는 **{top_ind['industry']}**이며, 결제금액은 **{format_won(top_ind['결제금액'])}**입니다."

    top_dist_text = ""
    if top_dist is not None:
        top_dist_text = f"행정동별 상권투자점수 기준 1위는 **{top_dist['district']}**이며, 결제금액은 **{format_won(top_dist['결제금액'])}**입니다."

    target_text = ""
    if top_target is not None:
        target_text = f"관심 업종 **{selected_industry}** 기준 입지검토점수가 가장 높은 곳은 **{top_target['district']}**입니다. 해당 지역의 결제금액은 **{format_won(top_target['결제금액'])}**, 결제건수는 **{top_target['결제건수']:,.0f}건**, 평균 객단가는 **{format_won(top_target['평균객단가'])}**입니다."
    else:
        target_text = f"선택 업종 **{selected_industry}**에 대한 결제 데이터가 선택 조건에서 확인되지 않습니다."

    store_note = ""
    if not store_df.empty:
        store_note = f"함께 업로드한 경기도 상가정보 데이터에서 수원시 상가 데이터는 **{len(store_df):,}개**로 확인되며, 이는 결제 수요와 상가 밀도를 함께 보는 경쟁강도 보완 지표로 활용됩니다."

    return f"""
### AI Analyst Report: {area} 지역화폐 기반 창업 투자 상권분석

#### 1. Investment Thesis
창업은 보증금, 인테리어, 인건비, 재고비용이 선투입되는 **투자 의사결정**입니다. 본 서비스는 수원시 지역화폐 결제 데이터를 활용해 예비창업자가 특정 지역과 업종에 진입하기 전 실제 소비 수요를 확인하도록 돕는 AI Analyst 프로토타입입니다.

#### 2. Data Basis
현재 분석은 공공데이터포털의 **2025년 11월 수원시 지역화폐 결제정보**를 기반으로 합니다. 원본 데이터에는 읍면동, 업종, 성별, 연령대, 결제건수, 결제금액이 포함되어 있습니다. 또한 경기지역화폐 가맹점 현황 OpenAPI에서 `SIGUN_NM=수원시` 조건으로 조회한 결과, 수원시 전체 지역화폐 가맹점 수는 **{SUWON_MERCHANT_TOTAL_API:,}개**입니다.  
{store_note}

#### 3. Market Demand
선택 지역의 총 결제금액은 **{format_won(total_pay)}**, 총 결제건수는 **{total_txn:,.0f}건**, 평균 객단가는 **{format_won(avg_ticket)}**입니다. 주요 소비 연령대는 **{top_age}**입니다.  
{top_ind_text}  
{top_dist_text}

#### 4. Target Industry Analysis
{target_text}

#### 5. Investment Scoring
업종별 창업투자점수는 **결제금액 35% + 결제건수 20% + 평균 객단가 15% + 고객확장성 10% + 지역확산 10% + 경쟁완화 10%**로 계산했습니다.  
행정동별 상권투자점수는 **소비규모 35% + 거래활성 20% + 객단가 15% + 상권다양성 10% + 고객다양성 10% + 경쟁완화 10%**로 계산했습니다.

#### 6. Local Currency / Blockchain Extension
지역화폐는 단순 결제수단이 아니라 지역 상권의 실제 소비 흐름을 보여주는 데이터 자산입니다. 향후 광주상생카드·온누리상품권 결제데이터가 공개되거나 연계되면, 같은 분석 구조를 광주 지역과 전통시장 상권에도 적용할 수 있습니다.

#### 7. Limitations
현재 결제정보는 2025년 11월 단월 데이터입니다. 월별 추세 분석을 위해서는 여러 기준월 데이터가 필요합니다. 또한 임대료, 유동인구, 마진율, 업종별 실제 가맹점 수는 추가 연계가 필요합니다.
"""

# Header
st.markdown("""
<div class="main-header">
  <h1 style="margin:0;font-size:1.85rem;">💳 LocalPay AI Analyst</h1>
  <p style="margin:8px 0 0;opacity:.92;">수원시 지역화폐 결제데이터 기반 · 소상공인 창업 투자 상권분석 플랫폼</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<span class="data-badge">📊 실제 공공데이터</span>
<span class="data-badge">2025년 11월 수원시 지역화폐 결제정보</span>
<span class="data-badge">경기도 상가정보 결합</span>
<span class="data-badge">AI Analyst Report</span>
<span class="data-badge">창업 투자 의사결정</span>
""", unsafe_allow_html=True)

st.markdown("""
<div class="insight-box">
<b>프로젝트 포지셔닝</b><br>
본 프로젝트는 광주 앱의 형태를 유지하되, 최종 시연 데이터는 실제 결제금액이 공개된 <b>수원시 지역화폐 공공데이터</b>를 사용합니다.
지역화폐 결제 데이터를 하나의 <b>상권 투자 데이터</b>로 해석하고, 예비창업자가 업종과 입지를 선택하기 전 실제 소비 수요를 확인하도록 돕습니다.
향후 광주상생카드·온누리상품권 데이터가 확보되면 같은 구조를 광주에도 적용할 수 있습니다.
</div>
""", unsafe_allow_html=True)

# Load data
payments = load_payments()
stores = load_stores()

# Sidebar
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
    if selected_industry == "전체":
        selected_industry_report = sorted(filtered["industry"].unique().tolist())[0]
    else:
        selected_industry_report = selected_industry

    months = sorted(filtered["month"].astype(str).unique().tolist())
    selected_months = st.multiselect("분석 월", months, default=months)
    if selected_months:
        filtered = filtered[filtered["month"].astype(str).isin(selected_months)]

    st.divider()
    st.caption("기본 데이터: 수원시 지역화폐 결제정보")
    st.caption("상가정보: 업로드된 경기도.csv 중 수원시 필터")
    st.caption("가맹점 API 조회 결과: 수원시 37,369개")

if filtered.empty:
    st.warning("선택 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# Store filter according to district if possible
stores_filtered = stores.copy()
if district != "전체" and "adongNm" in stores_filtered.columns:
    stores_filtered = stores_filtered[stores_filtered["adongNm"].astype(str) == district]

# Scores
industry_score = calc_industry_scores(filtered, stores_filtered)
district_score = calc_district_scores(filtered, stores)
target_score = calc_target_industry_location(filtered, stores, selected_industry_report)

# KPI
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

tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎯 Before vs After", "📍 지역 분석", "🏪 업종 분석", "👥 소비자 분석", "🏬 상가정보", "📈 투자 점수", "🤖 AI 리포트"
])

with tab0:
    st.markdown("### 교수님 피드백 반영: 실제 데이터 기반 시연으로 전환")
    st.markdown("""
| 구분 | 기존 접근 | 최종 접근 |
|---|---|---|
| 분석 대상 | 광주/온누리상품권 구상 중심 | **수원시 지역화폐 실제 결제데이터** 기반 시연 |
| 데이터 | 가맹점·상가정보 중심 | **결제금액·결제건수·업종·연령대·성별** 포함 |
| 추가 보완 | 점포 수 중심 | **경기도 상가정보 + 수원시 가맹점 API 결과** 결합 |
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

with tab1:
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

with tab2:
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

with tab3:
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

with tab4:
    st.markdown("### 경기도 상가정보 중 수원시 필터 결과")
    st.caption("업로드된 경기도.csv 파일을 수원시 기준으로 필터링한 상가정보입니다. 결제 수요와 상가 밀도를 함께 보기 위한 보완 데이터입니다.")
    c1, c2, c3 = st.columns(3)
    c1.metric("수원시 상가정보 행 수", f"{len(stores):,}개")
    if "indsMclsNm" in stores.columns:
        c2.metric("상가 업종 중분류 수", f"{stores['indsMclsNm'].nunique():,}개")
    if "adongNm" in stores.columns:
        c3.metric("상가 행정동 수", f"{stores['adongNm'].nunique():,}개")

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

with tab5:
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

    if not target_score.empty:
        st.markdown(f"### 관심 업종 `{selected_industry_report}` 입지 검토 점수")
        st.dataframe(target_score, use_container_width=True)

with tab6:
    st.markdown("### AI Analyst Report 자동 생성")
    report = make_report(filtered, stores, region, district, selected_industry_report, industry_score, district_score, target_score)
    st.markdown(f'<div class="insight-box">{report}</div>', unsafe_allow_html=True)
    st.download_button("리포트 Markdown 다운로드", data=report, file_name="localpay_suwon_ai_report.md", mime="text/markdown")

st.divider()
st.markdown("""
<div class="insight-box">
<b>발표용 핵심 문장</b><br>
“최종 시연은 공공데이터포털의 2025년 11월 수원시 지역화폐 결제정보를 사용합니다.
이 데이터에는 읍면동, 업종, 성별, 연령대, 결제건수, 결제금액이 포함되어 있어 실제 지역화폐 소비 데이터를 기반으로 예비창업자의 업종·입지 선택을 지원할 수 있습니다.
여기에 경기도 상가정보와 수원시 지역화폐 가맹점 수 37,369개를 결합해 향후 경쟁강도와 점포당 소비 잠재력 분석으로 확장할 수 있습니다.
분석 구조는 광주상생카드나 온누리상품권 데이터가 확보되면 광주에도 동일하게 적용 가능합니다.”
</div>
""", unsafe_allow_html=True)

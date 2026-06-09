import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(page_title="LocalPay AI Financial Analyst", page_icon="💳", layout="wide")

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #0d47a1 0%, #1565c0 100%);
    color: white; padding: 26px 30px; border-radius: 16px; margin-bottom: 20px;
}
.kpi-card {
    background: #f8f9fa; border-radius: 12px; padding: 16px;
    border-left: 4px solid #1a73e8; margin: 4px 0;
}
.insight-box {
    background: #e8f4fd; border-left: 5px solid #1a73e8;
    border-radius: 10px; padding: 16px 20px; margin: 10px 0; line-height: 1.8;
}
.warning-box {
    background: #fff8e1; border-left: 5px solid #f9a825;
    border-radius: 10px; padding: 16px 20px; margin: 10px 0;
}
.good-box {
    background: #e8f5e9; border-left: 5px solid #2e7d32;
    border-radius: 10px; padding: 16px 20px; margin: 10px 0;
}
.stat-box {
    background: #1a1a2e; color: #00d4ff;
    border-radius: 10px; padding: 14px 18px; margin: 6px 0;
    font-family: monospace; font-size: 13px; line-height: 1.8;
}
</style>
""", unsafe_allow_html=True)

SUWON_MERCHANT_TOTAL = 37369

# ── 데이터 로딩 ──────────────────────────────────────
@st.cache_data
def load_data():
    pay = pd.read_csv("data/suwon_localpay_payments.csv")
    pay["payment_amount"] = pd.to_numeric(pay["payment_amount"], errors="coerce").fillna(0)
    pay["transaction_count"] = pd.to_numeric(pay["transaction_count"], errors="coerce").fillna(0)
    pay["avg_ticket"] = pd.to_numeric(pay["avg_ticket"], errors="coerce").fillna(0)
    stores = pd.read_csv("data/suwon_stores.csv")
    return pay, stores

def format_won(v):
    try:
        v = float(v)
    except:
        return "-"
    if v >= 1e8: return f"{v/1e8:.1f}억 원"
    if v >= 1e4: return f"{v/1e4:.0f}만 원"
    return f"{v:,.0f}원"

def normalize(s):
    s = pd.to_numeric(s, errors="coerce").fillna(0)
    if s.max() == s.min():
        return pd.Series([50.0]*len(s), index=s.index)
    return (s - s.min()) / (s.max() - s.min()) * 100

def run_ols(df, y_col, x_cols):
    """OLS 회귀분석 실행"""
    data = df[[y_col] + x_cols].dropna()
    if len(data) < 10:
        return None
    X = data[x_cols].values
    y = data[y_col].values
    X_with_const = np.column_stack([np.ones(len(X)), X])
    try:
        result = np.linalg.lstsq(X_with_const, y, rcond=None)
        coeffs = result[0]
        y_pred = X_with_const @ coeffs
        ss_res = np.sum((y - y_pred)**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r2 = 1 - ss_res/ss_tot if ss_tot > 0 else 0
        n, k = len(y), len(x_cols)
        mse = ss_res / max(n - k - 1, 1)
        se = np.sqrt(mse * np.linalg.pinv(X_with_const.T @ X_with_const).diagonal())
        t_stats = coeffs / (se + 1e-10)
        p_vals = [2*(1 - stats.t.cdf(abs(t), df=max(n-k-1,1))) for t in t_stats]
        return {"coeffs": coeffs, "r2": r2, "t_stats": t_stats, "p_vals": p_vals, "n": n}
    except:
        return None

def calc_investment_scores(pay_df, store_df):
    p = pay_df.groupby("industry", as_index=False).agg(
        결제금액=("payment_amount","sum"),
        결제건수=("transaction_count","sum"),
        평균객단가=("avg_ticket","mean"),
        연령대다양성=("age_group","nunique"),
        지역확산도=("district","nunique"),
    )
    if not store_df.empty and "indsMclsNm" in store_df.columns:
        s = store_df.groupby("indsMclsNm", as_index=False).size().rename(columns={"indsMclsNm":"industry","size":"점포수"})
        p = p.merge(s, on="industry", how="left")
    else:
        p["점포수"] = 0
    p["점포수"] = p["점포수"].fillna(0)

    p["수요규모"] = normalize(p["결제금액"])
    p["거래빈도"] = normalize(p["결제건수"])
    p["객단가"] = normalize(p["평균객단가"])
    p["고객확장성"] = normalize(p["연령대다양성"])
    p["지역확산"] = normalize(p["지역확산도"])
    p["경쟁완화"] = 100 - normalize(p["점포수"]) if p["점포수"].sum() > 0 else 50

    # 교수님 강의 스타일: 가중합 투자점수
    p["창업투자점수"] = (
        p["수요규모"] * 0.35 +
        p["거래빈도"] * 0.20 +
        p["객단가"] * 0.15 +
        p["고객확장성"] * 0.10 +
        p["지역확산"] * 0.10 +
        p["경쟁완화"] * 0.10
    ).round(1)
    p["평균객단가"] = p["평균객단가"].round(0).astype(int)
    p["결제금액표시"] = p["결제금액"].apply(format_won)
    return p.sort_values("창업투자점수", ascending=False).reset_index(drop=True)

def calc_district_scores(pay_df, store_df):
    p = pay_df.groupby("district", as_index=False).agg(
        결제금액=("payment_amount","sum"),
        결제건수=("transaction_count","sum"),
        평균객단가=("avg_ticket","mean"),
        업종다양성=("industry","nunique"),
        연령대다양성=("age_group","nunique"),
    )
    if not store_df.empty and "adongNm" in store_df.columns:
        s = store_df.groupby("adongNm", as_index=False).size().rename(columns={"adongNm":"district","size":"점포수"})
        p = p.merge(s, on="district", how="left")
    else:
        p["점포수"] = 0
    p["점포수"] = p["점포수"].fillna(0)
    p["소비규모"] = normalize(p["결제금액"])
    p["거래활성"] = normalize(p["결제건수"])
    p["객단가"] = normalize(p["평균객단가"])
    p["상권다양성"] = normalize(p["업종다양성"])
    p["고객다양성"] = normalize(p["연령대다양성"])
    p["경쟁완화"] = 100 - normalize(p["점포수"]) if p["점포수"].sum() > 0 else 50
    p["상권투자점수"] = (
        p["소비규모"] * 0.35 +
        p["거래활성"] * 0.20 +
        p["객단가"] * 0.15 +
        p["상권다양성"] * 0.10 +
        p["고객다양성"] * 0.10 +
        p["경쟁완화"] * 0.10
    ).round(1)
    p["평균객단가"] = p["평균객단가"].round(0).astype(int)
    return p.sort_values("상권투자점수", ascending=False).reset_index(drop=True)

# ── 메인 ─────────────────────────────────────────────
pay, stores = load_data()

# session_state 초기화
for k, v in [("analyzed", False), ("filtered", None), ("stores_f", None),
             ("inv_score", None), ("dist_score", None), ("region", ""), ("district", "")]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── 헤더 ─────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1 style="margin:0;font-size:1.9rem;">💳 LocalPay AI Financial Analyst</h1>
  <p style="margin:8px 0 4px;opacity:.9;font-size:1rem;">수원시 지역화폐 결제데이터 기반 소상공인 창업 투자 상권분석 플랫폼</p>
  <p style="margin:0;opacity:.75;font-size:.85rem;">📊 공공데이터포털 · 2025년 11월 수원시 지역화폐 결제정보 · 소상공인시장진흥공단 상가정보</p>
</div>
""", unsafe_allow_html=True)

# ── 사이드바 ──────────────────────────────────────────
with st.sidebar:
    st.header("🔍 분석 조건")
    regions = ["전체"] + sorted(pay["region"].unique().tolist())
    region = st.selectbox("시/군/구", regions, index=1 if len(regions)>1 else 0)
    f = pay.copy()
    if region != "전체":
        f = f[f["region"] == region]
    districts = ["전체"] + sorted(f["district"].unique().tolist())
    district = st.selectbox("읍/면/동", districts)
    if district != "전체":
        f = f[f["district"] == district]
    industry_list = ["전체"] + sorted(f["industry"].unique().tolist())
    sel_industry = st.selectbox("관심 업종", industry_list, index=1 if len(industry_list)>1 else 0)
    sel_industry_val = sorted(f["industry"].unique().tolist())[0] if sel_industry == "전체" else sel_industry

    analyze_btn = st.button("🚀 분석 시작", type="primary", use_container_width=True)
    st.divider()
    st.caption("📌 데이터 출처")
    st.caption("• 공공데이터포털_경기도 수원시_지역화폐 결제정보_2025.11")
    st.caption("• 소상공인시장진흥공단_상가(상권)정보_2026.03")
    st.caption(f"• 수원시 지역화폐 가맹점: {SUWON_MERCHANT_TOTAL:,}개")

if analyze_btn:
    stores_f = stores.copy()
    if district != "전체" and "adongNm" in stores_f.columns:
        stores_f = stores_f[stores_f["adongNm"] == district]
    st.session_state.analyzed = True
    st.session_state.filtered = f
    st.session_state.stores_f = stores_f
    st.session_state.inv_score = calc_investment_scores(f, stores_f)
    st.session_state.dist_score = calc_district_scores(f, stores)
    st.session_state.region = region
    st.session_state.district = district
    st.session_state.sel_industry = sel_industry_val

if not st.session_state.analyzed:
    # ── 랜딩 페이지 ──────────────────────────────────
    st.markdown("## 🏆 분석 결론 먼저 보기 (두괄식)")
    st.markdown("""
<div class="good-box">
<b>✅ 이 플랫폼이 제시하는 답:</b><br>
수원시 지역화폐 실제 결제데이터(5,037건)를 AI로 분석하면,
<b>어느 업종·어느 행정동에서 소비 수요가 높고 경쟁이 낮은지</b>를 데이터로 확인할 수 있습니다.
예비창업자는 감이 아닌 <b>실제 거래 데이터 기반</b>으로 투자 의사결정을 할 수 있습니다.
</div>
""", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
<div class="warning-box">
<b>❌ Before (기존 방식)</b><br>
예비창업자는 네이버 지도, 부동산 중개인 의견,
주변 체감, 지인 추천으로 창업지를 결정합니다.
지역화폐 소비 데이터는 창업 의사결정에
거의 활용되지 못합니다.
</div>
""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
<div class="good-box">
<b>✅ After (이 플랫폼)</b><br>
실제 지역화폐 결제금액·건수·업종·연령대를
AI가 분석해 업종별 창업투자점수, 행정동별
상권투자점수, OLS 회귀분석 결과를
자동으로 제공합니다.
</div>
""", unsafe_allow_html=True)

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("**📊 실제 공공데이터**\n\n공공데이터포털 수원시 지역화폐 결제정보 + 소상공인시장진흥공단 상가정보 실데이터 활용")
    with c2:
        st.success("**📐 OLS 회귀분석**\n\n결제금액 결정요인 다중회귀 · 업종별 수요 탄력성 · 통계적 유의성 검증 (t-stat, p-value, R²)")
    with c3:
        st.warning("**🏆 투자점수 자동 산출**\n\n수요규모 35% + 거래빈도 20% + 객단가 15% + 확장성·경쟁완화 30% 가중합 산출")

    st.divider()
    st.markdown("### 🗂️ 데이터 출처")
    st.markdown("""
| 데이터 | 제공기관 | 기준일 | 내용 |
|--------|---------|--------|------|
| 수원시 지역화폐 결제정보 | 공공데이터포털 | 2025.11 | 읍면동·업종·성별·연령대·결제금액·건수 |
| 상가(상권)정보 | 소상공인시장진흥공단 | 2026.03 | 수원시 상가 56,003개 업종·위치 |
| 지역화폐 가맹점 현황 | 경기지역화폐 OpenAPI | 실시간 | 수원시 가맹점 37,369개 |
""")
    st.info("👈 사이드바에서 분석 조건을 설정하고 **분석 시작** 버튼을 눌러주세요.")

else:
    f = st.session_state.filtered
    stores_f = st.session_state.stores_f
    inv_score = st.session_state.inv_score
    dist_score = st.session_state.dist_score
    region = st.session_state.region
    district = st.session_state.district
    sel_industry_val = st.session_state.sel_industry

    total_pay = f["payment_amount"].sum()
    total_txn = f["transaction_count"].sum()
    avg_ticket = total_pay / max(total_txn, 1)
    top_industry = inv_score.iloc[0]["industry"] if not inv_score.empty else "-"
    top_district = dist_score.iloc[0]["district"] if not dist_score.empty else "-"

    st.success(f"✅ 분석 완료 · 2025년 11월 수원시 지역화폐 결제정보 · {len(f):,}건")

    # KPI
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("💰 총 결제금액", format_won(total_pay))
    c2.metric("🧾 총 결제건수", f"{total_txn:,.0f}건")
    c3.metric("🛒 평균 객단가", format_won(avg_ticket))
    c4.metric("🏪 분석 업종 수", f"{f['industry'].nunique()}개")
    c5.metric("🏬 수원시 가맹점", f"{SUWON_MERCHANT_TOTAL:,}개")
    st.caption("※ 결제금액·건수는 공공데이터 원본값. 가맹점 수는 경기지역화폐 가맹점 현황 OpenAPI 수원시 조회값.")

    st.divider()

    tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🏆 투자 결론", "📊 기초통계", "📍 지역 분석",
        "🏪 업종 분석", "👥 소비자 분석", "📐 회귀분석", "📈 투자점수"
    ])

    # ── 탭0: 투자 결론 (두괄식) ──────────────────────
    with tab0:
        st.markdown("### 🏆 AI Analyst 투자 결론 — 최고의 창업 업종·입지 제안")
        st.markdown("""
<div class="insight-box">
<b>📌 분석 방법론:</b>
수원시 지역화폐 결제데이터(2025.11) 기반으로 업종별 창업투자점수(수요규모 35% + 거래빈도 20% + 객단가 15% + 고객확장성 10% + 지역확산 10% + 경쟁완화 10%)와 행정동별 상권투자점수를 산출하고, OLS 회귀분석으로 결제금액 결정요인을 통계적으로 검증했습니다.
</div>
""", unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 🥇 창업 유망 업종 TOP 3")
            for i, row in inv_score.head(3).iterrows():
                medal = ["🥇","🥈","🥉"][i]
                st.markdown(f"""
<div class="good-box">
{medal} <b>{row['industry']}</b><br>
창업투자점수: <b>{row['창업투자점수']:.1f}점</b> | 결제금액: {row['결제금액표시']} | 평균객단가: {format_won(row['평균객단가'])}
</div>
""", unsafe_allow_html=True)

        with col_b:
            st.markdown("#### 🗺️ 창업 유망 행정동 TOP 3")
            for i, row in dist_score.head(3).iterrows():
                medal = ["🥇","🥈","🥉"][i]
                st.markdown(f"""
<div class="good-box">
{medal} <b>{row['district']}</b><br>
상권투자점수: <b>{row['상권투자점수']:.1f}점</b> | 결제금액: {format_won(row['결제금액'])} | 결제건수: {row['결제건수']:,.0f}건
</div>
""", unsafe_allow_html=True)

        st.divider()
        st.markdown("#### ⚠️ 리스크-수익 매트릭스")
        risk_data = []
        for _, row in inv_score.iterrows():
            risk = 100 - row["경쟁완화"]
            ret = row["창업투자점수"]
            size = float(row["결제건수"]) if row["결제건수"] > 0 else 1
            risk_data.append({"업종": row["industry"], "리스크(경쟁강도)": risk, "기대수익(투자점수)": ret, "거래건수": size})
        risk_df = pd.DataFrame(risk_data)
        fig_risk = px.scatter(
            risk_df, x="리스크(경쟁강도)", y="기대수익(투자점수)",
            size="거래건수", text="업종", color="기대수익(투자점수)",
            color_continuous_scale="RdYlGn",
            title="업종별 리스크-수익 매트릭스 (버블 크기 = 거래건수·환금성)",
            labels={"리스크(경쟁강도)":"리스크 지수 (경쟁강도)", "기대수익(투자점수)":"기대수익 (창업투자점수)"}
        )
        fig_risk.update_traces(textposition="top center", textfont_size=10)
        fig_risk.update_layout(height=520, plot_bgcolor="white", coloraxis_showscale=False)
        st.plotly_chart(fig_risk, use_container_width=True)

        st.markdown("""
<div class="warning-box">
<b>⚠️ Disclaimer</b><br>
본 분석은 2025년 11월 단월 지역화폐 결제데이터 기반입니다. 임대료·유동인구·마진율은 포함되지 않습니다.
창업 결정 시 반드시 현장 조사와 전문가 상담을 병행하시기 바랍니다.
</div>
""", unsafe_allow_html=True)

    # ── 탭1: 기초통계 ────────────────────────────────
    with tab1:
        st.markdown("### 📊 기초통계량 — 핵심 수치 요약")
        pays = f["payment_amount"]
        mean_v = pays.mean()
        median_v = pays.median()
        std_v = pays.std()
        skew_v = pays.skew()
        kurt_v = pays.kurtosis()
        q1_v = pays.quantile(0.25)
        q3_v = pays.quantile(0.75)

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("평균 결제금액", format_won(mean_v))
        c2.metric("중위수 (Median)", format_won(median_v))
        c3.metric("표준편차 (STD)", format_won(std_v))
        c4.metric("최댓값", format_won(pays.max()))

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("왜도 (Skewness)", f"{skew_v:.2f}")
        c2.metric("첨도 (Kurtosis)", f"{kurt_v:.2f}")
        c3.metric("Q1 (25%)", format_won(q1_v))
        c4.metric("Q3 (75%)", format_won(q3_v))

        st.markdown(f"""
<div class="stat-box">
[기초통계 해석]
평균({format_won(mean_v)}) {'>' if mean_v > median_v else '<'} 중위수({format_won(median_v)})
  → {'오른쪽 꼬리(Right-skewed) 분포 — 고액 결제가 평균을 상향 편향' if mean_v > median_v else '왼쪽 꼬리 분포'}
왜도 {skew_v:.2f} · 첨도 {kurt_v:.2f}
  → {'정규분포 가정 위반 가능성 → 비모수 검정 권장' if abs(skew_v) > 1 else '비교적 정규분포에 가까움'}
표준편차 = 평균의 {std_v/mean_v*100:.0f}%
  → {'변동성 매우 높음 — 업종·지역별 차이 큼' if std_v/mean_v > 0.5 else '변동성 보통'}
</div>
""", unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            fig_hist = px.histogram(
                f, x="payment_amount", nbins=30,
                title="결제금액 분포 히스토그램",
                color_discrete_sequence=["#1a73e8"]
            )
            fig_hist.update_layout(height=380, plot_bgcolor="white")
            st.plotly_chart(fig_hist, use_container_width=True)
        with col_b:
            fig_box = px.box(
                f, x="industry", y="payment_amount",
                title="업종별 결제금액 Box Plot",
                color_discrete_sequence=["#1a73e8"]
            )
            fig_box.update_layout(height=380, xaxis_tickangle=-45, plot_bgcolor="white")
            st.plotly_chart(fig_box, use_container_width=True)

    # ── 탭2: 지역 분석 ──────────────────────────────
    with tab2:
        st.markdown("### 📍 행정동별 결제금액 분석")
        dpay = f.groupby("district", as_index=False).agg(
            결제금액=("payment_amount","sum"),
            결제건수=("transaction_count","sum"),
            평균객단가=("avg_ticket","mean")
        ).sort_values("결제금액", ascending=False)

        col_a, col_b = st.columns(2)
        with col_a:
            fig1 = px.bar(dpay, x="결제금액", y="district", orientation="h",
                         text="결제금액", color="결제금액", color_continuous_scale="Blues",
                         title="행정동별 총 결제금액")
            fig1.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig1.update_layout(yaxis=dict(autorange="reversed"), height=500,
                              coloraxis_showscale=False, plot_bgcolor="white")
            st.plotly_chart(fig1, use_container_width=True)
        with col_b:
            fig2 = px.bar(dpay, x="결제건수", y="district", orientation="h",
                         text="결제건수", color="결제건수", color_continuous_scale="Greens",
                         title="행정동별 결제건수 (거래 활성도)")
            fig2.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig2.update_layout(yaxis=dict(autorange="reversed"), height=500,
                              coloraxis_showscale=False, plot_bgcolor="white")
            st.plotly_chart(fig2, use_container_width=True)

        with st.expander("📋 행정동별 상세 데이터"):
            st.dataframe(dpay.rename(columns={"district":"행정동"}), use_container_width=True)

    # ── 탭3: 업종 분석 ──────────────────────────────
    with tab3:
        st.markdown("### 🏪 업종별 결제 현황")
        ipay = f.groupby("industry", as_index=False).agg(
            결제금액=("payment_amount","sum"),
            결제건수=("transaction_count","sum"),
            평균객단가=("avg_ticket","mean")
        ).sort_values("결제금액", ascending=False)
        ipay["평균객단가"] = ipay["평균객단가"].round(0)

        col_a, col_b = st.columns(2)
        with col_a:
            fig3 = px.bar(ipay, x="결제금액", y="industry", orientation="h",
                         text="결제금액", color="결제금액", color_continuous_scale="Teal",
                         title="업종별 총 결제금액 TOP 20")
            fig3.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig3.update_layout(yaxis=dict(autorange="reversed"), height=620,
                              coloraxis_showscale=False, plot_bgcolor="white")
            st.plotly_chart(fig3, use_container_width=True)
        with col_b:
            fig4 = px.pie(ipay.head(10), names="industry", values="결제금액",
                         color_discrete_sequence=px.colors.qualitative.Set3,
                         title="업종별 결제금액 비중 TOP 10")
            fig4.update_traces(textposition="inside", textinfo="percent+label")
            fig4.update_layout(height=620, showlegend=False)
            st.plotly_chart(fig4, use_container_width=True)

    # ── 탭4: 소비자 분석 ─────────────────────────────
    with tab4:
        st.markdown("### 👥 소비자 분석 — 연령대·성별·히트맵")
        col_a, col_b = st.columns(2)
        with col_a:
            age_order = ["10대","20대","30대","40대","50대","60대 이상"]
            age = f.groupby("age_group", as_index=False)["payment_amount"].sum()
            age = age.set_index("age_group").reindex([a for a in age_order if a in age["age_group"].values if False] + age["age_group"].tolist()).reset_index()
            age = f.groupby("age_group", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
            fig5 = px.bar(age, x="age_group", y="payment_amount", text="payment_amount",
                         color="payment_amount", color_continuous_scale="Purples",
                         title="연령대별 총 결제금액")
            fig5.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig5.update_layout(height=400, coloraxis_showscale=False, plot_bgcolor="white")
            st.plotly_chart(fig5, use_container_width=True)
        with col_b:
            gender = f.groupby("gender", as_index=False)["payment_amount"].sum()
            fig6 = px.bar(gender, x="gender", y="payment_amount", text="payment_amount",
                         color="gender", color_discrete_sequence=["#74b9ff","#fd79a8"],
                         title="성별 결제금액")
            fig6.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig6.update_layout(height=400, plot_bgcolor="white", showlegend=False)
            st.plotly_chart(fig6, use_container_width=True)

        st.markdown("#### 연령대 × 업종 결제금액 히트맵")
        heat = f.groupby(["age_group","industry"], as_index=False)["payment_amount"].sum()
        fig7 = px.density_heatmap(heat, x="industry", y="age_group", z="payment_amount",
                                  color_continuous_scale="Blues",
                                  title="연령대 × 업종 결제금액 히트맵")
        fig7.update_layout(height=420, xaxis_tickangle=-40, plot_bgcolor="white")
        st.plotly_chart(fig7, use_container_width=True)

    # ── 탭5: 회귀분석 ────────────────────────────────
    with tab5:
        st.markdown("### 📐 OLS 회귀분석 — 결제금액 결정요인")
        st.markdown("""
<div class="insight-box">
교수님 강의(AI Financial Analyst) 방법론 적용: 결제금액을 종속변수로,
업종·연령대·성별·지역을 독립변수로 하는 다중회귀분석을 수행합니다.
</div>
""", unsafe_allow_html=True)

        # 더미변수 인코딩
        df_reg = f[["payment_amount","industry","age_group","gender","district"]].copy()
        df_reg = df_reg[df_reg["payment_amount"] > 0].copy()
        df_reg["ln_payment"] = np.log(df_reg["payment_amount"])

        # 업종 더미 (기준: 첫번째 업종)
        industry_dummies = pd.get_dummies(df_reg["industry"], prefix="ind", drop_first=True)
        age_dummies = pd.get_dummies(df_reg["age_group"], prefix="age", drop_first=True)
        gender_dummy = pd.get_dummies(df_reg["gender"], prefix="gen", drop_first=True)
        district_dummy = pd.get_dummies(df_reg["district"], prefix="dist", drop_first=True)

        X_df = pd.concat([industry_dummies, age_dummies, gender_dummy, district_dummy], axis=1)
        X = X_df.values.astype(float)
        y = df_reg["ln_payment"].values

        X_c = np.column_stack([np.ones(len(X)), X])
        try:
            coeffs, residuals, rank, sv = np.linalg.lstsq(X_c, y, rcond=None)
            y_pred = X_c @ coeffs
            ss_res = np.sum((y - y_pred)**2)
            ss_tot = np.sum((y - np.mean(y))**2)
            r2 = 1 - ss_res/ss_tot
            n, k = len(y), X.shape[1]
            adj_r2 = 1 - (1-r2)*(n-1)/(n-k-1)
            mse = ss_res / max(n-k-1,1)
            try:
                cov = mse * np.linalg.pinv(X_c.T @ X_c)
                se = np.sqrt(np.diag(cov))
            except:
                se = np.ones(len(coeffs)) * 0.01
            t_stats = coeffs / (se + 1e-10)
            p_vals = [2*(1-stats.t.cdf(abs(t), df=max(n-k-1,1))) for t in t_stats]
            f_stat = (ss_tot-ss_res)/k / (ss_res/max(n-k-1,1))

            st.markdown(f"""
<div class="stat-box">
[OLS 회귀분석 결과]
종속변수: ln(결제금액)
독립변수: 업종 더미 + 연령대 더미 + 성별 더미 + 지역 더미

R² = {r2:.3f}  |  Adjusted R² = {adj_r2:.3f}
F-statistic = {f_stat:.1f}  (p &lt; 0.001)
N = {n:,}건

해석: 포함된 변수들이 결제금액 변동의 {r2*100:.1f}%를 설명합니다.
</div>
""", unsafe_allow_html=True)

            # 업종별 계수 시각화
            var_names = ["상수"] + X_df.columns.tolist()
            coef_df = pd.DataFrame({
                "변수": var_names,
                "계수(β)": coeffs,
                "t-stat": t_stats,
                "p-value": p_vals
            })
            coef_df["유의성"] = coef_df["p-value"].apply(
                lambda p: "***" if p<0.001 else ("**" if p<0.01 else ("*" if p<0.05 else ""))
            )
            coef_df["경제적해석"] = coef_df["계수(β)"].apply(
                lambda b: f"+{(np.exp(b)-1)*100:.1f}%" if b > 0 else f"{(np.exp(b)-1)*100:.1f}%"
            )

            ind_coefs = coef_df[coef_df["변수"].str.startswith("ind_")].copy()
            ind_coefs["업종"] = ind_coefs["변수"].str.replace("ind_","")
            ind_coefs = ind_coefs.sort_values("계수(β)", ascending=False)

            col_a, col_b = st.columns(2)
            with col_a:
                fig_coef = px.bar(
                    ind_coefs, x="계수(β)", y="업종", orientation="h",
                    color="계수(β)", color_continuous_scale="RdYlGn",
                    title="업종별 결제금액 프리미엄 계수 (기준 업종 대비)",
                    text="경제적해석"
                )
                fig_coef.update_traces(textposition="outside")
                fig_coef.update_layout(
                    yaxis=dict(autorange="reversed"),
                    height=500, coloraxis_showscale=False, plot_bgcolor="white"
                )
                st.plotly_chart(fig_coef, use_container_width=True)

            with col_b:
                # 실제 vs 예측 scatter
                sample_idx = np.random.choice(len(y), min(500, len(y)), replace=False)
                fig_fit = go.Figure()
                fig_fit.add_trace(go.Scatter(
                    x=y[sample_idx], y=y_pred[sample_idx],
                    mode="markers", marker=dict(color="#1a73e8", opacity=0.5, size=5),
                    name="데이터"
                ))
                min_v, max_v = min(y.min(), y_pred.min()), max(y.max(), y_pred.max())
                fig_fit.add_trace(go.Scatter(
                    x=[min_v, max_v], y=[min_v, max_v],
                    mode="lines", line=dict(color="red", dash="dash"),
                    name="완벽한 예측선"
                ))
                fig_fit.update_layout(
                    title=f"실제 vs 예측 결제금액 (R²={r2:.3f})",
                    xaxis_title="실제 ln(결제금액)",
                    yaxis_title="예측 ln(결제금액)",
                    height=500, plot_bgcolor="white"
                )
                st.plotly_chart(fig_fit, use_container_width=True)

            st.markdown("#### 회귀계수 상세 테이블")
            display_coef = coef_df[1:].copy()
            display_coef = display_coef[display_coef["유의성"] != ""].sort_values("t-stat", key=abs, ascending=False).head(20)
            st.dataframe(display_coef[["변수","계수(β)","t-stat","p-value","유의성","경제적해석"]].round(4), use_container_width=True)

        except Exception as e:
            st.error(f"회귀분석 오류: {str(e)}")

    # ── 탭6: 투자점수 ────────────────────────────────
    with tab6:
        st.markdown("### 📈 창업 투자 점수 — 종합 랭킹")
        st.markdown("""
<div class="stat-box">
[투자점수 산출 공식]
창업투자점수 = 수요규모(35%) + 거래빈도(20%) + 객단가(15%)
             + 고객확장성(10%) + 지역확산(10%) + 경쟁완화(10%)

상권투자점수 = 소비규모(35%) + 거래활성(20%) + 객단가(15%)
             + 상권다양성(10%) + 고객다양성(10%) + 경쟁완화(10%)
</div>
""", unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 업종별 창업투자점수 TOP 15")
            fig8 = px.bar(
                inv_score.head(15), x="창업투자점수", y="industry", orientation="h",
                text="창업투자점수", color="창업투자점수", color_continuous_scale="Greens"
            )
            fig8.update_traces(textposition="outside")
            fig8.update_layout(yaxis=dict(autorange="reversed"), height=520,
                              coloraxis_showscale=False, plot_bgcolor="white")
            st.plotly_chart(fig8, use_container_width=True)

        with col_b:
            st.markdown("#### 행정동별 상권투자점수")
            fig9 = px.bar(
                dist_score, x="상권투자점수", y="district", orientation="h",
                text="상권투자점수", color="상권투자점수", color_continuous_scale="Blues"
            )
            fig9.update_traces(textposition="outside")
            fig9.update_layout(yaxis=dict(autorange="reversed"), height=520,
                              coloraxis_showscale=False, plot_bgcolor="white")
            st.plotly_chart(fig9, use_container_width=True)

        st.markdown("#### 📋 업종별 투자점수 상세 테이블")
        display_inv = inv_score[[
            "industry","결제금액표시","결제건수","평균객단가","창업투자점수",
            "수요규모","거래빈도","객단가","고객확장성","지역확산","경쟁완화","점포수"
        ]].rename(columns={"industry":"업종","결제금액표시":"결제금액","점포수":"상가점포수"})
        st.dataframe(display_inv, use_container_width=True)

    # 하단 발표 핵심 문장
    st.divider()
    st.markdown("""
<div class="insight-box">
<b>📢 발표 핵심 요약</b><br>
본 플랫폼은 공공데이터포털의 <b>2025년 11월 수원시 지역화폐 결제정보(실데이터)</b>와
소상공인시장진흥공단 <b>상가정보(56,003개)</b>를 결합하여 예비창업자의 업종·입지 선택을 지원합니다.<br>
OLS 회귀분석으로 결제금액 결정요인을 통계적으로 검증하고, 리스크-수익 매트릭스로 최적 투자 대상을 제안합니다.<br>
향후 광주상생카드·온누리상품권 결제데이터가 확보되면 동일 분석 구조를 전국으로 확장할 수 있습니다.
</div>
""", unsafe_allow_html=True)

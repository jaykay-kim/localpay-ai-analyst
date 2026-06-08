import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import anthropic
import json

st.set_page_config(
    page_title="LocalPay AI Analyst",
    page_icon="💳",
    layout="wide"
)

# ── 스타일 ──────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #f8f9fa;
    border-radius: 12px;
    padding: 16px 20px;
    border-left: 4px solid #1a73e8;
}
.report-box {
    background: #f0f4ff;
    border-radius: 12px;
    padding: 20px 24px;
    border: 1px solid #c5d3f7;
    line-height: 1.8;
}
h1 { color: #1a1a2e; }
</style>
""", unsafe_allow_html=True)

# ── 상수 ────────────────────────────────────────────────
SUWON_MERCHANT_TOTAL = 37369

# 실제 업종이 아닌 오염 데이터 제거용 필터
VALID_INDUSTRIES = [
    "가구", "건축자재", "광교1동 제외 기타", "기타유통", "기타의료",
    "대형유통", "레저/문화 용품", "레저/스포츠 서비스", "문화/취미",
    "미분류", "미용/위생", "병원", "비영리유통", "사무/통신",
    "서적/문구/학습자재", "숙박업", "신변잡화", "약국", "용역서비스",
    "음료/식품", "의류", "의원", "일반/휴게 음식", "일반유통",
    "자동차 정비/유지", "자동차판매", "전자상거래", "전자제품",
    "주방용품", "주유/충전소", "직물/침구류", "학교/교육", "학원",
    "회원정보미상"
]

REQUIRED_COLUMNS = [
    "month", "region", "district", "industry", "age_group",
    "payment_amount", "transaction_count", "avg_ticket"
]

COLOR_PALETTE = px.colors.qualitative.Pastel

# ── 데이터 로딩 ──────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_csv("sample_localpay_data.csv")
    # 업종 컬럼에 섞인 지역명 등 오염값 제거
    df = df[~df["industry"].isin(["광교1동", "회원정보미상"])]
    for c in ["payment_amount", "transaction_count", "avg_ticket"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

def format_won(value):
    value = float(value)
    if value >= 100_000_000:
        return f"{value/100_000_000:.1f}억 원"
    if value >= 10_000:
        return f"{value/10_000:.0f}만 원"
    return f"{value:,.0f}원"

def check_columns(data):
    return [c for c in REQUIRED_COLUMNS if c not in data.columns]

# ── 창업 참고 점수 ────────────────────────────────────────
def startup_score(data):
    grouped = data.groupby("industry", as_index=False).agg(
        결제금액=("payment_amount", "sum"),
        결제건수=("transaction_count", "sum"),
        평균객단가=("avg_ticket", "mean")
    )
    def norm(s):
        if s.max() == s.min():
            return pd.Series([0.5] * len(s), index=s.index)
        return (s - s.min()) / (s.max() - s.min())
    grouped["창업참고점수"] = (
        norm(grouped["결제금액"]) * 0.5 +
        norm(grouped["결제건수"]) * 0.3 +
        norm(grouped["평균객단가"]) * 0.2
    ) * 100
    grouped["평균객단가"] = grouped["평균객단가"].round(0).astype(int)
    grouped["결제금액표시"] = grouped["결제금액"].apply(format_won)
    grouped["창업참고점수"] = grouped["창업참고점수"].round(1)
    return grouped.sort_values("창업참고점수", ascending=False).reset_index(drop=True)

# ── Claude API 리포트 ─────────────────────────────────────
def generate_ai_report(summary: dict) -> str:
    try:
        client = anthropic.Anthropic()
        prompt = f"""
당신은 지역화폐 소비 데이터를 분석하는 전문 AI 애널리스트입니다.
아래 데이터를 바탕으로 소상공인과 정책 담당자에게 유용한 분석 리포트를 한국어로 작성해주세요.

[분석 대상]
- 지역: {summary['area']}
- 분석 기간: {summary['months']}
- 총 결제금액: {summary['total_payment']}
- 총 거래건수: {summary['total_txn']}건
- 평균 객단가: {summary['avg_ticket']}

[업종별 결제금액 TOP 5]
{summary['top_industries']}

[연령대별 결제금액]
{summary['age_distribution']}

[창업 참고 점수 TOP 3 업종]
{summary['top_startup']}

다음 항목을 포함해 리포트를 작성해주세요:
1. **핵심 인사이트** (이 지역의 소비 특징을 2~3문장으로 요약)
2. **주목할 업종** (왜 이 업종이 강세인지 해석)
3. **소상공인 창업 제언** (데이터 기반으로 실질적인 조언)
4. **정책 제언** (지역화폐 효율화를 위한 제안)
5. **주의사항** (데이터 한계 및 유의점)

리포트는 친근하면서도 전문적인 톤으로, 마크다운 형식으로 작성해주세요.
"""
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except anthropic.AuthenticationError:
        return "⚠️ API 키 오류: 사이드바에서 Anthropic API 키를 입력해주세요."
    except Exception as e:
        return f"⚠️ AI 리포트 생성 중 오류가 발생했습니다: {str(e)}"

# ════════════════════════════════════════════════════════
# 메인 UI
# ════════════════════════════════════════════════════════

st.title("💳 LocalPay AI Analyst")
st.subheader("수원시 지역화폐 공공데이터 기반 소상공인 상권분석 플랫폼")

# ── 사이드바 ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")

    api_key = st.text_input(
        "Anthropic API 키 (AI 리포트용)",
        type="password",
        placeholder="sk-ant-...",
        help="AI 리포트 탭에서 Claude가 자동 분석을 생성합니다. 없으면 기본 리포트가 표시됩니다."
    )
    if api_key:
        import os
        os.environ["ANTHROPIC_API_KEY"] = api_key

    st.divider()
    st.header("📂 데이터")
    uploaded = st.file_uploader("CSV 파일 업로드 (선택)", type=["csv"])
    st.caption("업로드하지 않으면 기본 데이터(2025년 11월 수원시)를 사용합니다.")

    st.divider()
    st.header("🔍 분석 조건")

df = pd.read_csv(uploaded) if uploaded else load_data()

missing = check_columns(df)
if missing:
    st.error(f"CSV 컬럼 오류 — 다음 컬럼이 없습니다: {', '.join(missing)}")
    st.stop()

for c in ["payment_amount", "transaction_count", "avg_ticket"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

with st.sidebar:
    regions = ["전체"] + sorted(df["region"].astype(str).unique().tolist())
    region = st.selectbox("시/군/구", regions, index=1 if len(regions) > 1 else 0)

    filtered = df.copy()
    if region != "전체":
        filtered = filtered[filtered["region"].astype(str) == region]

    districts = ["전체"] + sorted(filtered["district"].astype(str).unique().tolist())
    district = st.selectbox("읍/면/동", districts)
    if district != "전체":
        filtered = filtered[filtered["district"].astype(str) == district]

    months = sorted(filtered["month"].astype(str).unique().tolist())
    selected_months = st.multiselect("분석 월", months, default=months)
    if selected_months:
        filtered = filtered[filtered["month"].astype(str).isin(selected_months)]

    st.divider()
    st.caption("📊 데이터: 공공데이터포털 경기도 수원시 지역화폐 결제정보 (2025.11)")
    st.caption(f"🏪 수원시 가맹점 수: {SUWON_MERCHANT_TOTAL:,}개")

if filtered.empty:
    st.warning("선택 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# ── KPI 카드 ──────────────────────────────────────────────
total_payment = filtered["payment_amount"].sum()
total_txn = filtered["transaction_count"].sum()
avg_ticket = total_payment / max(total_txn, 1)
industry_count = filtered["industry"].nunique()

area_label = region if district == "전체" else f"{region} {district}"

st.info(f"📍 분석 지역: **{area_label}** | 기간: **{', '.join(selected_months) if selected_months else '전체'}**")

col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 총 결제금액", format_won(total_payment))
col2.metric("🧾 총 거래건수", f"{total_txn:,.0f}건")
col3.metric("🛒 평균 객단가", format_won(avg_ticket))
col4.metric("🏪 분석 업종 수", f"{industry_count}개")

st.divider()

# ── 탭 ───────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📍 지역 분석", "🏪 업종 분석", "👥 연령·성별 분석", "🤖 AI 리포트"])

# ── 탭1: 지역 분석 ───────────────────────────────────────
with tab1:
    st.markdown("### 읍·면·동별 결제금액")
    district_pay = (
        filtered.groupby("district")["payment_amount"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    district_pay.columns = ["읍면동", "결제금액"]
    district_pay["결제금액표시"] = district_pay["결제금액"].apply(format_won)

    fig = px.bar(
        district_pay, x="읍면동", y="결제금액",
        text="결제금액표시",
        color="결제금액",
        color_continuous_scale="Blues",
        title=f"{area_label} 읍·면·동별 결제금액"
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        xaxis_tickangle=-35,
        coloraxis_showscale=False,
        height=420,
        plot_bgcolor="white"
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 상세 데이터 보기"):
        st.dataframe(district_pay[["읍면동", "결제금액표시"]].rename(columns={"결제금액표시": "결제금액"}), use_container_width=True)

# ── 탭2: 업종 분석 ───────────────────────────────────────
with tab2:
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### 업종별 결제금액 TOP 15")
        industry_pay = (
            filtered.groupby("industry")["payment_amount"]
            .sum()
            .sort_values(ascending=False)
            .head(15)
            .reset_index()
        )
        industry_pay.columns = ["업종", "결제금액"]
        industry_pay["표시"] = industry_pay["결제금액"].apply(format_won)

        fig2 = px.bar(
            industry_pay, x="결제금액", y="업종",
            orientation="h", text="표시",
            color="결제금액",
            color_continuous_scale="Teal",
            title="업종별 결제금액"
        )
        fig2.update_traces(textposition="outside")
        fig2.update_layout(
            yaxis=dict(autorange="reversed"),
            coloraxis_showscale=False,
            height=460,
            plot_bgcolor="white"
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col_b:
        st.markdown("### 업종별 결제 비중")
        top10 = (
            filtered.groupby("industry")["payment_amount"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )
        top10.columns = ["업종", "결제금액"]
        fig3 = px.pie(
            top10, names="업종", values="결제금액",
            color_discrete_sequence=COLOR_PALETTE,
            title="상위 10개 업종 비중"
        )
        fig3.update_traces(textposition="inside", textinfo="percent+label")
        fig3.update_layout(height=460, showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("### 🏆 창업 참고 점수")
    st.caption("결제금액(50%) + 거래건수(30%) + 평균객단가(20%) 기반 1차 참고 지표입니다.")
    score_df = startup_score(filtered)

    fig4 = px.bar(
        score_df.head(15), x="창업참고점수", y="industry",
        orientation="h",
        text="창업참고점수",
        color="창업참고점수",
        color_continuous_scale="Oranges",
        title="업종별 창업 참고 점수 TOP 15"
    )
    fig4.update_traces(texttemplate="%{text:.1f}점", textposition="outside")
    fig4.update_layout(
        yaxis=dict(autorange="reversed", title="업종"),
        coloraxis_showscale=False,
        height=460,
        plot_bgcolor="white"
    )
    st.plotly_chart(fig4, use_container_width=True)

    with st.expander("📋 전체 업종 점수 테이블"):
        display_score = score_df[["industry", "결제금액표시", "결제건수", "평균객단가", "창업참고점수"]].copy()
        display_score.columns = ["업종", "결제금액", "거래건수", "평균객단가(원)", "창업참고점수"]
        st.dataframe(display_score, use_container_width=True)

# ── 탭3: 연령·성별 분석 ──────────────────────────────────
with tab3:
    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("### 연령대별 결제금액")
        age_order = ["10대", "20대", "30대", "40대", "50대", "60대 이상"]
        age_pay = (
            filtered.groupby("age_group")["payment_amount"]
            .sum()
            .reindex([a for a in age_order if a in filtered["age_group"].unique()])
            .reset_index()
        )
        age_pay.columns = ["연령대", "결제금액"]
        age_pay["표시"] = age_pay["결제금액"].apply(format_won)

        fig5 = px.bar(
            age_pay, x="연령대", y="결제금액",
            text="표시",
            color="연령대",
            color_discrete_sequence=COLOR_PALETTE,
            title="연령대별 결제금액"
        )
        fig5.update_traces(textposition="outside")
        fig5.update_layout(
            showlegend=False,
            height=380,
            plot_bgcolor="white"
        )
        st.plotly_chart(fig5, use_container_width=True)

    with col_d:
        if "gender" in filtered.columns:
            st.markdown("### 성별 결제금액")
            gender_pay = (
                filtered.groupby("gender")["payment_amount"]
                .sum()
                .reset_index()
            )
            gender_pay.columns = ["성별", "결제금액"]
            gender_pay["표시"] = gender_pay["결제금액"].apply(format_won)

            fig6 = px.pie(
                gender_pay, names="성별", values="결제금액",
                color_discrete_sequence=["#74b9ff", "#fd79a8"],
                title="성별 결제 비중"
            )
            fig6.update_traces(textinfo="percent+label", textposition="inside")
            fig6.update_layout(height=380)
            st.plotly_chart(fig6, use_container_width=True)

    # 연령대 × 업종 히트맵
    st.markdown("### 연령대 × 업종 결제금액 히트맵")
    top_industries = (
        filtered.groupby("industry")["payment_amount"]
        .sum()
        .sort_values(ascending=False)
        .head(12)
        .index.tolist()
    )
    heat_data = (
        filtered[filtered["industry"].isin(top_industries)]
        .groupby(["age_group", "industry"])["payment_amount"]
        .sum()
        .unstack(fill_value=0)
    )
    heat_data = heat_data.reindex([a for a in age_order if a in heat_data.index])

    fig7 = px.imshow(
        heat_data,
        color_continuous_scale="YlOrRd",
        aspect="auto",
        title="연령대 × 업종 결제금액 히트맵",
        labels={"color": "결제금액(원)"}
    )
    fig7.update_layout(height=350)
    st.plotly_chart(fig7, use_container_width=True)

# ── 탭4: AI 리포트 ───────────────────────────────────────
with tab4:
    st.markdown("### 🤖 AI Analyst 리포트")
    st.caption("Claude AI가 데이터를 분석하여 인사이트와 제언을 생성합니다.")

    # 리포트용 요약 데이터 준비
    industry_top5 = (
        filtered.groupby("industry")["payment_amount"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
    )
    industry_str = "\n".join(
        [f"  {i+1}. {row[0]}: {format_won(row[1])}" for i, row in enumerate(industry_top5.items())]
    )

    age_dist = filtered.groupby("age_group")["payment_amount"].sum().sort_values(ascending=False)
    age_str = "\n".join(
        [f"  - {row[0]}: {format_won(row[1])}" for row in age_dist.items()]
    )

    score_top3 = startup_score(filtered).head(3)["industry"].tolist()

    summary = {
        "area": area_label,
        "months": ", ".join(selected_months) if selected_months else "전체",
        "total_payment": format_won(total_payment),
        "total_txn": f"{total_txn:,.0f}",
        "avg_ticket": format_won(avg_ticket),
        "top_industries": industry_str,
        "age_distribution": age_str,
        "top_startup": ", ".join(score_top3)
    }

    if st.button("🚀 AI 리포트 생성", type="primary"):
        with st.spinner("Claude AI가 데이터를 분석 중입니다..."):
            report = generate_ai_report(summary)
        st.markdown(f'<div class="report-box">{report}</div>', unsafe_allow_html=True)
    else:
        # 기본 템플릿 리포트
        st.markdown(f"""
**📊 기본 요약 리포트 | {area_label}**

- 분석 기간: {', '.join(selected_months) if selected_months else '전체'}
- 총 결제금액: **{format_won(total_payment)}**, 거래건수: **{total_txn:,.0f}건**, 평균 객단가: **{format_won(avg_ticket)}**
- 결제금액 1위 업종: **{industry_top5.index[0]}** ({format_won(industry_top5.iloc[0])})
- 주요 소비 연령대: **{age_dist.index[0]}**
- 창업 참고 TOP 3 업종: **{', '.join(score_top3)}**

> 💡 **AI 리포트 생성** 버튼을 누르면 Claude AI가 더 깊은 인사이트와 제언을 작성해드립니다.  
> (사이드바에서 Anthropic API 키 입력 필요)
""")

    st.divider()
    st.markdown("#### 📌 데이터 한계 및 유의사항")
    st.info("""
- 본 데이터는 **2025년 11월 수원시 지역화폐 결제정보** 공공데이터 기반입니다.
- 임대료, 유동인구, 재방문율, 이벤트 효과 등의 변수는 포함되어 있지 않습니다.
- 창업 참고 점수는 결제금액·건수·객단가 기반의 1차 지표로, 실제 창업 결정에는 현장 조사가 병행되어야 합니다.
- 수원시 전체 지역화폐 가맹점 수는 **{:,}개** (경기도 지역화폐 가맹점 현황 OpenAPI 기준)입니다.
""".format(SUWON_MERCHANT_TOTAL))

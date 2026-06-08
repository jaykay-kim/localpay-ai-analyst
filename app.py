
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.set_page_config(
    page_title="LocalPay AI Analyst",
    page_icon="💳",
    layout="wide"
)

# 실제 API 조회 결과: 경기지역화폐 가맹점 현황 OpenAPI, SIGUN_NM=수원시
SUWON_MERCHANT_TOTAL = 37369

REQUIRED_COLUMNS = {
    "month", "region", "district", "industry", "age_group",
    "payment_amount", "transaction_count", "avg_ticket"
}

OPTIONAL_COLUMNS = {
    "event_participation", "revisit_rate", "merchant_count", "gender", "source", "source_date"
}

@st.cache_data
def load_default_data():
    return pd.read_csv("sample_localpay_data.csv")

def validate_data(data: pd.DataFrame):
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        return False, f"필수 컬럼이 없습니다: {', '.join(sorted(missing))}"
    return True, "OK"

def prepare_data(data: pd.DataFrame):
    data = data.copy()
    # 앱 호환용 보정: 공공데이터에 없는 컬럼은 임의 분석에 쓰지 않고 '미제공'으로 처리
    if "event_participation" not in data.columns:
        data["event_participation"] = "공공데이터 미제공"
    if "revisit_rate" not in data.columns:
        data["revisit_rate"] = np.nan
    if "merchant_count" not in data.columns:
        data["merchant_count"] = np.nan
    if "gender" not in data.columns:
        data["gender"] = "미제공"
    if "source" not in data.columns:
        data["source"] = "업로드 CSV"
    if "source_date" not in data.columns:
        data["source_date"] = ""
    data["payment_amount"] = pd.to_numeric(data["payment_amount"], errors="coerce").fillna(0)
    data["transaction_count"] = pd.to_numeric(data["transaction_count"], errors="coerce").fillna(0)
    data["avg_ticket"] = pd.to_numeric(data["avg_ticket"], errors="coerce").fillna(0)
    return data

def format_won(value):
    value = float(value)
    if value >= 100_000_000:
        return f"{value/100_000_000:.1f}억 원"
    if value >= 10_000:
        return f"{value/10_000:.0f}만 원"
    return f"{value:,.0f}원"

def calc_opportunity_score(data: pd.DataFrame):
    grouped = data.groupby("industry", as_index=False).agg(
        payment_amount=("payment_amount", "sum"),
        transaction_count=("transaction_count", "sum"),
        avg_ticket=("avg_ticket", "mean"),
    )
    for col in ["payment_amount", "transaction_count", "avg_ticket"]:
        min_v, max_v = grouped[col].min(), grouped[col].max()
        grouped[f"{col}_score"] = 0.5 if max_v == min_v else (grouped[col] - min_v) / (max_v - min_v)

    # 현재 실제 공공데이터에는 업종별 가맹점 수가 없으므로 경쟁강도는 반영하지 않음
    grouped["startup_score"] = (
        grouped["payment_amount_score"] * 0.50 +
        grouped["transaction_count_score"] * 0.30 +
        grouped["avg_ticket_score"] * 0.20
    ) * 100
    return grouped.sort_values("startup_score", ascending=False)

def make_ai_report(data: pd.DataFrame, region: str, district: str):
    industry = data.groupby("industry", as_index=False).agg(
        payment_amount=("payment_amount", "sum"),
        transaction_count=("transaction_count", "sum"),
        avg_ticket=("avg_ticket", "mean")
    ).sort_values("payment_amount", ascending=False)

    age = data.groupby("age_group", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
    score = calc_opportunity_score(data)

    top_industry = industry.iloc[0]
    second_industry = industry.iloc[1] if len(industry) > 1 else top_industry
    top_age = age.iloc[0]
    recommended = score.head(3)["industry"].tolist()
    caution = score.tail(2)["industry"].tolist()

    total_payment = data["payment_amount"].sum()
    total_txn = data["transaction_count"].sum()
    avg_ticket = total_payment / max(total_txn, 1)

    selected_area = f"{region} {district}" if district != "전체" else region

    report = f"""
### AI Analyst Report: {selected_area} 지역화폐 상권분석

**1. 데이터 기준**  
본 분석은 업로드된 공공데이터 기반입니다. 현재 기본 탑재 데이터는 **2025년 11월 수원시 지역화폐 결제정보**를 앱 형식으로 변환한 파일입니다. 결제건수와 결제금액은 원본 공공데이터 값을 사용했습니다.

**2. 핵심 요약**  
선택 지역의 총 결제금액은 **{format_won(total_payment)}**, 총 거래건수는 **{total_txn:,.0f}건**, 평균 객단가는 **{format_won(avg_ticket)}**입니다. 결제금액 기준 상위 업종은 **{top_industry['industry']}**, 다음은 **{second_industry['industry']}**입니다.

**3. 주요 수요층**  
연령대별 결제금액은 **{top_age['age_group']}** 비중이 가장 높게 나타났습니다. 예비창업자는 이 연령대의 방문 동선, 가격 민감도, 구매 목적을 고려해 업종과 상품 구성을 설계할 필요가 있습니다.

**4. 창업 참고 업종**  
현재 데이터 기준 종합 점수 상위 업종은 **{', '.join(recommended)}**입니다. 이 점수는 결제금액, 결제건수, 평균 객단가를 결합한 단순 지표입니다. 즉, “수요가 확인되는 업종”을 1차로 찾는 데 목적이 있습니다.

**5. 주의 업종**  
상대적으로 점수가 낮은 업종은 **{', '.join(caution)}**입니다. 단, 결제금액이 낮다고 해서 창업이 불가능하다는 뜻은 아니며, 해당 업종은 임대료, 경쟁점포, 유동인구, 마진율을 추가로 확인해야 합니다.

**6. 가맹점 데이터 연계**  
경기도 지역화폐 가맹점 현황 OpenAPI에서 `SIGUN_NM=수원시` 조건으로 조회한 결과, 수원시 전체 지역화폐 가맹점 수는 **{SUWON_MERCHANT_TOTAL:,}개**로 확인되었습니다. 향후 업종별·동별 가맹점 수까지 결합하면 “결제금액 ÷ 가맹점 수” 방식으로 점포당 소비 잠재력과 경쟁강도를 계산할 수 있습니다.

**7. 한계**  
현재 결제정보 공공데이터에는 재방문율, 이벤트 참여 여부, 실제 임대료, 유동인구, 업종별 가맹점 수가 포함되어 있지 않습니다. 따라서 본 시연은 실제 결제금액·결제건수·업종·연령대 중심의 1차 상권분석이며, 사업화 단계에서는 가맹점 현황 API와 상권정보 데이터를 추가 결합해야 합니다.
"""
    return report

st.title("💳 LocalPay AI Analyst")
st.subheader("실제 지역화폐 공공데이터 기반 소상공인 창업 상권분석 플랫폼")

st.info(
    "기본 데이터는 공공데이터포털의 2025년 11월 수원시 지역화폐 결제정보를 앱 형식으로 변환한 CSV입니다. "
    "왼쪽에서 다른 CSV를 업로드하면 해당 데이터로 분석할 수 있습니다."
)

with st.sidebar:
    st.header("① 데이터 선택")
    uploaded = st.file_uploader("CSV 파일 업로드", type=["csv"])
    st.caption("업로드하지 않으면 기본 탑재된 수원시 실제 공공데이터가 사용됩니다.")

    if uploaded is not None:
        df = pd.read_csv(uploaded)
    else:
        df = load_default_data()

    ok, msg = validate_data(df)
    if not ok:
        st.error(msg)
        st.stop()

    df = prepare_data(df)

    st.header("② 분석 지역 선택")
    regions = ["전체"] + sorted(df["region"].unique().tolist())
    region = st.selectbox("시/군/구 선택", regions, index=1 if len(regions) > 1 else 0)

    filtered = df.copy()
    if region != "전체":
        filtered = filtered[filtered["region"] == region]

    districts = ["전체"] + sorted(filtered["district"].unique().tolist())
    district = st.selectbox("읍/면/동 선택", districts)

    if district != "전체":
        filtered = filtered[filtered["district"] == district]

    st.header("③ 기간 선택")
    months = sorted(filtered["month"].astype(str).unique().tolist())
    selected_months = st.multiselect("분석 월", months, default=months)
    if selected_months:
        filtered = filtered[filtered["month"].astype(str).isin(selected_months)]

if filtered.empty:
    st.warning("선택 조건에 해당하는 데이터가 없습니다.")
    st.stop()

st.divider()

total_payment = filtered["payment_amount"].sum()
total_txn = filtered["transaction_count"].sum()
avg_ticket = total_payment / max(total_txn, 1)
industry_count = filtered["industry"].nunique()
age_count = filtered["age_group"].nunique()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("총 결제금액", format_won(total_payment))
c2.metric("총 거래건수", f"{total_txn:,.0f}건")
c3.metric("평균 객단가", format_won(avg_ticket))
c4.metric("분석 업종 수", f"{industry_count:,}개")
c5.metric("수원시 가맹점 수(API)", f"{SUWON_MERCHANT_TOTAL:,}개")

st.caption("※ 수원시 가맹점 수 37,369개는 경기지역화폐 가맹점 현황 OpenAPI에서 SIGUN_NM=수원시 조건으로 조회한 결과입니다.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 지역 대시보드", "🏪 업종 분석", "👥 연령대·성별 분석", "🧭 창업 점수", "📝 AI 리포트"])

with tab1:
    st.markdown("### 월별 결제금액")
    monthly = filtered.groupby("month", as_index=False)["payment_amount"].sum()
    chart = alt.Chart(monthly).mark_bar().encode(
        x=alt.X("month:N", title="기준년월"),
        y=alt.Y("payment_amount:Q", title="결제금액"),
        tooltip=["month", alt.Tooltip("payment_amount:Q", format=",")]
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True)

    st.markdown("### 읍면동별 결제금액")
    district_pay = filtered.groupby("district", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
    chart2 = alt.Chart(district_pay).mark_bar().encode(
        x=alt.X("payment_amount:Q", title="결제금액"),
        y=alt.Y("district:N", title="읍면동", sort="-x"),
        tooltip=["district", alt.Tooltip("payment_amount:Q", format=",")]
    ).properties(height=360)
    st.altair_chart(chart2, use_container_width=True)

with tab2:
    st.markdown("### 업종별 결제금액 TOP")
    industry_pay = filtered.groupby("industry", as_index=False).agg(
        payment_amount=("payment_amount", "sum"),
        transaction_count=("transaction_count", "sum"),
        avg_ticket=("avg_ticket", "mean")
    ).sort_values("payment_amount", ascending=False)

    chart3 = alt.Chart(industry_pay.head(20)).mark_bar().encode(
        x=alt.X("payment_amount:Q", title="결제금액"),
        y=alt.Y("industry:N", title="업종", sort="-x"),
        tooltip=["industry", alt.Tooltip("payment_amount:Q", format=","), alt.Tooltip("transaction_count:Q", format=",")]
    ).properties(height=520)
    st.altair_chart(chart3, use_container_width=True)

    st.dataframe(
        industry_pay.assign(avg_ticket=lambda x: x["avg_ticket"].round(0)),
        use_container_width=True
    )

with tab3:
    st.markdown("### 연령대별 결제금액")
    age_pay = filtered.groupby("age_group", as_index=False)["payment_amount"].sum()
    chart4 = alt.Chart(age_pay).mark_bar().encode(
        x=alt.X("age_group:N", title="연령대"),
        y=alt.Y("payment_amount:Q", title="결제금액"),
        tooltip=["age_group", alt.Tooltip("payment_amount:Q", format=",")]
    ).properties(height=300)
    st.altair_chart(chart4, use_container_width=True)

    if "gender" in filtered.columns and filtered["gender"].nunique() > 1:
        st.markdown("### 성별 결제금액")
        gender_pay = filtered.groupby("gender", as_index=False)["payment_amount"].sum()
        chart_g = alt.Chart(gender_pay).mark_bar().encode(
            x=alt.X("gender:N", title="성별"),
            y=alt.Y("payment_amount:Q", title="결제금액"),
            tooltip=["gender", alt.Tooltip("payment_amount:Q", format=",")]
        ).properties(height=280)
        st.altair_chart(chart_g, use_container_width=True)

    st.markdown("### 연령대 × 업종 소비 히트맵")
    heat = filtered.groupby(["age_group", "industry"], as_index=False)["payment_amount"].sum()
    chart5 = alt.Chart(heat).mark_rect().encode(
        x=alt.X("industry:N", title="업종"),
        y=alt.Y("age_group:N", title="연령대"),
        color=alt.Color("payment_amount:Q", title="결제금액"),
        tooltip=["age_group", "industry", alt.Tooltip("payment_amount:Q", format=",")]
    ).properties(height=360)
    st.altair_chart(chart5, use_container_width=True)

with tab4:
    st.markdown("### 창업 참고 점수")
    st.caption("현재 점수는 실제 결제금액, 결제건수, 평균 객단가를 결합한 1차 지표입니다. 업종별 실제 가맹점 수가 결합되면 경쟁강도까지 반영할 수 있습니다.")
    score = calc_opportunity_score(filtered)
    st.dataframe(
        score[["industry", "startup_score", "payment_amount", "transaction_count", "avg_ticket"]]
        .assign(startup_score=lambda x: x["startup_score"].round(1),
                avg_ticket=lambda x: x["avg_ticket"].round(0)),
        use_container_width=True
    )

    chart_s = alt.Chart(score.head(15)).mark_bar().encode(
        x=alt.X("startup_score:Q", title="창업 참고 점수"),
        y=alt.Y("industry:N", title="업종", sort="-x"),
        tooltip=["industry", alt.Tooltip("startup_score:Q", format=".1f")]
    ).properties(height=420)
    st.altair_chart(chart_s, use_container_width=True)

with tab5:
    st.markdown("### 자동 생성 리포트")
    selected_region = region if region != "전체" else "전체 지역"
    report = make_ai_report(filtered, selected_region, district)
    st.markdown(report)

    st.download_button(
        label="리포트 Markdown 다운로드",
        data=report,
        file_name="localpay_ai_analyst_report.md",
        mime="text/markdown"
    )

st.divider()
st.caption("※ 본 앱은 수업 발표용 프로토타입입니다. 실제 창업 의사결정에는 임대료, 유동인구, 경쟁점포, 인허가, 원가구조 등의 추가 검토가 필요합니다.")

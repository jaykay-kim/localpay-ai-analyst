
import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="LocalPay AI Analyst", page_icon="💳", layout="wide")

REQUIRED_COLUMNS = {
    "month", "region", "district", "industry", "age_group",
    "payment_amount", "transaction_count", "avg_ticket",
    "event_participation", "revisit_rate", "merchant_count"
}

@st.cache_data
def load_default_data():
    return pd.read_csv("sample_localpay_data.csv")

def validate_data(data: pd.DataFrame):
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        return False, f"필수 컬럼이 없습니다: {', '.join(sorted(missing))}"
    return True, "OK"

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
        revisit_rate=("revisit_rate", "mean"),
        merchant_count=("merchant_count", "mean")
    )
    for col in ["payment_amount", "transaction_count", "avg_ticket", "revisit_rate"]:
        min_v, max_v = grouped[col].min(), grouped[col].max()
        grouped[f"{col}_score"] = 0.5 if max_v == min_v else (grouped[col] - min_v) / (max_v - min_v)
    min_m, max_m = grouped["merchant_count"].min(), grouped["merchant_count"].max()
    grouped["competition_score"] = 0.5 if max_m == min_m else 1 - ((grouped["merchant_count"] - min_m) / (max_m - min_m))
    grouped["startup_score"] = (
        grouped["payment_amount_score"] * 0.35 +
        grouped["transaction_count_score"] * 0.25 +
        grouped["avg_ticket_score"] * 0.15 +
        grouped["revisit_rate_score"] * 0.15 +
        grouped["competition_score"] * 0.10
    ) * 100
    return grouped.sort_values("startup_score", ascending=False)

def make_ai_report(data: pd.DataFrame, region: str, district: str):
    industry = data.groupby("industry", as_index=False).agg(
        payment_amount=("payment_amount", "sum"),
        transaction_count=("transaction_count", "sum"),
        avg_ticket=("avg_ticket", "mean"),
        revisit_rate=("revisit_rate", "mean")
    ).sort_values("payment_amount", ascending=False)
    age = data.groupby("age_group", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
    event = data.groupby("event_participation", as_index=False).agg(
        payment_amount=("payment_amount", "sum"),
        transaction_count=("transaction_count", "sum")
    )
    score = calc_opportunity_score(data)

    top_industry = industry.iloc[0]
    second_industry = industry.iloc[1] if len(industry) > 1 else top_industry
    top_age = age.iloc[0]
    recommended = score.head(3)["industry"].tolist()
    caution = score.tail(2)["industry"].tolist()

    total_payment = data["payment_amount"].sum()
    total_txn = data["transaction_count"].sum()
    avg_ticket = total_payment / max(total_txn, 1)

    if set(event["event_participation"]) == {"참여", "미참여"}:
        e_map = event.set_index("event_participation")
        event_avg = e_map.loc["참여", "payment_amount"] / max(e_map.loc["참여", "transaction_count"], 1)
        non_event_avg = e_map.loc["미참여", "payment_amount"] / max(e_map.loc["미참여", "transaction_count"], 1)
        diff = (event_avg / max(non_event_avg, 1) - 1) * 100
        if diff >= 5:
            event_summary = f"이벤트 참여 거래의 평균 결제금액이 미참여 거래보다 약 {diff:.1f}% 높아, 캐시백·할인 정책이 소비 확대에 일정 부분 기여한 것으로 해석됩니다."
        else:
            event_summary = "이벤트 참여 거래와 미참여 거래의 평균 결제금액 차이는 크지 않아, 단순 할인보다 업종별 맞춤 혜택 설계가 필요합니다."
    else:
        event_summary = "이벤트 참여 데이터가 충분하지 않아 정책효과는 추가 데이터 확보 후 재분석이 필요합니다."

    selected_area = f"{region} {district}" if district != "전체" else region
    return f"""
### AI Analyst Report: {selected_area} 상권분석

**1. 핵심 요약**  
선택 지역의 지역화폐·온누리상품권형 샘플 결제 데이터 기준 총 결제금액은 **{format_won(total_payment)}**, 총 거래건수는 **{total_txn:,.0f}건**, 평균 객단가는 **{format_won(avg_ticket)}**입니다. 결제금액 기준 상위 업종은 **{top_industry['industry']}**, 다음은 **{second_industry['industry']}**입니다.

**2. 주요 수요층**  
연령대별 결제금액은 **{top_age['age_group']}** 비중이 가장 높게 나타났습니다. 따라서 이 지역에서 창업을 검토할 경우, 해당 연령대의 생활패턴과 방문 동선을 고려한 메뉴·가격·영업시간 설계가 중요합니다.

**3. 창업 유망 업종**  
종합 점수는 결제금액, 거래건수, 객단가, 재방문율, 경쟁강도 추정치를 합산해 계산했습니다. 현재 데이터 기준 추천 업종은 **{', '.join(recommended)}**입니다. 이 업종들은 정책화폐 기반 소비 수요가 확인되며, 반복 방문 가능성이 상대적으로 높습니다.

**4. 주의 업종**  
상대적으로 신중한 접근이 필요한 업종은 **{', '.join(caution)}**입니다. 단, 이 결과는 결제 데이터 중심의 1차 분석이므로 임대료, 유동인구, 배후세대, 경쟁점포 수를 추가로 확인해야 합니다.

**5. 정책·마케팅 인사이트**  
{event_summary} 특히 결제금액이 높은 업종에는 지역화폐 캐시백과 재방문 쿠폰을 연계하고, 저활성 업종에는 신규 고객 유입형 프로모션을 설계하는 것이 적절합니다.

**6. 한계**  
본 시연은 실제 온누리상품권 내부 원천데이터가 아닌 공개데이터 구조를 모사한 비식별 샘플 데이터 기반입니다. 실제 사업화 단계에서는 정부·지자체·운영기관의 데이터 제공, 개인정보 비식별 처리, 가맹점 단위 경쟁 데이터 보완이 필요합니다.
"""

st.title("💳 LocalPay AI Analyst")
st.subheader("지역화폐·온누리상품권 데이터 기반 소상공인 창업 상권분석 플랫폼")

st.markdown("""
이 시연 앱은 예비창업자와 소상공인이 특정 지역을 입력했을 때,  
**정책화폐 소비 흐름 → 업종별 매출 강도 → 연령대별 수요 → 창업 추천 업종 → AI 리포트**를 자동으로 확인하는 프로토타입입니다.
""")

with st.sidebar:
    st.header("① 데이터 선택")
    uploaded = st.file_uploader("CSV 파일 업로드", type=["csv"])
    st.caption("업로드하지 않으면 기본 샘플 데이터가 사용됩니다.")
    df = pd.read_csv(uploaded) if uploaded is not None else load_default_data()

    ok, msg = validate_data(df)
    if not ok:
        st.error(msg)
        st.stop()

    st.header("② 분석 지역 선택")
    regions = ["전체"] + sorted(df["region"].unique().tolist())
    region = st.selectbox("시/군/구 선택", regions, index=1)

    filtered = df.copy()
    if region != "전체":
        filtered = filtered[filtered["region"] == region]

    districts = ["전체"] + sorted(filtered["district"].unique().tolist())
    district = st.selectbox("읍/면/동 선택", districts)

    if district != "전체":
        filtered = filtered[filtered["district"] == district]

    st.header("③ 기간 선택")
    months = sorted(filtered["month"].unique().tolist())
    selected_months = st.multiselect("분석 월", months, default=months)
    if selected_months:
        filtered = filtered[filtered["month"].isin(selected_months)]

if filtered.empty:
    st.warning("선택 조건에 해당하는 데이터가 없습니다.")
    st.stop()

st.divider()

total_payment = filtered["payment_amount"].sum()
total_txn = filtered["transaction_count"].sum()
avg_ticket = total_payment / max(total_txn, 1)
revisit_rate = filtered["revisit_rate"].mean()
merchant_count = filtered["merchant_count"].sum()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("총 결제금액", format_won(total_payment))
c2.metric("총 거래건수", f"{total_txn:,.0f}건")
c3.metric("평균 객단가", format_won(avg_ticket))
c4.metric("평균 재방문율", f"{revisit_rate*100:.1f}%")
c5.metric("가맹점 수 추정", f"{merchant_count:,.0f}개")

tab1, tab2, tab3, tab4 = st.tabs(["📊 상권 대시보드", "🏪 업종 분석", "👥 연령대 분석", "📝 AI 리포트"])

with tab1:
    st.markdown("### 월별 결제금액 추이")
    monthly = filtered.groupby("month", as_index=False)["payment_amount"].sum()
    chart = alt.Chart(monthly).mark_line(point=True).encode(
        x=alt.X("month:N", title="월"),
        y=alt.Y("payment_amount:Q", title="결제금액"),
        tooltip=["month", alt.Tooltip("payment_amount:Q", format=",")]
    ).properties(height=320)
    st.altair_chart(chart, use_container_width=True)

    st.markdown("### 지역/동별 결제금액")
    district_pay = filtered.groupby("district", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
    chart2 = alt.Chart(district_pay).mark_bar().encode(
        x=alt.X("payment_amount:Q", title="결제금액"),
        y=alt.Y("district:N", title="동", sort="-x"),
        tooltip=["district", alt.Tooltip("payment_amount:Q", format=",")]
    ).properties(height=320)
    st.altair_chart(chart2, use_container_width=True)

with tab2:
    st.markdown("### 업종별 결제금액 TOP")
    industry_pay = filtered.groupby("industry", as_index=False).agg(
        payment_amount=("payment_amount", "sum"),
        transaction_count=("transaction_count", "sum"),
        avg_ticket=("avg_ticket", "mean"),
        revisit_rate=("revisit_rate", "mean"),
        merchant_count=("merchant_count", "mean")
    ).sort_values("payment_amount", ascending=False)

    chart3 = alt.Chart(industry_pay).mark_bar().encode(
        x=alt.X("payment_amount:Q", title="결제금액"),
        y=alt.Y("industry:N", title="업종", sort="-x"),
        tooltip=["industry", alt.Tooltip("payment_amount:Q", format=","), "transaction_count"]
    ).properties(height=360)
    st.altair_chart(chart3, use_container_width=True)

    st.markdown("### 창업 기회 점수")
    score = calc_opportunity_score(filtered)
    display_score = score[["industry", "startup_score", "payment_amount", "transaction_count", "avg_ticket", "revisit_rate", "merchant_count"]].copy()
    display_score["startup_score"] = display_score["startup_score"].round(1)
    display_score["avg_ticket"] = display_score["avg_ticket"].round(0)
    display_score["revisit_rate"] = (display_score["revisit_rate"] * 100).round(1)
    st.dataframe(display_score, use_container_width=True)

with tab3:
    st.markdown("### 연령대별 결제금액")
    age_pay = filtered.groupby("age_group", as_index=False)["payment_amount"].sum()
    chart4 = alt.Chart(age_pay).mark_bar().encode(
        x=alt.X("age_group:N", title="연령대"),
        y=alt.Y("payment_amount:Q", title="결제금액"),
        tooltip=["age_group", alt.Tooltip("payment_amount:Q", format=",")]
    ).properties(height=320)
    st.altair_chart(chart4, use_container_width=True)

    st.markdown("### 연령대 × 업종 소비 히트맵")
    heat = filtered.groupby(["age_group", "industry"], as_index=False)["payment_amount"].sum()
    chart5 = alt.Chart(heat).mark_rect().encode(
        x=alt.X("industry:N", title="업종"),
        y=alt.Y("age_group:N", title="연령대"),
        color=alt.Color("payment_amount:Q", title="결제금액"),
        tooltip=["age_group", "industry", alt.Tooltip("payment_amount:Q", format=",")]
    ).properties(height=320)
    st.altair_chart(chart5, use_container_width=True)

with tab4:
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
st.caption("※ 본 앱은 수업 발표용 프로토타입입니다. 실제 투자·창업 의사결정에는 임대료, 유동인구, 경쟁점포, 인허가, 원가구조 등의 추가 검토가 필요합니다.")

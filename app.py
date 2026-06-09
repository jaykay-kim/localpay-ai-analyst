
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="LocalPay AI Analyst",
    page_icon="💳",
    layout="wide"
)

SUWON_MERCHANT_TOTAL = 37369

REQUIRED_COLUMNS = [
    "month", "region", "district", "industry", "age_group",
    "payment_amount", "transaction_count", "avg_ticket"
]

@st.cache_data
def load_data():
    return pd.read_csv("sample_localpay_data.csv")

def format_won(value):
    value = float(value)
    if value >= 100_000_000:
        return f"{value/100_000_000:.1f}억 원"
    if value >= 10_000:
        return f"{value/10_000:.0f}만 원"
    return f"{value:,.0f}원"

def check_columns(data):
    missing = [c for c in REQUIRED_COLUMNS if c not in data.columns]
    return missing

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
    grouped["창업참고점수"] = grouped["창업참고점수"].round(1)
    return grouped.sort_values("창업참고점수", ascending=False)

def make_report(data, region, district):
    total_payment = data["payment_amount"].sum()
    total_txn = data["transaction_count"].sum()
    avg_ticket = total_payment / max(total_txn, 1)

    industry = data.groupby("industry", as_index=False).agg(
        payment_amount=("payment_amount", "sum"),
        transaction_count=("transaction_count", "sum")
    ).sort_values("payment_amount", ascending=False)

    age = data.groupby("age_group", as_index=False)["payment_amount"].sum().sort_values("payment_amount", ascending=False)
    score = startup_score(data)

    top_industry = industry.iloc[0]["industry"]
    top_age = age.iloc[0]["age_group"]
    rec = ", ".join(score.head(3)["industry"].tolist())

    area = region if district == "전체" else f"{region} {district}"

    return f"""
### AI Analyst Report: {area}

**데이터 기준**  
본 앱의 기본 데이터는 공공데이터포털의 **2025년 11월 수원시 지역화폐 결제정보**를 앱 형식으로 변환한 파일입니다.  
원본 데이터의 결제건수와 결제금액을 사용했습니다.

**핵심 요약**  
선택 지역의 총 결제금액은 **{format_won(total_payment)}**, 총 거래건수는 **{total_txn:,.0f}건**, 평균 객단가는 **{format_won(avg_ticket)}**입니다.

**상위 업종**  
결제금액 기준 가장 큰 업종은 **{top_industry}**입니다. 이 업종은 해당 지역에서 실제 지역화폐 소비 수요가 확인되는 업종으로 볼 수 있습니다.

**주요 소비 연령대**  
연령대별 결제금액은 **{top_age}** 비중이 가장 높게 나타났습니다.

**창업 참고 업종**  
결제금액, 결제건수, 평균 객단가를 결합한 1차 창업 참고 점수 기준 추천 업종은 **{rec}**입니다.

**가맹점 데이터 연계**  
경기도 지역화폐 가맹점 현황 OpenAPI에서 `SIGUN_NM=수원시` 조건으로 조회한 결과, 수원시 전체 지역화폐 가맹점 수는 **{SUWON_MERCHANT_TOTAL:,}개**입니다.  
향후 업종별·동별 가맹점 수까지 결합하면 “결제금액 ÷ 가맹점 수” 방식으로 점포당 소비 잠재력과 경쟁강도를 계산할 수 있습니다.

**한계**  
현재 결제정보 공공데이터에는 임대료, 유동인구, 재방문율, 이벤트 참여 여부, 업종별 가맹점 수가 포함되어 있지 않습니다. 따라서 본 시연은 실제 결제금액·결제건수·업종·연령대 중심의 1차 상권분석입니다.
"""

st.title("💳 LocalPay AI Analyst")
st.subheader("실제 수원시 지역화폐 공공데이터 기반 소상공인 창업 상권분석 플랫폼")

st.success("기본 탑재 데이터: 2025년 11월 수원시 지역화폐 결제정보 공공데이터")
st.caption("경기도 지역화폐 가맹점 현황 OpenAPI 조회 결과: 수원시 전체 가맹점 수 37,369개")

uploaded = st.sidebar.file_uploader("CSV 파일 업로드", type=["csv"])
if uploaded is not None:
    df = pd.read_csv(uploaded)
else:
    df = load_data()

missing = check_columns(df)
if missing:
    st.error("CSV 컬럼 오류: " + ", ".join(missing))
    st.stop()

for c in ["payment_amount", "transaction_count", "avg_ticket"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

st.sidebar.header("분석 조건")

regions = ["전체"] + sorted(df["region"].astype(str).unique().tolist())
region = st.sidebar.selectbox("시/군/구 선택", regions, index=1 if len(regions) > 1 else 0)

filtered = df.copy()
if region != "전체":
    filtered = filtered[filtered["region"].astype(str) == region]

districts = ["전체"] + sorted(filtered["district"].astype(str).unique().tolist())
district = st.sidebar.selectbox("읍/면/동 선택", districts)

if district != "전체":
    filtered = filtered[filtered["district"].astype(str) == district]

months = sorted(filtered["month"].astype(str).unique().tolist())
selected_months = st.sidebar.multiselect("분석 월", months, default=months)
if selected_months:
    filtered = filtered[filtered["month"].astype(str).isin(selected_months)]

if filtered.empty:
    st.warning("선택 조건에 해당하는 데이터가 없습니다.")
    st.stop()

total_payment = filtered["payment_amount"].sum()
total_txn = filtered["transaction_count"].sum()
avg_ticket = total_payment / max(total_txn, 1)

c1, c2, c3, c4 = st.columns(4)
c1.metric("총 결제금액", format_won(total_payment))
c2.metric("총 거래건수", f"{total_txn:,.0f}건")
c3.metric("평균 객단가", format_won(avg_ticket))
c4.metric("수원시 가맹점 수", f"{SUWON_MERCHANT_TOTAL:,}개")

tab1, tab2, tab3, tab4 = st.tabs(["지역 분석", "업종 분석", "연령·성별 분석", "AI 리포트"])

with tab1:
    st.markdown("### 읍면동별 결제금액")
    district_pay = filtered.groupby("district")["payment_amount"].sum().sort_values(ascending=False)
    st.bar_chart(district_pay)
    st.dataframe(district_pay.reset_index().rename(columns={"district":"읍면동", "payment_amount":"결제금액"}), use_container_width=True)

with tab2:
    st.markdown("### 업종별 결제금액 TOP")
    industry_pay = filtered.groupby("industry")["payment_amount"].sum().sort_values(ascending=False)
    st.bar_chart(industry_pay.head(20))
    st.dataframe(industry_pay.reset_index().rename(columns={"industry":"업종", "payment_amount":"결제금액"}), use_container_width=True)

    st.markdown("### 창업 참고 점수")
    score = startup_score(filtered)
    st.dataframe(score, use_container_width=True)

with tab3:
    st.markdown("### 연령대별 결제금액")
    age_pay = filtered.groupby("age_group")["payment_amount"].sum().sort_values(ascending=False)
    st.bar_chart(age_pay)
    st.dataframe(age_pay.reset_index().rename(columns={"age_group":"연령대", "payment_amount":"결제금액"}), use_container_width=True)

    if "gender" in filtered.columns:
        st.markdown("### 성별 결제금액")
        gender_pay = filtered.groupby("gender")["payment_amount"].sum().sort_values(ascending=False)
        st.bar_chart(gender_pay)
        st.dataframe(gender_pay.reset_index().rename(columns={"gender":"성별", "payment_amount":"결제금액"}), use_container_width=True)

with tab4:
    st.markdown(make_report(filtered, region, district))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import anthropic
import os
import json

st.set_page_config(
    page_title="AI 창업 상권분석 플랫폼",
    page_icon="🏪",
    layout="wide"
)

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
    color: white;
    padding: 24px 28px;
    border-radius: 14px;
    margin-bottom: 24px;
}
.data-badge {
    display: inline-block;
    background: #e8f0fe;
    color: #1a73e8;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
    margin: 2px;
}
.insight-box {
    background: #f0f4ff;
    border-left: 4px solid #1a73e8;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 8px 0;
    line-height: 1.8;
}
</style>
""", unsafe_allow_html=True)

# ── 상수 ────────────────────────────────────────────────
SIDO_CODES = {
    "서울특별시": "11", "부산광역시": "26", "대구광역시": "27",
    "인천광역시": "28", "광주광역시": "29", "대전광역시": "30",
    "울산광역시": "31", "세종특별자치시": "36", "경기도": "41",
    "강원특별자치도": "51", "충청북도": "43", "충청남도": "44",
    "전북특별자치도": "52", "전라남도": "46", "경상북도": "47",
    "경상남도": "48", "제주특별자치도": "50"
}

INDUSTRY_MAP = {
    "한식": "Q12A01", "중식": "Q12A02", "일식": "Q12A03", "양식": "Q12A04",
    "카페/커피": "Q12A05", "패스트푸드": "Q12A06", "치킨": "Q12A07",
    "분식": "Q12A08", "편의점": "Q15A01", "슈퍼마켓": "Q15A02",
    "약국": "Q14A01", "의류": "Q13A01", "미용실": "Q11A01",
    "네일숍": "Q11A02", "세탁소": "Q11A03", "학원(보습)": "Q10A01",
    "헬스장/PT": "Q10A02", "부동산": "Q16A01", "인테리어": "Q16A02"
}

# ── API 호출 함수 ────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_store_data(api_key: str, sido_cd: str, inds_lrg_cd: str = None, page_no: int = 1, num_rows: int = 1000):
    """소상공인시장진흥공단 상가(상권)정보 API"""
    url = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInAdmi"
    params = {
        "serviceKey": api_key,
        "pageNo": page_no,
        "numOfRows": num_rows,
        "divId": "ctprvnCd",
        "key": sido_cd,
        "type": "json"
    }
    if inds_lrg_cd:
        params["indsLrgCd"] = inds_lrg_cd
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        body = data.get("body", {})
        items = body.get("items", [])
        total = body.get("totalCount", 0)
        return pd.DataFrame(items) if items else pd.DataFrame(), total
    except Exception as e:
        return pd.DataFrame(), 0

@st.cache_data(ttl=3600)
def fetch_store_by_sigungu(api_key: str, sigungu_cd: str, page_no: int = 1, num_rows: int = 1000):
    """시군구 코드 기준 상가 조회"""
    url = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInAdmi"
    params = {
        "serviceKey": api_key,
        "pageNo": page_no,
        "numOfRows": num_rows,
        "divId": "sigunguCd",
        "key": sigungu_cd,
        "type": "json"
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        body = data.get("body", {})
        items = body.get("items", [])
        total = body.get("totalCount", 0)
        return pd.DataFrame(items) if items else pd.DataFrame(), total
    except Exception as e:
        return pd.DataFrame(), 0

def format_won(value):
    v = float(value)
    if v >= 100_000_000:
        return f"{v/100_000_000:.1f}억"
    if v >= 10_000:
        return f"{v/10_000:.0f}만"
    return f"{v:,.0f}"

# ── AI 분석 ─────────────────────────────────────────────
def generate_ai_analysis(summary: dict) -> str:
    try:
        client = anthropic.Anthropic()
        prompt = f"""
당신은 소상공인 창업을 돕는 AI 상권분석 전문가입니다.
아래 실제 공공데이터(소상공인시장진흥공단 상가정보)를 바탕으로 창업 희망자에게 유용한 분석을 해주세요.

[분석 조건]
- 지역: {summary['region']}
- 관심 업종: {summary['industry']}
- 전체 상가 수: {summary['total_stores']:,}개
- 해당 업종 점포 수: {summary['target_stores']:,}개
- 업종 집중도(해당업종/전체): {summary['concentration']:.1f}%
- 상위 5개 행정동 밀집 현황: {summary['top_districts']}
- 업종 다양성 지수 (동일 지역 내 업종 수): {summary['industry_diversity']}개 업종

다음을 포함해 창업자 관점의 분석 리포트를 작성해주세요:
1. **시장 현황 요약** — 이 지역 이 업종의 경쟁 강도는?
2. **유망 입지 추천** — 어느 행정동이 창업에 유리한가? (과포화 vs 블루오션)
3. **창업 리스크 요인** — 주의해야 할 점
4. **AI 종합 의견** — 한 줄 결론

친근하고 실용적인 톤으로, 마크다운 형식으로 작성해주세요.
"""
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except anthropic.AuthenticationError:
        return "⚠️ API 키를 확인해주세요. 사이드바에서 Anthropic API 키를 입력하세요."
    except Exception as e:
        return f"⚠️ AI 분석 생성 오류: {str(e)}"

# ════════════════════════════════════════════════════════
# 메인 UI
# ════════════════════════════════════════════════════════

st.markdown("""
<div class="main-header">
    <h1 style="margin:0; font-size:1.8rem;">🏪 AI 창업 상권분석 플랫폼</h1>
    <p style="margin:6px 0 0 0; opacity:0.9;">소상공인진흥공단 실데이터 기반 · AI 입지 분석 · 업종별 경쟁 현황</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<span class="data-badge">📊 소상공인시장진흥공단 상가정보 API</span>
<span class="data-badge">🏛️ 공공데이터포털 data.go.kr</span>
<span class="data-badge">🤖 Claude AI 분석</span>
""", unsafe_allow_html=True)

# ── 사이드바 ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ API 설정")

    pub_api_key = st.text_input(
        "공공데이터포털 API 키",
        type="password",
        placeholder="공공데이터포털 발급 키 입력",
        help="data.go.kr 회원가입 후 '소상공인시장진흥공단_상가(상권)정보' 활용신청"
    )

    anthropic_key = st.text_input(
        "Anthropic API 키 (AI 분석용)",
        type="password",
        placeholder="sk-ant-..."
    )
    if anthropic_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key

    st.divider()
    st.header("🔍 분석 조건")

    sido = st.selectbox("시/도 선택", list(SIDO_CODES.keys()), index=0)
    industry_name = st.selectbox("관심 업종", list(INDUSTRY_MAP.keys()), index=0)
    top_n = st.slider("행정동 TOP N 표시", 5, 20, 10)

    analyze_btn = st.button("🚀 상권 분석 시작", type="primary", use_container_width=True)

    st.divider()
    st.caption("📌 API 키 발급 방법")
    st.caption("1. data.go.kr 회원가입")
    st.caption("2. '소상공인 상가정보' 검색")
    st.caption("3. 활용신청 → 인증키 발급")
    st.caption("(개발계정 약 1시간 후 사용 가능)")

# ── 메인 콘텐츠 ──────────────────────────────────────────
if not analyze_btn:
    # 랜딩 화면
    st.markdown("### 📖 이 플랫폼은 무엇인가요?")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**📍 지역 × 업종 분석**\n\n관심 지역의 특정 업종 점포 수, 밀집 행정동, 경쟁 강도를 한눈에 파악합니다.")
    with col2:
        st.success("**📊 실데이터 기반**\n\n소상공인시장진흥공단이 국세청·카드사 데이터로 구축한 전국 상가정보를 실시간 호출합니다.")
    with col3:
        st.warning("**🤖 AI 창업 제언**\n\nClaude AI가 데이터를 해석해 블루오션 입지, 리스크 요인, 창업 적합도를 제안합니다.")

    st.markdown("---")
    st.markdown("### 🗂️ 활용 데이터 출처")
    st.markdown("""
| 데이터 | 제공기관 | 내용 | 링크 |
|--------|---------|------|------|
| 상가(상권)정보 API | 소상공인시장진흥공단 | 전국 상가업소 업종·위치·상호 | [data.go.kr](https://www.data.go.kr/data/15012005/openapi.do) |
| 전국지역화폐가맹점 | 행정안전부 | 지역화폐 가맹점 현황 | [data.go.kr](https://www.data.go.kr/data/15100062/standard.do) |
| 온누리상품권 가맹점 | 소상공인시장진흥공단 | 온누리 가맹점 전국 현황 | [data.go.kr](https://www.data.go.kr/data/3060079/fileData.do) |
""")
    st.info("👈 사이드바에서 API 키와 분석 조건을 입력하고 **상권 분석 시작** 버튼을 눌러주세요.")

elif not pub_api_key:
    st.error("공공데이터포털 API 키를 사이드바에 입력해주세요.")
    st.markdown("""
**API 키 발급 방법:**
1. [data.go.kr](https://www.data.go.kr) 접속 → 회원가입
2. 검색창에 **'소상공인시장진흥공단 상가정보'** 검색
3. 오픈API → 활용신청
4. 개발계정 자동승인 (약 1시간 후 사용 가능)
""")

else:
    sido_cd = SIDO_CODES[sido]
    inds_cd = INDUSTRY_MAP[industry_name]

    with st.spinner(f"🔄 {sido} 상가 데이터를 불러오는 중..."):
        df_all, total_all = fetch_store_data(pub_api_key, sido_cd, num_rows=1000)
        df_target, total_target = fetch_store_data(pub_api_key, sido_cd, inds_lrg_cd=inds_cd, num_rows=1000)

    if df_all.empty:
        st.error("데이터를 불러오지 못했습니다. API 키와 네트워크 상태를 확인해주세요.")
        st.stop()

    # ── KPI ────────────────────────────────────────────
    concentration = (len(df_target) / max(len(df_all), 1)) * 100

    st.info(f"📍 **{sido}** | 업종: **{industry_name}** | 조회 기준: 소상공인시장진흥공단 상가정보 (실데이터)")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 조회 상가 수", f"{len(df_all):,}개")
    c2.metric(f"{industry_name} 점포 수", f"{len(df_target):,}개")
    c3.metric("업종 집중도", f"{concentration:.1f}%")
    c4.metric("API 총 레코드", f"{total_all:,}개")

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📍 지역별 분포", "🏪 업종 현황", "🤖 AI 창업 분석"])

    # ── 탭1: 지역별 분포 ──────────────────────────────
    with tab1:
        if not df_all.empty and "adongNm" in df_all.columns:
            st.markdown(f"### {sido} 행정동별 전체 상가 분포")

            dong_count = (
                df_all.groupby("adongNm")
                .size()
                .reset_index(name="점포수")
                .sort_values("점포수", ascending=False)
                .head(top_n)
            )

            fig1 = px.bar(
                dong_count, x="adongNm", y="점포수",
                text="점포수",
                color="점포수",
                color_continuous_scale="Blues",
                title=f"{sido} 행정동별 상가 점포 수 TOP {top_n}"
            )
            fig1.update_traces(textposition="outside")
            fig1.update_layout(
                xaxis_tickangle=-35,
                coloraxis_showscale=False,
                height=420,
                plot_bgcolor="white"
            )
            st.plotly_chart(fig1, use_container_width=True)

            if not df_target.empty and "adongNm" in df_target.columns:
                st.markdown(f"### {industry_name} 업종 행정동별 분포")
                target_dong = (
                    df_target.groupby("adongNm")
                    .size()
                    .reset_index(name="점포수")
                    .sort_values("점포수", ascending=False)
                    .head(top_n)
                )
                fig2 = px.bar(
                    target_dong, x="adongNm", y="점포수",
                    text="점포수",
                    color="점포수",
                    color_continuous_scale="Oranges",
                    title=f"{sido} {industry_name} 행정동별 집중도 TOP {top_n}"
                )
                fig2.update_traces(textposition="outside")
                fig2.update_layout(
                    xaxis_tickangle=-35,
                    coloraxis_showscale=False,
                    height=420,
                    plot_bgcolor="white"
                )
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("행정동 데이터가 없습니다. API 응답을 확인해주세요.")
            if not df_all.empty:
                st.write("API 응답 컬럼:", df_all.columns.tolist())

    # ── 탭2: 업종 현황 ────────────────────────────────
    with tab2:
        if not df_all.empty and "indsMclsNm" in df_all.columns:
            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("### 업종 중분류별 점포 수")
                inds_count = (
                    df_all.groupby("indsMclsNm")
                    .size()
                    .reset_index(name="점포수")
                    .sort_values("점포수", ascending=False)
                    .head(15)
                )
                fig3 = px.bar(
                    inds_count, x="점포수", y="indsMclsNm",
                    orientation="h",
                    text="점포수",
                    color="점포수",
                    color_continuous_scale="Teal",
                    title="업종 중분류별 점포 수 TOP 15"
                )
                fig3.update_traces(textposition="outside")
                fig3.update_layout(
                    yaxis=dict(autorange="reversed"),
                    coloraxis_showscale=False,
                    height=480,
                    plot_bgcolor="white"
                )
                st.plotly_chart(fig3, use_container_width=True)

            with col_b:
                st.markdown("### 업종 대분류 비중")
                if "indsLclsNm" in df_all.columns:
                    lrg_count = (
                        df_all.groupby("indsLclsNm")
                        .size()
                        .reset_index(name="점포수")
                        .sort_values("점포수", ascending=False)
                    )
                    fig4 = px.pie(
                        lrg_count, names="indsLclsNm", values="점포수",
                        color_discrete_sequence=px.colors.qualitative.Pastel,
                        title="업종 대분류 비중"
                    )
                    fig4.update_traces(textposition="inside", textinfo="percent+label")
                    fig4.update_layout(height=480, showlegend=False)
                    st.plotly_chart(fig4, use_container_width=True)

            with st.expander("📋 전체 상가 데이터 보기 (상위 200개)"):
                cols_to_show = [c for c in ["bizesNm", "indsLclsNm", "indsMclsNm", "indsScnm", "lnAdr", "rdnAdr"] if c in df_all.columns]
                rename_map = {
                    "bizesNm": "상호명", "indsLclsNm": "대분류",
                    "indsMclsNm": "중분류", "indsScnm": "소분류",
                    "lnAdr": "지번주소", "rdnAdr": "도로명주소"
                }
                st.dataframe(
                    df_all[cols_to_show].head(200).rename(columns=rename_map),
                    use_container_width=True
                )
        else:
            st.warning("업종 분류 데이터가 없습니다.")
            if not df_all.empty:
                st.write("API 응답 샘플:", df_all.head(3))

    # ── 탭3: AI 창업 분석 ────────────────────────────
    with tab3:
        st.markdown("### 🤖 AI 창업 상권 분석 리포트")
        st.caption("Claude AI가 실데이터를 해석해 창업 입지와 리스크를 분석합니다.")

        # 요약 데이터 준비
        top_districts_str = "데이터 없음"
        industry_diversity = 0

        if not df_target.empty and "adongNm" in df_target.columns:
            top5 = (
                df_target.groupby("adongNm")
                .size()
                .sort_values(ascending=False)
                .head(5)
            )
            top_districts_str = ", ".join([f"{k}({v}개)" for k, v in top5.items()])

        if not df_all.empty and "indsMclsNm" in df_all.columns:
            industry_diversity = df_all["indsMclsNm"].nunique()

        summary = {
            "region": sido,
            "industry": industry_name,
            "total_stores": len(df_all),
            "target_stores": len(df_target),
            "concentration": concentration,
            "top_districts": top_districts_str,
            "industry_diversity": industry_diversity
        }

        if st.button("🚀 AI 분석 리포트 생성", type="primary"):
            if not anthropic_key:
                st.warning("AI 분석을 위해 사이드바에서 Anthropic API 키를 입력해주세요.")
            else:
                with st.spinner("Claude AI가 상권 데이터를 분석 중입니다..."):
                    report = generate_ai_analysis(summary)
                st.markdown(f'<div class="insight-box">{report}</div>', unsafe_allow_html=True)
        else:
            # 기본 요약
            st.markdown(f"""
**📊 기본 분석 요약**

- **분석 지역**: {sido}
- **관심 업종**: {industry_name}
- **전체 상가 중 {industry_name} 비중**: {concentration:.1f}% ({len(df_target):,}개 / {len(df_all):,}개)
- **밀집 행정동 TOP 5**: {top_districts_str}
- **지역 내 업종 다양성**: {industry_diversity}개 중분류

> 💡 **AI 분석 리포트 생성** 버튼을 누르면 Claude AI가 블루오션 입지, 경쟁강도, 창업 리스크를 상세히 분석해드립니다.
""")

        st.divider()
        st.markdown("#### 📌 데이터 및 분석 한계")
        st.info("""
- 본 분석은 **소상공인시장진흥공단 상가(상권)정보 API** 실데이터 기반입니다.
- 매출액, 임대료, 유동인구는 포함되지 않으며, 점포 수 기반의 경쟁 밀도 분석입니다.
- API 1회 호출 기준 최대 1,000건 조회 (전체 데이터는 페이징 처리 필요)
- 창업 결정 시 반드시 현장 조사와 전문가 상담을 병행하시기 바랍니다.
""")

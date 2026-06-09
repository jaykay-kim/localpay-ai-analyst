import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import anthropic
import os

st.set_page_config(page_title="AI 창업 상권분석 플랫폼", page_icon="🏪", layout="wide")

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
    color: white; padding: 24px 28px; border-radius: 14px; margin-bottom: 24px;
}
.data-badge {
    display: inline-block; background: #e8f0fe; color: #1a73e8;
    padding: 4px 10px; border-radius: 20px; font-size: 12px; margin: 2px;
}
.insight-box {
    background: #f0f4ff; border-left: 4px solid #1a73e8;
    border-radius: 8px; padding: 16px 20px; margin: 8px 0; line-height: 1.8;
}
</style>
""", unsafe_allow_html=True)

SIDO_LIST = [
    "서울특별시", "광주광역시", "부산광역시", "대구광역시", "대전광역시",
    "인천광역시", "울산광역시", "세종특별자치시", "경기도", "강원특별자치도",
    "충청북도", "충청남도", "전북특별자치도", "경상남도"
]
SIDO_API_CODES = {
    "서울특별시":"11","부산광역시":"26","대구광역시":"27","인천광역시":"28",
    "광주광역시":"29","대전광역시":"30","울산광역시":"31","세종특별자치시":"36",
    "경기도":"41","강원특별자치도":"51","충청북도":"43","충청남도":"44",
    "전북특별자치도":"52","경상남도":"48"
}
INDUSTRY_LIST = sorted(list(set([
    "한식", "중식", "일식", "서양식", "기타 간이", "기타 외국",
    "구내식당·뷔페", "주점", "비알코올 ",
    "이용·미용", "욕탕·신체관리", "세탁",
    "의원", "병원", "의약·화장품 소매", "수의",
    "일반 교육", "기타 교육", "스포츠 서비스",
    "식료품 소매", "종합 소매", "음료 소매",
    "섬유·의복·신발 소매", "가구 소매", "가전·통신 소매",
    "부동산 서비스", "여행사·보조", "사진 촬영",
    "자동차 수리·세차", "컴퓨터 수리"
])))

@st.cache_data(ttl=3600)
def try_api(api_key, sido_cd):
    try:
        url = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInAdmi"
        params = {"serviceKey": api_key, "pageNo": 1, "numOfRows": 1000,
                  "divId": "ctprvnCd", "key": sido_cd, "type": "json"}
        resp = requests.get(url, params=params, timeout=10)
        items = resp.json().get("body", {}).get("items", [])
        total = resp.json().get("body", {}).get("totalCount", 0)
        if items:
            return pd.DataFrame(items), total
    except:
        pass
    return None, 0

@st.cache_data
def load_sample():
    return pd.read_csv("sample_store_data.csv")

def get_data(api_key, sido):
    sido_cd = SIDO_API_CODES.get(sido, "11")
    if api_key:
        df, total = try_api(api_key, sido_cd)
        if df is not None and not df.empty:
            return df, total, "✅ 실데이터 (소상공인시장진흥공단 API 실시간 호출)"
    df_all = load_sample()
    df = df_all[df_all["sigunguNm"] == sido].copy()
    if df.empty:
        df = df_all.copy()
    return df, len(df), "📋 실데이터 샘플 (소상공인시장진흥공단 2026.03 파일데이터 기반)"

def generate_ai_analysis(summary):
    try:
        client = anthropic.Anthropic()
        prompt = f"""당신은 소상공인 창업을 돕는 AI 상권분석 전문가입니다.
아래 실제 공공데이터(소상공인시장진흥공단 상가정보) 기반 분석 결과를 바탕으로
창업 희망자에게 유용한 리포트를 작성해주세요.

[분석 데이터]
- 지역: {summary['region']}
- 관심 업종: {summary['industry']}
- 전체 상가 수: {summary['total_stores']:,}개
- 해당 업종 점포 수: {summary['target_stores']:,}개
- 업종 집중도: {summary['concentration']:.1f}%
- 밀집 행정동 TOP5: {summary['top_districts']}
- 업종 다양성: {summary['industry_diversity']}개 중분류

다음 항목으로 마크다운 리포트를 작성해주세요:
1. **시장 현황 요약** — 경쟁 강도 평가
2. **유망 입지 추천** — 과포화 vs 블루오션 행정동
3. **창업 리스크 요인** — 주의사항
4. **AI 종합 의견** — 한 줄 결론"""
        msg = client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except anthropic.AuthenticationError:
        return "⚠️ Anthropic API 키를 확인해주세요."
    except Exception as e:
        return f"⚠️ AI 분석 오류: {str(e)}"

# ── session_state 초기화 ──────────────────────────────
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False
if "ai_report" not in st.session_state:
    st.session_state.ai_report = ""
if "df_all" not in st.session_state:
    st.session_state.df_all = None
if "df_target" not in st.session_state:
    st.session_state.df_target = None
if "summary" not in st.session_state:
    st.session_state.summary = {}
if "data_source" not in st.session_state:
    st.session_state.data_source = ""
if "sido_saved" not in st.session_state:
    st.session_state.sido_saved = ""
if "industry_saved" not in st.session_state:
    st.session_state.industry_saved = ""

# ── UI ───────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1 style="margin:0;font-size:1.8rem;">🏪 AI 창업 상권분석 플랫폼</h1>
  <p style="margin:6px 0 0;opacity:.9;">소상공인진흥공단 실데이터 기반 · AI 입지 분석 · 업종별 경쟁 현황</p>
</div>""", unsafe_allow_html=True)

st.markdown("""
<span class="data-badge">📊 소상공인시장진흥공단 상가정보</span>
<span class="data-badge">🏛️ 공공데이터포털 data.go.kr</span>
<span class="data-badge">🤖 Claude AI 분석</span>
<span class="data-badge">📅 2026년 3월 기준</span>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 설정")
    pub_api_key = st.text_input("공공데이터포털 API 키 (선택)", type="password", placeholder="없으면 실데이터 샘플로 동작")
    anthropic_key = st.text_input("Anthropic API 키 (AI 분석용)", type="password", placeholder="sk-ant-...")
    if anthropic_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key

    st.divider()
    st.header("🔍 분석 조건")
    sido = st.selectbox("시/도 선택", SIDO_LIST)
    industry_name = st.selectbox("관심 업종", INDUSTRY_LIST)
    top_n = st.slider("행정동 TOP N", 5, 20, 10)
    analyze_btn = st.button("🚀 상권 분석 시작", type="primary", use_container_width=True)

    st.divider()
    st.caption("💡 API 키 없이도 실데이터 샘플로 시연 가능")
    st.caption("출처: 소상공인시장진흥공단 상가(상권)정보 2026.03")

# ── 분석 실행 ─────────────────────────────────────────
if analyze_btn:
    with st.spinner(f"🔄 {sido} 데이터 로딩 중..."):
        df_all, total_all, data_source = get_data(pub_api_key, sido)
    df_target = df_all[df_all["indsMclsNm"] == industry_name].copy() if "indsMclsNm" in df_all.columns else pd.DataFrame()
    concentration = (len(df_target) / max(len(df_all), 1)) * 100
    dong_col = "adongNm" if "adongNm" in df_all.columns else None
    top_districts_str = "데이터 없음"
    if not df_target.empty and dong_col:
        top5 = df_target.groupby(dong_col).size().sort_values(ascending=False).head(5)
        top_districts_str = ", ".join([f"{k}({v}개)" for k, v in top5.items()])
    industry_diversity = df_all["indsMclsNm"].nunique() if "indsMclsNm" in df_all.columns else 0

    # session_state에 저장
    st.session_state.analyzed = True
    st.session_state.ai_report = ""
    st.session_state.df_all = df_all
    st.session_state.df_target = df_target
    st.session_state.data_source = data_source
    st.session_state.sido_saved = sido
    st.session_state.industry_saved = industry_name
    st.session_state.summary = {
        "region": sido, "industry": industry_name,
        "total_stores": len(df_all), "target_stores": len(df_target),
        "concentration": concentration,
        "top_districts": top_districts_str,
        "industry_diversity": industry_diversity,
        "total_all": total_all
    }

# ── 결과 표시 ─────────────────────────────────────────
if not st.session_state.analyzed:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("**📍 지역 × 업종 분석**\n\n전국 상가 실데이터 기반으로 행정동별 점포 수와 경쟁 밀도를 분석합니다.")
    with c2:
        st.success("**📊 실데이터 기반**\n\n소상공인시장진흥공단 2026년 3월 전국 상가정보 (국세청·카드사 기반)를 활용합니다.")
    with c3:
        st.warning("**🤖 AI 창업 제언**\n\nClaude AI가 블루오션 입지, 경쟁 리스크, 창업 적합도를 분석합니다.")
    st.divider()
    st.markdown("### 🗂️ 활용 데이터 출처")
    st.markdown("""
| 데이터 | 제공기관 | 기준일 | 링크 |
|--------|---------|--------|------|
| 상가(상권)정보 | 소상공인시장진흥공단 | 2026.03 | [data.go.kr](https://www.data.go.kr/data/15083033/fileData.do) |
| 상가정보 Open API | 소상공인시장진흥공단 | 실시간 | [data.go.kr](https://www.data.go.kr/data/15012005/openapi.do) |
| 온누리상품권 가맹점 | 소상공인시장진흥공단 | - | [data.go.kr](https://www.data.go.kr/data/3060079/fileData.do) |
""")
    st.info("👈 사이드바에서 분석 조건을 설정하고 **상권 분석 시작**을 눌러주세요.")

else:
    df_all = st.session_state.df_all
    df_target = st.session_state.df_target
    summary = st.session_state.summary
    sido_saved = st.session_state.sido_saved
    industry_saved = st.session_state.industry_saved
    concentration = summary["concentration"]
    dong_col = "adongNm" if "adongNm" in df_all.columns else None

    if "✅" in st.session_state.data_source:
        st.success(st.session_state.data_source)
    else:
        st.info(st.session_state.data_source)

    st.info(f"📍 **{sido_saved}** | 관심 업종: **{industry_saved}**")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 조회 상가", f"{len(df_all):,}개")
    c2.metric(f"{industry_saved} 점포", f"{len(df_target):,}개")
    c3.metric("업종 집중도", f"{concentration:.1f}%")
    c4.metric("전체 레코드 수", f"{summary['total_all']:,}개")

    st.divider()
    tab1, tab2, tab3 = st.tabs(["📍 지역별 분포", "🏪 업종 현황", "🤖 AI 창업 분석"])

    with tab1:
        if dong_col:
            ca, cb = st.columns(2)
            with ca:
                st.markdown(f"#### 행정동별 전체 상가 TOP {top_n}")
                d = df_all.groupby(dong_col).size().reset_index(name="점포수").sort_values("점포수", ascending=False).head(top_n)
                fig = px.bar(d, x=dong_col, y="점포수", text="점포수", color="점포수", color_continuous_scale="Blues")
                fig.update_traces(textposition="outside")
                fig.update_layout(xaxis_tickangle=-35, coloraxis_showscale=False, height=400, plot_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
            with cb:
                if not df_target.empty:
                    st.markdown(f"#### {industry_saved} 행정동별 분포 TOP {top_n}")
                    d2 = df_target.groupby(dong_col).size().reset_index(name="점포수").sort_values("점포수", ascending=False).head(top_n)
                    fig2 = px.bar(d2, x=dong_col, y="점포수", text="점포수", color="점포수", color_continuous_scale="Oranges")
                    fig2.update_traces(textposition="outside")
                    fig2.update_layout(xaxis_tickangle=-35, coloraxis_showscale=False, height=400, plot_bgcolor="white")
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.warning(f"'{industry_saved}' 업종 데이터가 없습니다.")

    with tab2:
        ca, cb = st.columns(2)
        with ca:
            if "indsMclsNm" in df_all.columns:
                st.markdown("#### 업종 중분류별 점포 수 TOP 15")
                inds = df_all.groupby("indsMclsNm").size().reset_index(name="점포수").sort_values("점포수", ascending=False).head(15)
                fig3 = px.bar(inds, x="점포수", y="indsMclsNm", orientation="h", text="점포수",
                              color="점포수", color_continuous_scale="Teal")
                fig3.update_traces(textposition="outside")
                fig3.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, height=480, plot_bgcolor="white")
                st.plotly_chart(fig3, use_container_width=True)
        with cb:
            if "indsLclsNm" in df_all.columns:
                st.markdown("#### 업종 대분류 비중")
                lrg = df_all.groupby("indsLclsNm").size().reset_index(name="점포수")
                fig4 = px.pie(lrg, names="indsLclsNm", values="점포수", color_discrete_sequence=px.colors.qualitative.Pastel)
                fig4.update_traces(textposition="inside", textinfo="percent+label")
                fig4.update_layout(height=480, showlegend=False)
                st.plotly_chart(fig4, use_container_width=True)
        with st.expander("📋 상가 데이터 상위 200개"):
            cols = [c for c in ["bizesNm","indsLclsNm","indsMclsNm","adongNm","rdnAdr"] if c in df_all.columns]
            rename = {"bizesNm":"상호명","indsLclsNm":"대분류","indsMclsNm":"중분류","adongNm":"행정동","rdnAdr":"주소"}
            st.dataframe(df_all[cols].head(200).rename(columns=rename), use_container_width=True)

    with tab3:
        st.markdown("### 🤖 AI 창업 상권 분석 리포트")
        st.caption("Claude AI가 실데이터를 해석해 창업 입지와 리스크를 분석합니다.")

        st.markdown(f"""
**📊 기본 분석 요약**
- **분석 지역**: {sido_saved} | **관심 업종**: {industry_saved}
- **{industry_saved} 비중**: {concentration:.1f}% ({len(df_target):,}개 / {len(df_all):,}개)
- **밀집 행정동 TOP 5**: {summary['top_districts']}
- **업종 다양성**: {summary['industry_diversity']}개 중분류
""")

        # AI 리포트 이미 생성된 경우 바로 표시
        if st.session_state.ai_report:
            st.markdown(f'<div class="insight-box">{st.session_state.ai_report}</div>', unsafe_allow_html=True)
        else:
            if st.button("🚀 AI 분석 리포트 생성", type="primary"):
                if not anthropic_key:
                    st.warning("사이드바에서 Anthropic API 키를 입력해주세요.")
                else:
                    with st.spinner("Claude AI 분석 중..."):
                        report = generate_ai_analysis(summary)
                    st.session_state.ai_report = report
                    st.markdown(f'<div class="insight-box">{report}</div>', unsafe_allow_html=True)

        st.divider()
        st.info("""
**📌 데이터 출처 및 한계**
- 소상공인시장진흥공단 상가(상권)정보 2026년 3월 기준 (국세청·카드사 데이터 기반)
- 매출액·임대료·유동인구는 포함되지 않으며, 점포 수 기반 경쟁 밀도 분석입니다
- 창업 결정 시 반드시 현장 조사와 전문가 상담을 병행하시기 바랍니다
""")

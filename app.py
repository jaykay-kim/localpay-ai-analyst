import streamlit as st
import pandas as pd
import plotly.express as px
import requests
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

SIDO_LIST = ["광주광역시"]
SIDO_API_CODES = {
    "서울특별시":"11","부산광역시":"26","대구광역시":"27","인천광역시":"28",
    "광주광역시":"29","대전광역시":"30","울산광역시":"31","세종특별자치시":"36",
    "경기도":"41","강원특별자치도":"51","충청북도":"43","충청남도":"44",
    "전북특별자치도":"52","전라남도":"46","경상북도":"47","경상남도":"48","제주특별자치도":"50"
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

@st.cache_data(show_spinner=False)
def load_sido_data(sido):
    """시도별 CSV 파일 로드"""
    path = f"data/{sido}.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()

def get_data(api_key, sido):
    sido_cd = SIDO_API_CODES.get(sido, "11")
    if api_key:
        df, total = try_api(api_key, sido_cd)
        if df is not None and not df.empty:
            return df, total, "✅ 실데이터 (소상공인시장진흥공단 API 실시간 호출)"
    df = load_sido_data(sido)
    if df.empty:
        return pd.DataFrame(), 0, "⚠️ 데이터 없음"
    return df, len(df), f"📋 실데이터 (소상공인시장진흥공단 2026.03 파일데이터 · {len(df):,}개 전체)"

def generate_ai_analysis(summary):
    region = summary["region"]
    industry = summary["industry"]
    total = summary["total_stores"]
    target = summary["target_stores"]
    conc = summary["concentration"]
    top_d = summary["top_districts"]
    diversity = summary["industry_diversity"]

    if conc >= 5:
        competition = "**매우 높음** 🔴"
        comp_comment = f"{region} 내 {industry} 업종은 전체 상가의 {conc:.1f}%를 차지하며 경쟁이 치열한 상태입니다."
    elif conc >= 3:
        competition = "**높음** 🟠"
        comp_comment = f"{region} 내 {industry} 업종은 전체 상가의 {conc:.1f}%로 경쟁 밀도가 높은 편입니다."
    elif conc >= 1:
        competition = "**보통** 🟡"
        comp_comment = f"{region} 내 {industry} 업종은 전체 상가의 {conc:.1f}%로 적정 수준의 경쟁이 형성되어 있습니다."
    else:
        competition = "**낮음** 🟢"
        comp_comment = f"{region} 내 {industry} 업종은 전체 상가의 {conc:.1f}%로 상대적으로 블루오션에 가깝습니다."

    top_dong_list = [d.split("(")[0] for d in top_d.split(", ") if "(" in d][:3]
    top_dong_str = ", ".join(top_dong_list) if top_dong_list else "정보 없음"

    if diversity >= 60:
        diversity_comment = f"업종 다양성이 {diversity}개 중분류로 매우 높아 상권이 활성화되어 있습니다."
    elif diversity >= 40:
        diversity_comment = f"업종 다양성이 {diversity}개 중분류로 다양한 업종이 공존하는 상권입니다."
    else:
        diversity_comment = f"업종 다양성이 {diversity}개 중분류로 특정 업종 중심의 상권입니다."

    return f"""
#### 1. 시장 현황 요약
{comp_comment} 총 {total:,}개 상가 중 {industry} 점포는 {target:,}개로 집계됩니다. {diversity_comment}

#### 2. 유망 입지 추천
밀집도 상위 행정동은 **{top_d}** 순으로 나타났습니다.
- **과포화 주의 지역**: {top_dong_str} — 이미 경쟁 점포가 집중된 지역으로 신규 진입 시 차별화 전략이 필요합니다.
- **블루오션 탐색 방향**: 밀집도 하위 행정동이나 인근 주거 밀집 지역을 중심으로 수요 대비 공급이 적은 입지를 탐색하세요.

#### 3. 창업 리스크 요인
- 본 데이터는 **점포 수 기반** 분석으로 실제 매출·임대료·유동인구는 반영되지 않습니다.
- 상위 밀집 행정동은 이미 경쟁이 포화 상태일 수 있어 **현장 방문 조사**가 필수입니다.
- 창업 전 소상공인시장진흥공단 [상권정보시스템(sg.sbiz.or.kr)](https://sg.sbiz.or.kr) 병행 활용을 권장합니다.

#### 4. AI 종합 의견
> {region} {industry} 시장은 경쟁강도 {competition} 수준입니다. 밀집 지역을 피하고 유동인구·임대료·접근성을 종합 고려한 입지 선정이 성공의 핵심입니다.

---
*소상공인시장진흥공단 2026년 3월 상가정보 실데이터 기반 분석입니다.*
"""

# ── session_state 초기화 ──────────────────────────────
for key, val in [("analyzed", False), ("ai_report", ""), ("df_all", None),
                 ("df_target", None), ("summary", {}), ("data_source", ""),
                 ("sido_saved", ""), ("industry_saved", "")]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── UI ───────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1 style="margin:0;font-size:1.8rem;">🏪 AI 창업 상권분석 플랫폼</h1>
  <p style="margin:6px 0 0;opacity:.9;">소상공인진흥공단 실데이터 기반 · AI 입지 분석 · 업종별 경쟁 현황</p>
</div>""", unsafe_allow_html=True)

st.markdown("""
<span class="data-badge">📊 소상공인시장진흥공단 상가정보</span>
<span class="data-badge">🏛️ 공공데이터포털 data.go.kr</span>
<span class="data-badge">🤖 AI 분석</span>
<span class="data-badge">📅 2026년 3월 기준</span>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 설정")
    pub_api_key = st.text_input("공공데이터포털 API 키 (선택)", type="password", placeholder="없으면 실데이터 파일로 동작")
    st.divider()
    st.header("🔍 분석 조건")
    sido = st.selectbox("시/도 선택", SIDO_LIST)
    industry_name = st.selectbox("관심 업종", INDUSTRY_LIST)
    top_n = st.slider("행정동 TOP N", 5, 20, 10)
    analyze_btn = st.button("🚀 상권 분석 시작", type="primary", use_container_width=True)
    st.divider()
    st.caption("📊 소상공인시장진흥공단 2026.03 전체 실데이터")
    st.caption("서울 537,489개 · 광주 75,325개 등 전국 272만개")

if analyze_btn:
    with st.spinner(f"🔄 {sido} 전체 데이터 로딩 중... (잠시 기다려주세요)"):
        df_all, total_all, data_source = get_data(pub_api_key, sido)

    if df_all.empty:
        st.error("데이터를 불러오지 못했습니다.")
        st.stop()

    df_target = df_all[df_all["indsMclsNm"] == industry_name].copy() if "indsMclsNm" in df_all.columns else pd.DataFrame()
    concentration = (len(df_target) / max(len(df_all), 1)) * 100
    dong_col = "adongNm" if "adongNm" in df_all.columns else None
    top_districts_str = "데이터 없음"
    if not df_target.empty and dong_col:
        top5 = df_target.groupby(dong_col).size().sort_values(ascending=False).head(5)
        top_districts_str = ", ".join([f"{k}({v}개)" for k, v in top5.items()])
    industry_diversity = df_all["indsMclsNm"].nunique() if "indsMclsNm" in df_all.columns else 0

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
        "concentration": concentration, "top_districts": top_districts_str,
        "industry_diversity": industry_diversity, "total_all": total_all
    }

if not st.session_state.analyzed:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("**📍 지역 × 업종 분석**\n\n전국 상가 실데이터 기반으로 행정동별 점포 수와 경쟁 밀도를 분석합니다.")
    with c2:
        st.success("**📊 전체 실데이터**\n\n소상공인시장진흥공단 2026년 3월 전국 272만개 상가정보 전체를 활용합니다.")
    with c3:
        st.warning("**🤖 AI 창업 제언**\n\n실데이터 기반으로 경쟁강도, 블루오션 입지, 창업 리스크를 분석합니다.")
    st.divider()
    st.markdown("### 🗂️ 활용 데이터 출처")
    st.markdown("""
| 데이터 | 제공기관 | 기준일 | 전국 상가 수 |
|--------|---------|--------|------|
| 상가(상권)정보 파일데이터 | 소상공인시장진흥공단 | 2026.03 | 2,725,319개 |
| 상가정보 Open API | 소상공인시장진흥공단 | 실시간 | - |
| 온누리상품권 가맹점 | 소상공인시장진흥공단 | - | - |
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
    c1.metric("전체 상가 수", f"{len(df_all):,}개")
    c2.metric(f"{industry_saved} 점포", f"{len(df_target):,}개")
    c3.metric("업종 집중도", f"{concentration:.1f}%")
    c4.metric("전체 레코드", f"{summary['total_all']:,}개")

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
                fig.update_layout(xaxis_tickangle=-35, coloraxis_showscale=False, height=420, plot_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
            with cb:
                if not df_target.empty:
                    st.markdown(f"#### {industry_saved} 행정동별 분포 TOP {top_n}")
                    d2 = df_target.groupby(dong_col).size().reset_index(name="점포수").sort_values("점포수", ascending=False).head(top_n)
                    fig2 = px.bar(d2, x=dong_col, y="점포수", text="점포수", color="점포수", color_continuous_scale="Oranges")
                    fig2.update_traces(textposition="outside")
                    fig2.update_layout(xaxis_tickangle=-35, coloraxis_showscale=False, height=420, plot_bgcolor="white")
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
        with st.expander("📋 상가 데이터 상위 500개"):
            cols = [c for c in ["bizesNm","indsLclsNm","indsMclsNm","adongNm","rdnAdr"] if c in df_all.columns]
            rename = {"bizesNm":"상호명","indsLclsNm":"대분류","indsMclsNm":"중분류","adongNm":"행정동","rdnAdr":"주소"}
            st.dataframe(df_all[cols].head(500).rename(columns=rename), use_container_width=True)

    with tab3:
        st.markdown("### 🤖 AI 창업 상권 분석 리포트")
        st.caption("실데이터 기반으로 경쟁강도, 유망 입지, 창업 리스크를 분석합니다.")
        st.markdown(f"""
**📊 기본 분석 요약**
- **분석 지역**: {sido_saved} | **관심 업종**: {industry_saved}
- **{industry_saved} 비중**: {concentration:.1f}% ({len(df_target):,}개 / {len(df_all):,}개)
- **밀집 행정동 TOP 5**: {summary['top_districts']}
- **업종 다양성**: {summary['industry_diversity']}개 중분류
""")
        if st.session_state.ai_report:
            st.markdown(f'<div class="insight-box">{st.session_state.ai_report}</div>', unsafe_allow_html=True)
        else:
            if st.button("🚀 AI 분석 리포트 생성", type="primary"):
                with st.spinner("분석 중..."):
                    report = generate_ai_analysis(summary)
                st.session_state.ai_report = report
                st.markdown(f'<div class="insight-box">{report}</div>', unsafe_allow_html=True)

        st.divider()
        st.info("""
**📌 데이터 출처 및 한계**
- 소상공인시장진흥공단 상가(상권)정보 2026년 3월 기준 전체 데이터 (국세청·카드사 기반)
- 매출액·임대료·유동인구는 포함되지 않으며, 점포 수 기반 경쟁 밀도 분석입니다
- 창업 결정 시 반드시 현장 조사와 전문가 상담을 병행하시기 바랍니다
""")

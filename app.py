
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os

st.set_page_config(page_title="Gwangju Startup Investment AI Analyst", page_icon="📈", layout="wide")

st.markdown("""
<style>
.main-header {background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%); color: white; padding: 24px 28px; border-radius: 14px; margin-bottom: 24px;}
.data-badge {display: inline-block; background: #e8f0fe; color: #1a73e8; padding: 4px 10px; border-radius: 20px; font-size: 12px; margin: 2px;}
.insight-box {background: #f0f4ff; border-left: 4px solid #1a73e8; border-radius: 8px; padding: 16px 20px; margin: 8px 0; line-height: 1.8;}
.good-box {background: #ecfdf5; border-left: 4px solid #10b981; border-radius: 8px; padding: 14px 18px; margin: 8px 0; line-height: 1.7;}
</style>
""", unsafe_allow_html=True)

SIDO_LIST = ["광주광역시"]
SIDO_API_CODES = {"광주광역시":"29"}
INDUSTRY_LIST = sorted(list(set([
    "한식", "중식", "일식", "서양식", "기타 간이", "기타 외국", "구내식당·뷔페", "주점", "비알코올 ",
    "이용·미용", "욕탕·신체관리", "세탁", "의원", "병원", "의약·화장품 소매", "수의", "일반 교육", "기타 교육", "스포츠 서비스",
    "식료품 소매", "종합 소매", "음료 소매", "섬유·의복·신발 소매", "가구 소매", "가전·통신 소매", "부동산 서비스",
    "여행사·보조", "사진 촬영", "자동차 수리·세차", "컴퓨터 수리"
])))

POLICY_FIT = {"한식":92,"중식":78,"일식":72,"서양식":70,"기타 간이":90,"비알코올 ":86,"식료품 소매":96,"종합 소매":90,"음료 소매":82,"의약·화장품 소매":84,"이용·미용":78,"세탁":82,"의원":65,"병원":60,"기타 교육":58,"일반 교육":56,"섬유·의복·신발 소매":74,"가전·통신 소매":55,"가구 소매":52,"자동차 수리·세차":50,"주점":40,"부동산 서비스":30}
CULTURE_FIT = {"한식":88,"기타 간이":86,"비알코올 ":94,"서양식":84,"일식":76,"중식":72,"섬유·의복·신발 소매":82,"사진 촬영":80,"여행사·보조":75,"스포츠 서비스":62,"식료품 소매":68,"종합 소매":64,"이용·미용":70,"의약·화장품 소매":60}
CULTURE_DONG_BONUS = {"동명동":12,"충장동":12,"서남동":8,"양림동":12,"사직동":8,"상무1동":8,"상무2동":8,"수완동":6,"첨단1동":6,"첨단2동":6,"용봉동":5,"운암동":4}

@st.cache_data(ttl=3600)
def try_api(api_key, sido_cd):
    try:
        url = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInAdmi"
        params = {"serviceKey": api_key, "pageNo": 1, "numOfRows": 1000, "divId": "ctprvnCd", "key": sido_cd, "type": "json"}
        resp = requests.get(url, params=params, timeout=10)
        items = resp.json().get("body", {}).get("items", [])
        total = resp.json().get("body", {}).get("totalCount", 0)
        if items: return pd.DataFrame(items), total
    except Exception: pass
    return None, 0

@st.cache_data(show_spinner=False)
def load_sido_data(sido):
    path = f"data/{sido}.csv"
    if os.path.exists(path): return pd.read_csv(path)
    return pd.DataFrame()

def get_data(api_key, sido):
    if api_key:
        df, total = try_api(api_key, SIDO_API_CODES.get(sido, "29"))
        if df is not None and not df.empty:
            return df, total, "✅ 실데이터 (소상공인시장진흥공단 API 실시간 호출)"
    df = load_sido_data(sido)
    if df.empty: return pd.DataFrame(), 0, "⚠️ 데이터 없음"
    return df, len(df), f"📋 실데이터 (소상공인시장진흥공단 2026.03 파일데이터 · {len(df):,}개 전체)"

def normalize(s):
    if s.max() == s.min(): return pd.Series([50] * len(s), index=s.index)
    return ((s - s.min()) / (s.max() - s.min()) * 100).fillna(0)

def get_policy_fit(industry): return POLICY_FIT.get(industry, 55)
def get_culture_fit(industry): return CULTURE_FIT.get(industry, 55)

def calc_dong_scores(df_all, industry_name):
    if "adongNm" not in df_all.columns or "indsMclsNm" not in df_all.columns: return pd.DataFrame()
    total_by_dong = df_all.groupby("adongNm").size().rename("전체점포수")
    target_by_dong = df_all[df_all["indsMclsNm"] == industry_name].groupby("adongNm").size().rename("관심업종점포수")
    diversity = df_all.groupby("adongNm")["indsMclsNm"].nunique().rename("업종다양성")
    result = pd.concat([total_by_dong, target_by_dong, diversity], axis=1).fillna(0).reset_index()
    result[["관심업종점포수","전체점포수","업종다양성"]] = result[["관심업종점포수","전체점포수","업종다양성"]].astype(int)
    result["시장수요점수"] = normalize(result["관심업종점포수"])
    result["경쟁완화점수"] = 100 - normalize(result["관심업종점포수"])
    result.loc[result["관심업종점포수"] == 0, "경쟁완화점수"] = 60
    result["상권다양성점수"] = normalize(result["업종다양성"])
    result["정책화폐적합도"] = get_policy_fit(industry_name)
    base_culture = get_culture_fit(industry_name)
    result["문화관광연계성"] = result["adongNm"].apply(lambda x: min(100, base_culture + CULTURE_DONG_BONUS.get(str(x), 0)))
    result["창업투자점수"] = (result["시장수요점수"]*0.35 + result["경쟁완화점수"]*0.25 + result["상권다양성점수"]*0.15 + result["정책화폐적합도"]*0.15 + result["문화관광연계성"]*0.10).round(1)
    result["경쟁강도"] = pd.cut(result["관심업종점포수"], bins=[-1,0,3,10,999999], labels=["수요검증 필요","낮음","보통","높음"]).astype(str)
    return result.sort_values("창업투자점수", ascending=False)

def calc_industry_scores(df_all):
    if "indsMclsNm" not in df_all.columns: return pd.DataFrame()
    g = df_all.groupby("indsMclsNm").agg(점포수=("indsMclsNm","size"), 진출행정동수=("adongNm","nunique")).reset_index().rename(columns={"indsMclsNm":"업종"})
    g["시장검증점수"] = normalize(g["점포수"])
    g["경쟁완화점수"] = 100 - normalize(g["점포수"]) * 0.7
    g["지역확산점수"] = normalize(g["진출행정동수"])
    g["정책화폐적합도"] = g["업종"].apply(get_policy_fit)
    g["문화관광연계성"] = g["업종"].apply(get_culture_fit)
    g["업종투자점수"] = (g["시장검증점수"]*0.30 + g["경쟁완화점수"]*0.20 + g["지역확산점수"]*0.15 + g["정책화폐적합도"]*0.20 + g["문화관광연계성"]*0.15).round(1)
    return g.sort_values("업종투자점수", ascending=False)

def generate_ai_analysis(summary, score_df):
    region, industry, total, target, conc, top_d, diversity = summary["region"], summary["industry"], summary["total_stores"], summary["target_stores"], summary["concentration"], summary["top_districts"], summary["industry_diversity"]
    best = score_df.iloc[0] if score_df is not None and not score_df.empty else None
    if conc >= 5: competition, comp_comment = "**매우 높음** 🔴", f"{region} 내 {industry} 업종은 전체 상가의 {conc:.1f}%를 차지해 경쟁이 강한 시장입니다."
    elif conc >= 3: competition, comp_comment = "**높음** 🟠", f"{region} 내 {industry} 업종은 전체 상가의 {conc:.1f}%로 경쟁 밀도가 높은 편입니다."
    elif conc >= 1: competition, comp_comment = "**보통** 🟡", f"{region} 내 {industry} 업종은 전체 상가의 {conc:.1f}%로 일정 수준의 수요와 경쟁이 동시에 확인됩니다."
    else: competition, comp_comment = "**낮음** 🟢", f"{region} 내 {industry} 업종은 전체 상가의 {conc:.1f}%로 상대적으로 점포 수가 적어 수요 검증이 필요합니다."
    best_comment = ""
    if best is not None:
        best_comment = f"""
**추천 검토 입지**  
창업 투자 점수 기준 1위 행정동은 **{best['adongNm']}**입니다.  
- 창업 투자 점수: **{best['창업투자점수']}점**
- 관심 업종 점포 수: **{int(best['관심업종점포수']):,}개**
- 전체 점포 수: **{int(best['전체점포수']):,}개**
- 경쟁강도: **{best['경쟁강도']}**
"""
    return f"""
#### 1. Investment Thesis
창업은 보증금, 인테리어, 인건비, 재고비용이 선투입되는 **투자 의사결정**입니다. 본 분석은 광주 상가정보 공공데이터를 활용해, 주식 종목을 분석하듯이 업종과 입지를 점수화하는 AI Analyst 방식입니다.

#### 2. Market Demand
{comp_comment} 총 {total:,}개 상가 중 {industry} 점포는 {target:,}개로 집계됩니다. 광주 전체 업종 다양성은 {diversity}개 중분류로 확인됩니다.

#### 3. Competition Risk
밀집도 상위 행정동은 **{top_d}** 순으로 나타났습니다. 상위 지역은 수요가 검증된 곳이지만, 동시에 임대료와 경쟁점포 리스크가 클 수 있습니다.

#### 4. Investment Scoring
{best_comment}
창업 투자 점수는 **시장수요 35% + 경쟁완화 25% + 상권다양성 15% + 정책화폐 적합도 15% + 문화관광 연계성 10%**로 계산했습니다.

#### 5. Local Currency / Blockchain Extension
현재 데이터는 점포 수 기반 상권 데이터입니다. 향후 광주상생카드·온누리상품권 결제 데이터가 연계되면, 업종별 결제금액과 가맹점 수를 결합해 **점포당 소비 잠재력**을 산출할 수 있습니다. 이는 지역화폐 데이터를 단순 결제수단이 아니라 지역상권의 데이터 자산으로 활용하는 방식입니다.

#### 6. Action Recommendation
> {region} {industry} 시장의 경쟁강도는 {competition} 수준입니다. 신규 창업자는 상위 밀집지에 바로 진입하기보다, 창업 투자 점수가 높고 경쟁강도가 과도하지 않은 행정동을 중심으로 현장조사·임대료·유동인구를 추가 확인하는 전략이 필요합니다.

---
*소상공인시장진흥공단 2026년 3월 상가정보 실데이터 기반 분석입니다. 매출액·임대료·유동인구는 포함되지 않아 창업 최종 결정에는 추가 검증이 필요합니다.*
"""

for key, val in [("analyzed", False),("ai_report", ""),("df_all", None),("df_target", None),("summary", {}),("data_source", ""),("sido_saved", ""),("industry_saved", ""),("score_df", None),("industry_score_df", None)]:
    if key not in st.session_state: st.session_state[key] = val

st.markdown("""
<div class="main-header"><h1 style="margin:0;font-size:1.8rem;">📈 Gwangju Startup Investment AI Analyst</h1><p style="margin:6px 0 0;opacity:.9;">광주 상가정보 공공데이터 기반 · 소상공인 창업 투자 점수 · AI Analyst Report 자동화</p></div>
""", unsafe_allow_html=True)
st.markdown("""<span class="data-badge">📊 소상공인시장진흥공단 상가정보</span><span class="data-badge">🏛️ 공공데이터포털</span><span class="data-badge">📈 창업 투자 의사결정</span><span class="data-badge">🤖 AI Analyst Report</span><span class="data-badge">💳 지역화폐 확장 가능</span>""", unsafe_allow_html=True)
st.markdown("""<div class="insight-box"><b>수업 연계 포인트</b><br>본 프로젝트는 창업을 하나의 <b>투자 의사결정</b>으로 해석합니다. 예비창업자는 보증금·인테리어·인건비·재고비용을 선투입하고 특정 지역과 업종을 선택합니다. 따라서 AI Analyst는 주식이나 비트코인만 분석하는 것이 아니라, 광주 상권 데이터를 기반으로 <b>업종·입지·경쟁강도·정책화폐 적합도</b>를 점수화해 창업 투자 판단을 보조할 수 있습니다.</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 설정")
    pub_api_key = st.text_input("공공데이터포털 API 키 (선택)", type="password", placeholder="없으면 내장 실데이터 파일로 동작")
    st.divider(); st.header("🔍 분석 조건")
    sido = st.selectbox("시/도 선택", SIDO_LIST)
    industry_name = st.selectbox("관심 업종", INDUSTRY_LIST)
    top_n = st.slider("행정동 TOP N", 5, 20, 10)
    analyze_btn = st.button("🚀 창업 투자 분석 시작", type="primary", use_container_width=True)
    st.divider(); st.caption("📊 소상공인시장진흥공단 2026.03 광주 상가정보 실데이터"); st.caption("광주광역시 75,325개 점포 데이터 기반")

if analyze_btn:
    with st.spinner(f"🔄 {sido} 전체 상가정보 데이터 로딩 중..."):
        df_all, total_all, data_source = get_data(pub_api_key, sido)
    if df_all.empty:
        st.error("데이터를 불러오지 못했습니다."); st.stop()
    df_target = df_all[df_all["indsMclsNm"] == industry_name].copy() if "indsMclsNm" in df_all.columns else pd.DataFrame()
    concentration = (len(df_target) / max(len(df_all), 1)) * 100
    dong_col = "adongNm" if "adongNm" in df_all.columns else None
    top_districts_str = "데이터 없음"
    if not df_target.empty and dong_col:
        top5 = df_target.groupby(dong_col).size().sort_values(ascending=False).head(5)
        top_districts_str = ", ".join([f"{k}({v}개)" for k, v in top5.items()])
    industry_diversity = df_all["indsMclsNm"].nunique() if "indsMclsNm" in df_all.columns else 0
    score_df, industry_score_df = calc_dong_scores(df_all, industry_name), calc_industry_scores(df_all)
    st.session_state.analyzed, st.session_state.ai_report = True, ""
    st.session_state.df_all, st.session_state.df_target, st.session_state.data_source = df_all, df_target, data_source
    st.session_state.sido_saved, st.session_state.industry_saved = sido, industry_name
    st.session_state.score_df, st.session_state.industry_score_df = score_df, industry_score_df
    st.session_state.summary = {"region":sido,"industry":industry_name,"total_stores":len(df_all),"target_stores":len(df_target),"concentration":concentration,"top_districts":top_districts_str,"industry_diversity":industry_diversity,"total_all":total_all}

if not st.session_state.analyzed:
    c1,c2,c3 = st.columns(3)
    with c1: st.info("**Before**\n\n예비창업자는 네이버 지도, 부동산 중개인 의견, 주변 체감, 지인 추천으로 창업지를 판단합니다.")
    with c2: st.success("**After**\n\nAI가 광주 상가정보를 분석해 업종별 경쟁강도, 행정동별 밀집도, 창업 투자 점수, 리스크 요인을 자동 리포트로 제공합니다.")
    with c3: st.warning("**Investment View**\n\n창업을 투자로 보고, 시장수요·경쟁완화·상권다양성·정책화폐 적합도·문화관광 연계성을 점수화합니다.")
    st.divider(); st.markdown("### 🧭 창업 투자 점수 산식")
    st.markdown("""
| 지표 | 가중치 | 의미 |
|---|---:|---|
| 시장수요 점수 | 35% | 해당 업종 점포 수가 일정 수준 존재하는지 |
| 경쟁완화 점수 | 25% | 특정 행정동에 과밀하지 않은지 |
| 상권다양성 점수 | 15% | 주변 업종이 다양해 복합 소비가 가능한지 |
| 정책화폐 적합도 | 15% | 광주상생카드·온누리상품권과 맞는 생활밀착 업종인지 |
| 문화관광 연계성 | 10% | 동명동·충장로·양림동 등 광주 문화상권과의 적합성 |
""")
    st.markdown("### 🗂️ 활용 데이터 출처")
    st.markdown("""
| 데이터 | 제공기관 | 기준일 | 활용 |
|--------|---------|--------|------|
| 상가(상권)정보 파일데이터 | 소상공인시장진흥공단 | 2026.03 | 광주 점포 수, 업종, 행정동, 주소 |
| 광주상생카드·온누리상품권 결제 데이터 | 향후 연계 대상 | - | 실제 소비금액·점포당 소비 잠재력 고도화 |
| 지역화폐 가맹점/결제 OpenAPI | 향후 연계 대상 | - | 가맹점 수, 업종별 경쟁강도 보완 |
""")
    st.info("👈 사이드바에서 관심 업종을 선택하고 **창업 투자 분석 시작**을 눌러주세요.")
else:
    df_all, df_target, summary, score_df, industry_score_df = st.session_state.df_all, st.session_state.df_target, st.session_state.summary, st.session_state.score_df, st.session_state.industry_score_df
    sido_saved, industry_saved, concentration = st.session_state.sido_saved, st.session_state.industry_saved, summary["concentration"]
    dong_col = "adongNm" if "adongNm" in df_all.columns else None
    st.info(st.session_state.data_source)
    st.info(f"📍 **{sido_saved}** | 관심 업종: **{industry_saved}**")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("전체 상가 수", f"{len(df_all):,}개"); c2.metric(f"{industry_saved} 점포", f"{len(df_target):,}개"); c3.metric("업종 집중도", f"{concentration:.1f}%"); c4.metric("업종 다양성", f"{summary['industry_diversity']:,}개")
    st.divider()
    tab1,tab2,tab3,tab4,tab5 = st.tabs(["📍 지역별 분포","🏪 업종 현황","📈 창업 투자 점수","🤖 AI 투자 리포트","🔗 수업 연계"])
    with tab1:
        if dong_col:
            ca,cb = st.columns(2)
            with ca:
                st.markdown(f"#### 행정동별 전체 상가 TOP {top_n}"); d = df_all.groupby(dong_col).size().reset_index(name="점포수").sort_values("점포수", ascending=False).head(top_n)
                fig=px.bar(d,x=dong_col,y="점포수",text="점포수",color="점포수",color_continuous_scale="Blues"); fig.update_traces(textposition="outside"); fig.update_layout(xaxis_tickangle=-35,coloraxis_showscale=False,height=420,plot_bgcolor="white"); st.plotly_chart(fig,use_container_width=True)
            with cb:
                if not df_target.empty:
                    st.markdown(f"#### {industry_saved} 행정동별 분포 TOP {top_n}"); d2=df_target.groupby(dong_col).size().reset_index(name="점포수").sort_values("점포수", ascending=False).head(top_n)
                    fig2=px.bar(d2,x=dong_col,y="점포수",text="점포수",color="점포수",color_continuous_scale="Oranges"); fig2.update_traces(textposition="outside"); fig2.update_layout(xaxis_tickangle=-35,coloraxis_showscale=False,height=420,plot_bgcolor="white"); st.plotly_chart(fig2,use_container_width=True)
                else: st.warning(f"'{industry_saved}' 업종 데이터가 없습니다.")
    with tab2:
        ca,cb=st.columns(2)
        with ca:
            if "indsMclsNm" in df_all.columns:
                st.markdown("#### 업종 중분류별 점포 수 TOP 15"); inds=df_all.groupby("indsMclsNm").size().reset_index(name="점포수").sort_values("점포수", ascending=False).head(15)
                fig3=px.bar(inds,x="점포수",y="indsMclsNm",orientation="h",text="점포수",color="점포수",color_continuous_scale="Teal"); fig3.update_traces(textposition="outside"); fig3.update_layout(yaxis=dict(autorange="reversed"),coloraxis_showscale=False,height=480,plot_bgcolor="white"); st.plotly_chart(fig3,use_container_width=True)
        with cb:
            if "indsLclsNm" in df_all.columns:
                st.markdown("#### 업종 대분류 비중"); lrg=df_all.groupby("indsLclsNm").size().reset_index(name="점포수"); fig4=px.pie(lrg,names="indsLclsNm",values="점포수",color_discrete_sequence=px.colors.qualitative.Pastel); fig4.update_traces(textposition="inside",textinfo="percent+label"); fig4.update_layout(height=480,showlegend=False); st.plotly_chart(fig4,use_container_width=True)
        with st.expander("📋 상가 데이터 상위 500개"):
            cols=[c for c in ["bizesNm","indsLclsNm","indsMclsNm","adongNm","rdnAdr"] if c in df_all.columns]; rename={"bizesNm":"상호명","indsLclsNm":"대분류","indsMclsNm":"중분류","adongNm":"행정동","rdnAdr":"주소"}; st.dataframe(df_all[cols].head(500).rename(columns=rename),use_container_width=True)
    with tab3:
        st.markdown("### 📈 행정동별 창업 투자 점수"); st.caption("시장수요·경쟁완화·상권다양성·정책화폐 적합도·문화관광 연계성을 결합한 발표용 분석 지표입니다.")
        if score_df is not None and not score_df.empty:
            top_score=score_df.head(top_n); fig_score=px.bar(top_score,x="창업투자점수",y="adongNm",orientation="h",text="창업투자점수",color="창업투자점수",color_continuous_scale="Greens",hover_data=["관심업종점포수","전체점포수","업종다양성","경쟁강도"]); fig_score.update_traces(textposition="outside"); fig_score.update_layout(yaxis=dict(autorange="reversed"),coloraxis_showscale=False,height=520,plot_bgcolor="white"); st.plotly_chart(fig_score,use_container_width=True)
            view=score_df[["adongNm","창업투자점수","관심업종점포수","전체점포수","업종다양성","시장수요점수","경쟁완화점수","상권다양성점수","정책화폐적합도","문화관광연계성","경쟁강도"]].rename(columns={"adongNm":"행정동"}); st.dataframe(view,use_container_width=True)
        st.markdown("### 🏪 광주 전체 업종별 투자 관점 점수")
        if industry_score_df is not None and not industry_score_df.empty: st.dataframe(industry_score_df.head(20),use_container_width=True)
    with tab4:
        st.markdown("### 🤖 AI 창업 투자 리포트"); st.caption("상권분석 결과를 투자 리포트 형식으로 자동 정리합니다.")
        st.markdown(f"""**📊 기본 분석 요약**
- **분석 지역**: {sido_saved} | **관심 업종**: {industry_saved}
- **{industry_saved} 비중**: {concentration:.1f}% ({len(df_target):,}개 / {len(df_all):,}개)
- **밀집 행정동 TOP 5**: {summary['top_districts']}
- **업종 다양성**: {summary['industry_diversity']}개 중분류
""")
        if st.session_state.ai_report: st.markdown(f'<div class="insight-box">{st.session_state.ai_report}</div>', unsafe_allow_html=True)
        else:
            if st.button("🚀 AI 투자 리포트 생성", type="primary"):
                with st.spinner("분석 중..."): report = generate_ai_analysis(summary, score_df)
                st.session_state.ai_report = report; st.markdown(f'<div class="insight-box">{report}</div>', unsafe_allow_html=True)
        st.divider(); st.info("""**📌 데이터 출처 및 한계**
- 소상공인시장진흥공단 상가(상권)정보 2026년 3월 기준 광주 데이터
- 매출액·임대료·유동인구는 포함되지 않으며, 점포 수 기반 경쟁 밀도 분석입니다
- 광주상생카드·온누리상품권 결제 데이터가 연계되면 실제 소비금액 기반 분석으로 고도화할 수 있습니다
""")
    with tab5:
        st.markdown("### 🔗 수업 내용과의 연결")
        st.markdown("""<div class="good-box"><b>1. AI Analyst Workflow</b><br>데이터 수집 → 구조화 → 지표 산출 → 점수화 → 리포트 자동화 흐름을 구현했습니다.</div><div class="good-box"><b>2. Investment Decision</b><br>창업 입지와 업종 선택을 투자 의사결정으로 해석했습니다. 주식 종목 대신 광주 상권·업종을 분석 대상 자산으로 본 것입니다.</div><div class="good-box"><b>3. Valuation / Scoring</b><br>점포 수, 경쟁강도, 상권다양성, 정책화폐 적합도, 문화관광 연계성을 결합해 창업 투자 점수를 산출했습니다.</div><div class="good-box"><b>4. Blockchain / Local Currency Extension</b><br>광주상생카드·온누리상품권 결제 데이터와 결합하면 실제 소비금액 기반의 점포당 소비 잠재력 분석으로 확장할 수 있습니다.</div>""", unsafe_allow_html=True)
        st.markdown("### Before vs After")
        st.markdown("""
| 구분 | 기존 방식 | AI Analyst 적용 후 |
|---|---|---|
| 창업 입지 판단 | 네이버 지도, 중개인 의견, 체감 | 행정동별 점포 수·경쟁강도 자동 분석 |
| 업종 선택 | 유행 업종 또는 개인 경험 | 업종별 투자 점수와 정책화폐 적합도 비교 |
| 리스크 확인 | 현장 방문 후 수작업 판단 | 경쟁과밀 지역과 수요검증 필요 지역 자동 표시 |
| 보고서 작성 | 사람이 직접 정리 | AI 창업 투자 리포트 자동 생성 |
""")

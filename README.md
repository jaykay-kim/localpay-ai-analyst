# 🏪 AI 창업 상권분석 플랫폼

소상공인시장진흥공단 실데이터 기반 · AI 입지 분석 · 업종별 경쟁 현황

## 주요 기능

- 📍 **지역 × 업종 분석** — 시/도 + 관심 업종 선택 시 행정동별 점포 수·경쟁 밀도 자동 분석
- 📊 **실데이터 기반** — 소상공인시장진흥공단 상가정보 API (국세청·카드사 기반 전국 데이터)
- 🤖 **AI 창업 제언** — Claude AI가 블루오션 입지, 경쟁 리스크, 창업 적합도 분석
- 🗺️ **Plotly 인터랙티브 차트** — 행정동별 분포, 업종 비중, TOP N 시각화

## 활용 데이터

| 데이터 | 제공기관 | 링크 |
|--------|---------|------|
| 상가(상권)정보 API | 소상공인시장진흥공단 | https://www.data.go.kr/data/15012005/openapi.do |
| 전국지역화폐가맹점 | 행정안전부 | https://www.data.go.kr/data/15100062/standard.do |
| 온누리상품권 가맹점 | 소상공인시장진흥공단 | https://www.data.go.kr/data/3060079/fileData.do |

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

## API 키 준비

### 1. 공공데이터포털 API 키 (필수)
1. [data.go.kr](https://www.data.go.kr) 회원가입
2. 검색창에 **'소상공인시장진흥공단 상가정보'** 검색
3. 오픈API → 활용신청 → 개발계정 자동승인 (약 1시간 소요)

### 2. Anthropic API 키 (AI 분석용, 선택)
- [console.anthropic.com](https://console.anthropic.com) 에서 발급

## Streamlit Cloud 배포 시 Secrets 설정

```toml
# .streamlit/secrets.toml
PUBLIC_DATA_API_KEY = "발급받은 공공데이터 API 키"
ANTHROPIC_API_KEY = "sk-ant-..."
```

## 프로젝트 배경

본 플랫폼은 AI Analyst 수업 기말 발표 프로젝트로,
공공데이터 기반 소상공인 창업 지원 서비스의 가능성을 탐색합니다.

- 기존 지역화폐·온누리상품권 결제 데이터의 한계를 넘어
- 전국 단위 실제 상가정보를 활용한 상권 분석으로 확장
- AI를 통한 데이터 해석 및 창업 제언 자동화를 목표로 합니다.

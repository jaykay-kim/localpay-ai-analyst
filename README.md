# 💳 LocalPay AI Analyst

수원시 지역화폐 공공데이터 기반 소상공인 상권분석 플랫폼

## 주요 기능
- 📍 읍·면·동별 결제금액 분석
- 🏪 업종별 결제 현황 및 창업 참고 점수
- 👥 연령대 × 업종 히트맵 분석
- 🤖 Claude AI 기반 인사이트 리포트 자동 생성

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

## AI 리포트 사용
Anthropic API 키가 필요합니다. 앱 사이드바에서 입력하거나 환경변수로 설정하세요.
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## 데이터 출처
공공데이터포털 — 경기도 수원시 지역화폐 결제정보 (2025년 11월)

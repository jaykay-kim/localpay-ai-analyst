# LocalPay AI Analyst

지역화폐·온누리상품권 데이터 기반 소상공인 창업 상권분석 플랫폼 시연용 프로젝트입니다.

## 프로젝트 개요

본 프로젝트는 「블록체인과 투자, AI 애널리스트」 수업 기말발표용 프로토타입입니다.

온누리상품권과 지역화폐를 단순 결제수단이 아니라 지역상권의 소비 흐름을 보여주는 데이터 자산으로 보고, 예비창업자와 소상공인이 특정 지역을 입력하면 다음 정보를 자동 분석합니다.

- 지역별/동별 결제금액
- 업종별 결제금액 TOP
- 연령대별 소비패턴
- 이벤트 참여 여부에 따른 소비 차이
- 창업 기회 점수
- AI Analyst 형태의 자동 리포트

## 교수님 피드백 반영

기존 제안은 실제 온누리상품권 결제 데이터를 분석하는 방향이었으나, 실제 데이터는 정부·지자체·운영기관 승인과 개인정보 이슈로 확보가 어렵습니다.

따라서 본 최종 발표에서는 실제 내부 원천데이터가 아닌 비식별 샘플 데이터를 사용하여, 데이터가 확보되었을 때 어떤 AI 분석 자동화가 가능한지를 시연하는 프로토타입으로 범위를 조정했습니다.

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud 배포 방법

1. GitHub에 새 repository를 만듭니다.
2. 이 폴더의 파일을 업로드합니다.
   - `app.py`
   - `sample_localpay_data.csv`
   - `requirements.txt`
   - `README.md`
3. https://share.streamlit.io 에 접속합니다.
4. GitHub repository를 연결합니다.
5. Main file path에 `app.py`를 입력하고 Deploy를 누릅니다.

## 데이터 설명

`sample_localpay_data.csv`는 발표 시연용 비식별 샘플 데이터입니다.

| 컬럼 | 설명 |
|---|---|
| month | 결제 월 |
| region | 시/군/구 |
| district | 읍/면/동 |
| industry | 업종 |
| age_group | 연령대 |
| payment_amount | 결제금액 |
| transaction_count | 거래건수 |
| avg_ticket | 평균 객단가 |
| event_participation | 이벤트 참여 여부 |
| revisit_rate | 재방문율 |
| merchant_count | 가맹점 수 추정 |

## 발표 시연 흐름

1. 지역을 선택합니다.
2. 총 결제금액, 거래건수, 평균 객단가를 확인합니다.
3. 업종별 결제금액 TOP을 확인합니다.
4. 연령대별 소비패턴을 확인합니다.
5. 창업 기회 점수로 추천 업종을 확인합니다.
6. AI Analyst Report를 자동 생성합니다.

## 한계

본 앱은 실제 투자 또는 창업 의사결정을 대체하지 않습니다. 실제 사업화 단계에서는 실제 온누리상품권·지역화폐 결제 데이터, 임대료, 유동인구, 경쟁점포 수, 배후세대, 인허가 조건, 원가구조 및 마진율 등의 추가 검토가 필요합니다.

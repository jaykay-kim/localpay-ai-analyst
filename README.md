# LocalPay AI Analyst - Real Data Update

실제 수원시 지역화폐 결제정보 공공데이터를 기본 탑재한 Streamlit 시연 앱입니다.

## 기본 데이터

- 공공데이터포털: 경기도 수원시_지역화폐 결제 정보_20260120.csv
- 기준년월: 2025년 11월
- 포함 정보: 시군구명, 읍면동명, 성별, 연령대, 업종명, 결제건수, 결제금액
- 앱 업로드용 컬럼으로 변환하여 `sample_localpay_data.csv`에 탑재

## API 연계 결과

- 경기지역화폐 가맹점 현황 OpenAPI
- 조회 조건: SIGUN_NM=수원시
- list_total_count: 37,369개

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 발표 설명

본 앱은 실제 수원시 지역화폐 결제정보를 사용해 업종별 결제금액, 연령대별 소비패턴, 읍면동별 결제규모를 분석합니다.  
가맹점 수는 경기도 지역화폐 가맹점 현황 API에서 조회한 수원시 전체 가맹점 수 37,369개를 반영했습니다.

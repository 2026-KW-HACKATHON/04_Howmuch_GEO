# Overview

**Backend** 에서는 **FastAPI** 를 사용. (배포 : **Render**)

주요 사용처는, **V-World API** 를 통한 여러 지도 관련 데이터의 사용에 있음.

**prefix** 는 **/api/v1**

추가 유지보수를 이어나가면서 버전을 바꿀 수 있게 함으로서, 엔드포인트의 구분을 둠.

# /api/v1/cadastral/

- 역할 : 프론트에서 **Kakao SDK API** 로 만든 지도의 현재 렌더링 **bound** 좌표를 통하여 해당 좌표 내의 필지 전부 조회

- **API** 로직 구조도:

<img width="1062" height="760" alt="_api_v1_cadastral 엔드포인트 로직 drawio (1)" src="https://github.com/user-attachments/assets/f55ff4c3-7971-4518-bc72-df2b3ff736da" />

```python
@router.post("/cadastral/")
async def get_vworld_cadastral(request: CadastralRequest):
```

# /api/v1/zone/

- 역할 : 필지 정보를 바탕으로 프론트에서 호출. 필지에는 고유한 **pnu** 번호가 존재함. 해당 **pnu** 정보가 위에서 얻어질 수 있는데, 이를 통하여 프론트에서 선택한  모든 필지의 **pnu** 에 대한 **V-World API** 를 통한 추가 정보를 반환.

  - **fetch_land_price_per_m2()** : 필지면적, 필지용도, 지목 반환.

  - **fetch_land_characteristics()** : 필지당 공시지가 반환.

- 위의 정보들을 토대로, 고정값들은 그대로 불러오며, 여러 수식 계산이 일어나며, 결국 프론트 슬라이더 구성에 필요한 값들을 반환.
  
- **API** 로직 구조도:
<img width="2792" height="1172" alt="_api_v1_zone 엔드포인트 로직 drawio (1)" src="https://github.com/user-attachments/assets/79404f1b-9c89-49ba-9554-c564956369dd" />

```python
@router.post(
    "/zone",
    summary="구역 선택 및 요약 집계"
)
async def get_zone(req: ZoneRequest):
```

# /api/v1/contribution/

- 역할 : 구성된 슬라이더를 조작하여 얻은 정보를 포함한, 최종 정보들을 바탕으로 최종 분담금 계산.

- **API** 로직 구조도:

<img width="1806" height="1240" alt="_api_v1_contribution 엔드포인트 로직 drawio (1)" src="https://github.com/user-attachments/assets/4c8f2e01-eb81-4e64-aee3-c2a95f4dbbe2" />

```python
@router.post(
    "/contribution",
    summary="조합원 개인 분담금 및 사업성 계산")
async def get_contribution(req: ContributionRequest):
```

# 추가 정보

- **V-World** 호출상 테스트 과정에서, 만약 로컬환경에서의 **API** 호출은 작동하지만, **Codespace** 나 **Render** 과 같은 클라우드상의 호출은 차단되는 현상 관측. 클라우드 개발 과정에서 임의로 연결 실패에서는 사전정의 데이터 사용 및 콘솔 출력으로 처리.

- **Pydantic** 을 이용한 **Request** 스키마의 정의로 엄격한 검증 실행.

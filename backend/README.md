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
async def get_contribution(req: ContributionRequest, request: Request):
```

# 일일 크레딧

- `GET /api/v1/user/credits` : 로그인한 사용자의 남은 크레딧과 다음 충전 시각을 반환.
- `POST /api/v1/user/credits/reset` : 로그인한 사용자의 당일 크레딧을 5개로 초기화. 프로필 메뉴에서 실행.
- `POST /api/v1/zone` : 로그인 필수. 구역 분석 성공 시 크레딧 차감용 토큰을 발급하지만, 이 단계에서는 차감하지 않음.
- `POST /api/v1/contribution` : 로그인 필수. 계산과 응답 검증이 모두 성공한 경우 토큰당 크레딧 1개를 차감.
- `POST /api/v1/zone/type` : 로그인 필수, 크레딧 없음. 필지를 고르는 즉시 사업 유형(재개발/재건축)만 미리 판정한다 (`{project_type, project_type_reason}`, /zone 과 같은 규칙·캐시).
- 사용자별 하루 5개가 지급되며, 매일 한국 시간 자정에 자동 충전. 잔액은 Redis에 사용자 ID와 날짜를 조합해 저장.
- 구역 분석 후 발급된 동일 토큰으로 실행되는 슬라이더 재계산은 추가 크레딧을 사용하지 않음.
- 분담금 계산 또는 응답 검증이 실패하면 크레딧을 차감하지 않음.

# 추가 정보

- **Pydantic** 을 이용한 **Request** 스키마의 정의로 엄격한 검증 실행.

# 분담금 계산 엔진 (AI 파트)

계산식·근거·흐름도는 저장소 루트 `PIPELINE.md` 에 있다. 여기에는 API 필드와 운영에 필요한 것만 적는다.

## 환경 변수

| 변수 | 용도 | 없을 때 |
|---|---|---|
| `BLDRGST_API_KEY` | 건축HUB 건축물대장 (표제부·전유공용) — 종전자산 건물분, 조합원 수 실측 | 건물분 0 (나대지로 계산) + 경고 |
| `MOLIT_API_KEY` | 국토부 아파트 실거래 — 분양가 시점 보정 | 보정 없이 사례 그대로 |
| `VWORLD_API_KEY` · `VWORLD_DOMAIN` · `PROXY_URL` | 토지특성(`/getLandCharacteristics`)·토지소유정보(`/getPossessionAttr`) | 용도지역 2종 가정 / 소유구분 미확인 |

## /api/v1/zone 응답 (엔진 필드)

- **far_base** : 정비계획 상한용적률. 도시정비법 제54조 임대(초과분의 50%)가 이 값을 넘는 법적상한 구간에만 붙는다
- **sliders.floor_area_ratio** : 노드 슬라이더. `options`(값) · `tiers`(기준/허용/상한/법적상한) · `contributions`(노드별 토지 공공기여 비율) · `min_contribution`(종상향 최소 공공기여, 순부담)
- **sliders.project_period_years** : 손잡이 두 개(따로 움직임). `value: [분담금 고시일, 최종 인가]`, `range: true`, `gap: {value 8, min 3(공사기간 중앙값), max 트랙 폭}`, `ticks`
- **sliders.parking_margin** : 주차 여유율 (실제 ÷ 법정 주차대수)
- **sliders.member_price_ratio** : 조합원 분양가 비율. `auto: true`, `value: null` 로 내려간다 — 값은 `/contribution` 이 역산해 돌려준다
- **project_type** · **project_type_reason** : 사업 유형 판정 (아파트 단지만 → 재건축, 아파트 외 사유 필지 포함 → 재개발). 선택한 필지 칸 옆 배지
- **reconstruction** : 재건축 단지 정보 (세대수 · 단지 대지 · 현황용적률 · 공동주택가격 합계·호수·전용면적별 호당 값). 재개발이면 null
- **business_correction** : 사업성 보정계수 (서울시 평균 공시지가 ÷ 구역 '대' 필지 평균, 1.00~2.00)
- **upzoning** : 종상향 판정 (`base_zoning` 원래 용도지역 평균 단계, `steps`, `contribution_ratio` 최소 공공기여율)
- **prior_asset.parcels[]** : 필지 원자료. `/contribution` 에 그대로 돌려보낸다. `cost_index`(재조달원가 상대지수) · `owner_type`(소유구분) ·
  `housing_kind`·`housing_price`·`housing_units`·`housing_area_prices` (주택 공시가격 — 있으면 종전자산 = 공시가격 ÷ 현실화율) 포함
- **prior_asset.housing_total** · **housing_parcel_count** : 주택 공시가격으로 잡은 몫

## /api/v1/contribution 요청 (엔진 필드)

- **sliders.project_period_years** : `[고시일, 최종 인가]` (숫자 하나면 고시일로 보고 기본 간격 8년을 더한다. 최종 인가는 고시일 + 3년 이상으로 맞춘다)
- **project_type** · **reconstruction** : `/zone` 판정 그대로. 재건축이면 의무 임대 0 · 종전자산 = 공동주택가격 ÷ 69% · 내 종전 = 내 전유면적의 호당 공시가격
- **sliders.member_price_ratio** : `null`(또는 키 없음) = 자동 — ① 관리처분 확정 비례율이 100% 가 되도록 역산한다. 숫자 = 그 값 그대로 (사용자가 손잡이를 움직임)
- **public_contribution_ratio** : 고른 용적률 노드의 공공기여 비율 (`sliders.floor_area_ratio.contributions` 에서)
- **contribution_mix** : 공공기여 기부면적 비율(%) `{land, public_rental, cash}` — 세부 설정 「적용」 값. 합이 100 이 아니어도 비율대로 맞추고, 현금은 맞춘 뒤 50% 까지 (넘으면 잘라서 나머지를 토지·공공임대에 나눈다). 합 0 이면 토지 100%
- **contribution_method** : (`contribution_mix` 가 없을 때만) 버튼 프리셋 이름 `land`(토지 100) · `land_cash`(토지 50 + 현금 50) · `land_rental`(토지 50 + 공공임대 50)
- **min_contribution_ratio** : 종상향 최소 공공기여 (`sliders.floor_area_ratio.min_contribution`). 토지가 아닌 방식의 순부담 하한
- **parcel_valuations** : `/zone` 의 `prior_asset.parcels` 그대로
- **unit_mix** · **rental_exclusive_area_m2** · **owner.pnu** · **owner.exclusive_area_m2** : 세부 설정 (없으면 기본값)

## /api/v1/contribution 응답 (엔진 필드)

- **unit_contributions[]** : 평형별 분담금 (준공 정산 기준)
- **timeline** : 사업 일정과 시점별 값
  - `mgmt_ym`(고시일) · `start_ym`(착공) · `complete_ym`(준공) · `prior_ym`(종전자산 평가)
  - `stages[]` : ① 관리처분 확정 ② 분양·임대 시점 반영 ③ 공사비 물가변동 ④ 비물가 초과 증액(= 준공 정산)
  - `member_price_per_pyeong`(조합원 분양가, 고시일 확정) · `cost_contract_per_pyeong` → `cost_final_per_pyeong` · `escalation_*`
  - `project_type` · `prior_basis` (종전자산을 잡은 방법)
  - `member_price_mode`(auto/manual) · `member_price_ratio`(계산에 쓴 비율) · `member_price_ratio_solved`(범위 제한 전 역산 값) · `member_price_ratio_bound`(범위 끝에 걸리면 min/max) · `member_price_target_rate`(100)
  - `net_site_area_m2` : 공공기여 뒤 건축 대지
  - `contribution_*` : 공공기여 — `mix`(적용된 비율 %, 합 100) · `total_m2`(기부면적, 환산 포함) · `land_ratio`(실제로 뗀 토지 비율) · `cash`(만원)·`cash_area_m2`(환산부지) · `rental_count`(기부채납 공공임대 세대) · `site_value_per_m2`(부지가액 = 공시지가 × 2, 만원/㎡) · `note`(공공기여 칸 아래 안내 문장)
  - `rental_*` : 임대 인수 — 의무 임대 기본형건축비(지상+지하) × 80% (고시·확정·정산 단가), 완화분 `rental_uplift_*` 표준건축비·지하 63% (고시·정산 단가), 의무/완화분 세대수, 임대 몫 지하층면적, 의무 임대 부속토지 단가·면적, 건물(의무·완화분)·토지 수입
- **prior_asset_detail** : 구역 토지분·건물분, r_구역, ρ(개인화 배수)
- **member_count_range** : 조합원 수 슬라이더 범위 (분양 세대수 상한 반영)

## 캐시 (Redis)

| 키 | 내용 | TTL |
|---|---|---|
| `land:{pnu}` | 토지특성 | 7일 |
| `bld2:{pnu}` | 건축물대장 표제부 요약 (2026-10-07 층수·기타용도 추가로 키 변경) | 30일 |
| `own3:{pnu}` | 토지소유정보 (모든 필지, 동시 4개 조회, 앞 20행 표본 — 사유 지분이 있으면 사유, 1997-01-15 전 소유자 수) | 30일 |
| `aptc:{pnu}` | 아파트 단지 (총괄표제부 세대수·용적률 산정 연면적·부속지번) — 아파트 필지만 | 30일 |
| `aptp:{pnu}` | 공동주택가격 요약 (올해, 없으면 작년) — 공동주택 필지 | 30일 |
| `hsp:{pnu}` | 개별주택가격 (올해, 없으면 작년) — 단독·다가구 필지 | 30일 |
| `exc:{pnu}` | 전유면적 합계 (내 필지 지정 시) | 30일 |
| `trades:{lawd}:{ym}` | 국토부 실거래 | 1일 |

## 규칙 유지보수

서울시 기본계획·조례 숫자(4단 용적률, 종상향 공공기여율, 보정계수 범위, 서울시 평균 공시지가 등)는
`AI/engine/data/policy_rules.json` 에 있다. 바뀌면 이 파일만 고치고 백엔드를 다시 띄운다.
공고·건의 단계 변경은 `pending` 에 두고 뉴스로 감시한다 (사람이 기사를 확인한 뒤 반영).

```
python -m AI.maintenance.policy_watch                     # 카카오 웹검색 (KAKAO_API_KEY)
python -m AI.maintenance.policy_watch --from-file a.json  # 저장한 기사 목록으로
python -m AI.maintenance.policy_watch --list
python -m AI.maintenance.policy_watch --apply <id> --source <기사 URL>
```


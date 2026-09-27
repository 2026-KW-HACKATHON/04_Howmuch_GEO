#Engine 파일 기본값
ENGINE_DEFAULTS = {
    "underground_ratio": 0.6,            # 지하 연면적 / 지상 연면적
    "community_ratio": 0.05,             # 커뮤니티·부대복리 비율
    "housing_supply_efficiency": 0.97,   # 주택 연면적 → 공급면적 전환율
    "commercial_price_ratio": 1.2,       # 상가 분양가 = 일반분양가 × 배수
    "base_rental_ratio": 0.10,           # 임대 의무비율 (연면적 기준, 서울 주거지역, 법정)
    "uplift_rental_share": 0.5,          # 용적률 상향 완화분 중 임대 비율 (법정 상한 0.75)
    "rental_supply_area_m2": 59.0,       # 임대 1세대 공급면적
    "rental_price_per_unit": 30_000,     # 임대 1세대 인수가(만원)
    "avg_prior_asset": 45_000,           # 조합원 평균 종전자산(만원)
    "appraisal_ratio": 1.3,              # 감정평가액 / 공시가격 보정률
}

#ProjectParams 전용 제외 대상을 뺀 기본값
ENGINE_DEFAULTS_FOR_PARAMS = {
    "underground_ratio": 0.6,
    "community_ratio": 0.05,
    "housing_supply_efficiency": 0.97,
    "commercial_price_ratio": 1.2,
    "base_rental_ratio": 0.10,
    "uplift_rental_share": 0.5,
    "rental_supply_area_m2": 59.0,
    "rental_price_per_unit": 30_000,
    "avg_prior_asset": 45_000,
}

#UnitMix 사전 기본값
UNIT_MIX = [
    {"name": "59", "exclusive_area_m2": 59.0, "supply_area_m2": 82.64, "share": 0.31},
    {"name": "84", "exclusive_area_m2": 84.0, "supply_area_m2": 112.40, "share": 0.56},
    {"name": "114", "exclusive_area_m2": 114.0, "supply_area_m2": 148.76, "share": 0.13},
]

#조합원 수 슬라이더 범위 계수
#  기본값 = 세대수(전원 참여, 가장 보수적) / 하한 = 조합설립 동의율 법정 최소 75%
#  상한 = 재건축은 세대수(1세대=1소유권), 재개발은 나대지·도로지분·무허가 소유자까지 포함
MEMBER_COUNT_MIN_RATIO = 0.75
MEMBER_COUNT_MAX_RATIO = {"재건축": 1.0, "재개발": 1.25}

#세대수 자료가 없을 때 조합원 수 슬라이더 하한 (분양 세대수 기준)
#  기존 세대수를 모르면 동의율 기준을 쓸 수 없어서, 분양 세대수 안에서 넓게 탐색하게 둔다
MEMBER_COUNT_UNKNOWN_MIN_RATIO = 0.3

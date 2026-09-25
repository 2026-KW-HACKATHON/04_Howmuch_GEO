#Engine 파일 기본값
ENGINE_DEFAULTS = {
    "underground_ratio": 0.6,            # 지하 연면적 / 지상 연면적
    "community_ratio": 0.05,             # 커뮤니티·부대복리 비율
    "housing_supply_efficiency": 0.97,   # 주택 연면적 → 공급면적 전환율
    "commercial_price_ratio": 1.2,       # 상가 분양가 = 일반분양가 × 배수
    "rental_ratio": 0.15,                # 임대 비율 (면적 기준)
    "rental_supply_area_m2": 59.0,       # 임대 1세대 공급면적
    "rental_price_per_unit": 30_000,     # 임대 1세대 인수가(만원)
    "avg_prior_asset": 35_000,           # 조합원 평균 종전자산(만원)
    "appraisal_ratio": 1.3,              # 감정평가액 / 공시가격 보정률
}

#ProjectParams 전용 제외 대상을 뺀 기본값
ENGINE_DEFAULTS_FOR_PARAMS = {
    "underground_ratio": 0.6,
    "community_ratio": 0.05,
    "housing_supply_efficiency": 0.97,
    "commercial_price_ratio": 1.2,
    "rental_ratio": 0.15,
    "rental_supply_area_m2": 59.0,
    "rental_price_per_unit": 30_000,
    "avg_prior_asset": 35_000,
}

#UnitMix 사전 기본값
UNIT_MIX = [
    {"name": "59", "exclusive_area_m2": 59.0, "supply_area_m2": 82.64, "share": 0.31},
    {"name": "84", "exclusive_area_m2": 84.0, "supply_area_m2": 112.40, "share": 0.56},
    {"name": "114", "exclusive_area_m2": 114.0, "supply_area_m2": 148.76, "share": 0.13},
]
# 지도에서 고른 필지 목록 → 구역 단위 입력값(ZoneSummary)
# 백엔드가 V-World/토지특성 API 로 받은 필지 정보를 ParcelInfo 리스트로 넘겨주면
# 여기서 합산해서 ProjectParams 에 넣을 값과 슬라이더 범위를 만든다.
from AI.engine.schema import ParcelInfo, ZoneSummary

# 용도지역 → (조례 기준 용적률, 법적상한용적률) %
# 기준: 서울시 도시계획조례 제55조 제1항 / 상한: 국토계획법 시행령 제85조
# 정비사업은 도시정비법 제54조에 따라 심의를 거쳐 법적상한용적률까지 완화 가능
# ※ 완화분의 일정 비율(최대 75%)은 국민주택규모 임대로 공급해야 함 → calc_allocation 에서 반영
FAR_TABLE = {
    "제1종전용주거지역": (100, 100),
    "제2종전용주거지역": (120, 150),
    "제1종일반주거지역": (150, 200),
    "제2종일반주거지역": (200, 250),
    "제3종일반주거지역": (250, 300),
    "준주거지역":       (400, 500),
}

# 종전자산 합산에서 제외할 지목 (국공유지 성격)
EXCLUDED_LAND_CATEGORY = {"도로", "구거", "하천", "공원", "제방"}

# 시군구 코드(PNU 앞 5자리) → 이름
# 우선 노원구와 인접 자치구만. 범위가 넓어지면 행정표준코드 전체를 불러오는 방식으로 바꿀 것
SIGUNGU_NAME = {
    "11350": "노원구",
    "11305": "강북구",
    "11320": "도봉구",
    "11230": "동대문구",
    "11260": "중랑구",
    "11215": "광진구",
    "11110": "종로구",
    "11140": "중구",
    "11380": "은평구",
    "11410": "서대문구",
    "11440": "마포구",
    "11170": "용산구",
    "11200": "성동구",
    "11290": "성북구",
}


# V-World 응답의 용도지역 문자열을 FAR_TABLE 키와 맞춤 (공백/줄바꿈 제거)
def normalize_zoning(zoning: str) -> str:
    return "".join(zoning.split()) if zoning else ""


# PNU 앞 5자리 = 시군구 코드 (예: 1135010300100010000 → "11350")
def sigungu_code(pnu: str) -> str:
    return pnu[:5] if pnu and len(pnu) >= 5 else ""


# 구역의 시군구 이름. 선택 면적 중 가장 큰 면적이 속한 시군구를 고르며, 표에 없으면 None
def district(parcels: list[ParcelInfo]) -> str | None:
    area_by_code: dict[str, float] = {}
    for parcel in parcels:
        code = sigungu_code(parcel.pnu)
        if not code:
            continue
        area = parcel.area_m2 if parcel.area_m2 and parcel.area_m2 > 0 else 0.0
        area_by_code[code] = area_by_code.get(code, 0.0) + area

    if not area_by_code:
        return None

    #면적이 가장 큰 시군구를 대표로 사용 (면적을 모두 모르면 코드 순서로 결정됨)
    top_code = max(area_by_code, key=lambda c: area_by_code[c])
    return SIGUNGU_NAME.get(top_code)


# 필지 목록 → 구역 집계
def build_zone_summary(parcels: list[ParcelInfo]) -> ZoneSummary:
    if not parcels:
        raise ValueError("선택된 필지가 없습니다.")

    warnings = []

    site_area_m2 = 0.0      # 구역 면적 합계
    land_value_total = 0.0  # 종전자산 추정 기초 (만원)
    far_min_weighted = 0.0  # 면적 가중 기준 용적률
    far_max_weighted = 0.0  # 면적 가중 상한 용적률
    far_area_m2 = 0.0       # 용적률을 알 수 있는 필지 면적 합계
    zonings = set()

    for parcel in parcels:
        # 면적이 없는 필지는 합산에서 제외 (토지특성 API 미조회 등)
        if parcel.area_m2 is None or parcel.area_m2 <= 0:
            warnings.append(f"면적이 없는 필지를 제외했습니다: {parcel.pnu}")
            continue

        site_area_m2 += parcel.area_m2

        # 종전자산 기초 : 도로·구거 등 국공유지는 조합원 자산이 아니므로 제외
        if parcel.land_category in EXCLUDED_LAND_CATEGORY:
            pass
        else:
            # 공시지가는 원/㎡ → 만원 환산
            land_value_total += parcel.area_m2 * parcel.land_price_per_m2 / 10_000

        # 용적률 : 용도지역별 값을 면적으로 가중평균
        zoning = normalize_zoning(parcel.zoning)
        zonings.add(zoning)
        far_range = FAR_TABLE.get(zoning)
        if far_range is None:
            warnings.append(f"용적률 표에 없는 용도지역입니다: {parcel.zoning} ({parcel.pnu})")
            continue

        far_min_weighted += parcel.area_m2 * far_range[0]
        far_max_weighted += parcel.area_m2 * far_range[1]
        far_area_m2 += parcel.area_m2

    if site_area_m2 <= 0:
        raise ValueError("면적이 있는 필지가 하나도 없습니다.")

    # 용도지역을 하나도 못 읽었으면 슬라이더 범위를 정할 수 없음
    if far_area_m2 <= 0:
        raise ValueError("용도지역을 확인할 수 있는 필지가 없습니다.")

    far_min = far_min_weighted / far_area_m2
    far_max = far_max_weighted / far_area_m2

    if len(zonings) > 1:
        warnings.append(f"용도지역이 섞여 있어 면적 가중평균을 사용했습니다: {', '.join(sorted(zonings))}")

    #대표 시군구 : 공사비 등 예측 모듈에 넘길 지역
    region = district(parcels)
    codes = {sigungu_code(p.pnu) for p in parcels if sigungu_code(p.pnu)}
    if len(codes) > 1:
        warnings.append(f"여러 시군구에 걸친 구역입니다. 면적이 가장 큰 {region or '지역'} 기준으로 처리했습니다.")
    if region is None:
        warnings.append("PNU 로 시군구를 확인하지 못했습니다. 지역별 예측값 대신 전체 기준이 사용됩니다.")

    return ZoneSummary(
        site_area_m2=site_area_m2,
        far_min=far_min,
        far_max=far_max,
        land_value_total=land_value_total,
        pnus=[p.pnu for p in parcels],
        warnings=warnings,
        region=region,
    )

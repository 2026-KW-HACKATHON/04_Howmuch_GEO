# 사업 유형 판정 : 재개발 / 재건축
#   재건축 = 정비기반시설은 양호하나 노후·불량건축물에 해당하는 공동주택이 밀집한 지역의 사업 (도시정비법 제2조제2호다목)
#   서비스 규칙 (2026-10-08) : 고른 필지가 아파트 단지(들)뿐이면 재건축, 아파트 외 사유 필지가 하나라도 섞이면 재개발
#   · 아파트 = 공동주택 중 주택으로 쓰는 층수가 5개 층 이상 (건축법 시행령 별표1 제2호가목)
#       → 건축물대장 주용도 '공동주택' 이고 기타용도에 '아파트' 가 있거나 지상층수 5 이상
#   · 아파트 단지의 부속지번(건물 없이 단지에 묶인 필지)은 아파트 땅이다
#       (미미삼 17번지 : 미성아파트 부지인데 건물은 13번지로 등록 → 건축HUB 부속지번으로 찾는다)
#   · 판정에서 빼는 필지 : 국공유지, 지목이 도로·구거·하천·제방·유지·공원인 필지
#       정비구역에 함께 들어가는 기반시설이라 사업 유형을 바꾸지 않는다
#       (미미삼 정비구역에는 주민센터·치안센터·우체국·근린공원이 들어 있다)
#   · 여러 단지를 함께 고르면(통합 재건축) 아파트만이면 재건축이다. 미미삼도 세 단지다
#   ※ 단지 안 상가가 별도 필지면 "아파트 외 사유 필지" 로 세어 재개발이 된다 (상가 필지를 빼고 고르면 재건축)
#   · 건물 없는 소필지 : 아파트 단지와 함께 고른 건물 없는 사유 필지의 면적 합이 선택 면적의 MINOR_PARCEL_SHARE 미만이면
#       단지에 딸린 자투리로 보고 재건축 판정을 바꾸지 않는다 (2026-10-08). 건물이 있는 필지는 크기와 무관하게 재개발이다
from dataclasses import dataclass, field

from AI.engine.prior_asset import is_public_owner

REDEVELOPMENT = "재개발"
RECONSTRUCTION = "재건축"

#판정에서 빼는 지목 (정비기반시설)
INFRA_CATEGORIES = ("도로", "구거", "하천", "제방", "유지", "공원")

#건물 없는 소필지 문턱 (선택 면적 대비) — 측정값이 아니라 판정 기준이다 (2026-10-08, 사용자가 판단을 맡김)
#  · 월계동신 정비구역 5필지를 그대로 고르면 부속지번에 없는 산203(임야 198㎡ = 구역의 0.45%) 하나로 재개발이 됐고,
#    그 때문에 재개발 의무 임대·이중 땅값이 붙어 59㎡ 분담금이 2.8억 달라졌다 (PIPELINE §9 세 구역 검산)
#  · 5% 는 이런 자투리(임야·대지 끝자락)를 넉넉히 덮고, 건물 없는 큰 땅(나대지·공터)이 섞인 구역은 넘도록 잡았다
MINOR_PARCEL_SHARE = 0.05


def is_apartment(main_purpose: str, etc_purpose: str, floors: int) -> bool:
    return "공동주택" in (main_purpose or "") and ("아파트" in (etc_purpose or "") or int(floors or 0) >= 5)


@dataclass
class ParcelUse:
    pnu: str
    has_building: bool
    main_purpose: str = ""
    etc_purpose: str = ""
    floors: int = 0
    owner_type: str = ""
    land_category: str = ""
    land_area_m2: float = 0.0   # 토지면적 (건물 없는 소필지 판정). 0 이면 소필지 규칙을 쓰지 않는다


@dataclass
class ProjectTypeResult:
    project_type: str
    reason: str
    apartment_pnus: list[str] = field(default_factory=list)
    annex_pnus: list[str] = field(default_factory=list)     # 아파트 단지의 부속지번으로 확인된 필지
    ignored_pnus: list[str] = field(default_factory=list)   # 국공유·기반시설 (판정에서 뺌)
    other_pnus: list[str] = field(default_factory=list)     # 아파트 외 사유 필지 → 있으면 재개발
    minor_pnus: list[str] = field(default_factory=list)     # 건물 없는 소필지 — 단지에 딸린 자투리로 봄 (재건축 유지)


#annex : 고른 아파트 필지들의 부속지번 PNU 모음 (건축HUB getBrAtchJibunInfo)
def classify_project(parcels: list[ParcelUse], annex: set[str]) -> ProjectTypeResult:
    result = ProjectTypeResult(REDEVELOPMENT, "")
    for p in parcels:
        if p.has_building and is_apartment(p.main_purpose, p.etc_purpose, p.floors):
            result.apartment_pnus.append(p.pnu)
        elif not p.has_building and p.pnu in annex:
            result.annex_pnus.append(p.pnu)
        elif is_public_owner(p.owner_type) or p.land_category in INFRA_CATEGORIES:
            result.ignored_pnus.append(p.pnu)
        else:
            result.other_pnus.append(p.pnu)

    #건물 없는 소필지 : 아파트 단지가 있고 아파트 외 필지가 모두 건물 없는 땅이며 면적 합이 문턱 미만이면 단지에 딸린 자투리로 본다
    total_area = sum(p.land_area_m2 for p in parcels)
    others = [p for p in parcels if p.pnu in result.other_pnus]
    minor_area = sum(p.land_area_m2 for p in others)
    if (
        result.apartment_pnus and others and total_area > 0
        and all(not p.has_building for p in others)
        and minor_area < MINOR_PARCEL_SHARE * total_area
    ):
        result.minor_pnus = [p.pnu for p in others]
        result.other_pnus = []

    excluded = f" · 국공유·기반시설 {len(result.ignored_pnus)}필지는 판정에서 뺌" if result.ignored_pnus else ""
    if result.minor_pnus:
        excluded += f" · 건물 없는 소필지 {len(result.minor_pnus)}개(선택 면적의 {minor_area / total_area:.1%})는 단지 땅으로 봄"
    if result.apartment_pnus and not result.other_pnus:
        annex_text = f" + 부속지번 {len(result.annex_pnus)}필지" if result.annex_pnus else ""
        result.project_type = RECONSTRUCTION
        result.reason = f"아파트 단지 필지 {len(result.apartment_pnus)}개{annex_text}만 선택{excluded}"
    elif result.apartment_pnus:
        result.reason = f"아파트 외 필지 {len(result.other_pnus)}개가 섞여 재개발로 계산{excluded}"
    else:
        result.reason = f"아파트 단지가 없어 재개발로 계산{excluded}"
    return result

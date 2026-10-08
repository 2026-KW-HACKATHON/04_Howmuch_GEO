from math import isfinite
from pydantic import BaseModel, Field, field_validator, model_validator
from app.schemas.realestate.realestate_request import ParcelHintDTO, UnitMixEntryDTO
from app.config.engine_defaults import COMPLETION_GAP_MIN, PROJECT_PERIOD_TRACK
from AI.engine.rental_cost import FLOOR_BANDS

#조직 Map View 스키마
class OrganizationMapView(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    level: int = Field(..., ge=1, le=14)

#조직 시나리오 요청 스키마
class OrganizationScenarioRequest(BaseModel):
    pnus: list[str] = Field(..., min_length=1, max_length=1000)
    parcels: list[ParcelHintDTO] = Field(..., min_length=1, max_length=1000)
    map_view: OrganizationMapView
    zoning: str = Field(..., min_length=1, max_length=40)
    target_ym: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    sliders: dict[str, int | float | str | list[int | float]]
    unit_mix: list[UnitMixEntryDTO] | None = Field(None, max_length=4)
    rental_exclusive_area_m2: float | None = Field(None, gt=0, le=200)

    @field_validator("pnus")
    @classmethod
    def validate_pnus(cls, pnus: list[str]) -> list[str]:
        if len(set(pnus)) != len(pnus) or any(not pnu.isdigit() or len(pnu) != 19 for pnu in pnus):
            raise ValueError("필지 번호 형식이 올바르지 않습니다.")
        return pnus

    @field_validator("zoning")
    @classmethod
    def validate_zoning(cls, zoning: str) -> str:
        allowed_zonings = {
            "제1종전용주거지역",
            "제2종전용주거지역",
            "제1종일반주거지역",
            "제2종일반주거지역",
            "제3종일반주거지역",
            "준주거지역",
        }
        if zoning not in allowed_zonings:
            raise ValueError("지원하지 않는 용도지역입니다.")
        return zoning

    @field_validator("target_ym")
    @classmethod
    def validate_target_ym(cls, target_ym: str) -> str:
        month = int(target_ym[-2:])
        if month < 1 or month > 12:
            raise ValueError("기준 연월이 올바르지 않습니다.")
        return target_ym

    @field_validator("sliders")
    @classmethod
    def validate_sliders(cls, sliders: dict[str, int | float | str | list[int | float]]) -> dict[str, int | float | str | list[int | float]]:
        allowed_keys = {
            "floor_area_ratio",
            "member_count",
            "member_price_ratio",
            "other_cost_ratio",
            "parking_margin",
            "commercial_ratio",
            "construction_cost_per_pyeong",
            "general_price_per_m2",
            "rental_floor_band",
            "project_period_years",
        }
        if not sliders or not sliders.keys() <= allowed_keys:
            raise ValueError("지원하지 않는 슬라이더 값이 포함되어 있습니다.")
        for key, value in sliders.items():
            if key == "rental_floor_band":
                #층수 구간 (슬라이더 options 와 같은 목록)
                if value not in FLOOR_BANDS:
                    raise ValueError(f"{key} 슬라이더 값이 올바르지 않습니다.")
            elif key == "project_period_years":
                #손잡이 두 개 [분담금 고시일, 최종 인가] (년). 트랙 안 · 최소 간격 이상
                track_min, track_max = PROJECT_PERIOD_TRACK
                if (
                    not isinstance(value, list) or len(value) != 2
                    or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in value)
                    or not track_min <= value[0] <= value[1] <= track_max
                    or value[1] - value[0] < COMPLETION_GAP_MIN
                ):
                    raise ValueError(f"{key} 슬라이더 값이 올바르지 않습니다.")
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{key} 슬라이더 값은 유한한 숫자여야 합니다.")
        return sliders

    @model_validator(mode="after")
    def validate_parcel_selection(self):
        parcel_pnus = [parcel.pnu for parcel in self.parcels]
        if len(set(parcel_pnus)) != len(parcel_pnus) or set(parcel_pnus) != set(self.pnus):
            raise ValueError("저장할 필지 목록과 필지 정보가 일치하지 않습니다.")
        return self

#조직 시나리오 생성 스키마
class OrganizationScenarioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    scenario: OrganizationScenarioRequest

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        normalized = name.strip()
        if not normalized:
            raise ValueError("기준안 이름을 입력해 주세요.")
        return normalized

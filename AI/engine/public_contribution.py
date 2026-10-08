# 공공기여 방식 — 토지 / 현금 / 공공임대 건축물을 기부면적 비율(%)로 섞는다
#
# 상한용적률 산식 (서울시 2030 도시·주거환경정비기본계획 2024.9 p.260,
#   「공공시설등 기부채납 용적률 인센티브 운영기준」 2026.06.05 일부개정)
#   상한 = 최종허용 + 허용(보정 전) × (1.3 × 가중치 × α토지 + 1.0 × α건축물 + 0.7 × α현금)
#   α 의 분모 = 사업부지 (기부한 토지와 건축물 기부채납 대지지분을 뺀 대지).
#   현금·건축비 환산부지(금액 ÷ 부지가액)는 분모에서 빼지 않는다 (운영기준 1-3-3~1-3-6)
#
# 용적률 노드(zone.far_plan)는 토지로만 낼 때의 기부 비율 c(원래 대지 대비)를 붙여 내려준다.
#   그 노드 용적률까지 올리는 데 필요한 "Σ 계수 × α" (need) 는 방식과 무관하므로 c 에서 되돌려 구한다
#     need = 1.3 × c ÷ (1 − c)
#   종상향 최소 노드도 같다 — 그 노드 용적률이 최소 비율 c 를 토지로 냈을 때 받는 값이기 때문이다
#
# 비율의 기준은 기부면적(순부담)이다 — 현금과 공공임대 건축비는 부지가액으로 땅 면적에 환산해 센다.
#   이촌 강변·강서 고시의 순부담 표기(토지 349.4 + 건축물 환산 160.4 + 현금 환산 441.0㎡)와 같은 기준이고,
#   현금 한도(시행령 제14조② : 기부면적의 2분의 1)도 이 기준이라 같은 비율로 바로 건다
#   · 토지     : 떼는 땅 L. 건축 대지가 그만큼 준다
#   · 현금     : 환산부지 E. 현금 = E × 부지가액 이 사업비가 된다
#   · 공공임대 : 공공임대 F(공급면적)를 지어 기부채납 (인수대금 0, 대지 그대로).
#                기부면적에는 대지지분 λF (토지 계수 1.3) + 설치비 환산 bF (건축물 계수 1.0) 로 들어간다
#   기부면적 N 을 비율대로 나누면 (토지몫 = s토지 + s공공임대 × λ/(λ+b), 건축물몫 = s공공임대 × b/(λ+b))
#     need × (S − N × 토지몫) = N × (1.3 × 토지몫 + 1.0 × 건축물몫 + 0.7 × s현금)
#     → N = need × S ÷ (1.3 × 토지몫 + 1.0 × 건축물몫 + 0.7 × s현금 + need × 토지몫)
#   L = s토지 N,  E = s현금 N,  F = s공공임대 N ÷ (λ + b)
#   예전 버튼 셋은 이 식의 특수한 경우다 — 토지 100 / 토지 50 + 현금 50 / 공공임대 100 (결과 같음, 2026-10-08 확인)
#   종상향 최소 공공기여(순부담, 원래 대지 대비)가 더 크면 N 을 그만큼 늘리되 노드 용적률은 그대로 둔다 (보수적)
#   공공임대 기부 세대도 같은 획지의 건물이라 용적률은 남은 대지 전체에 곱한다 (가정)
#
# 그 밖의 공공시설 건축물(계수 0.7)은 대지지분을 어떻게 잡느냐에 따라 결과가 크게 달라져 넣지 않았다 (2026-10-08 결정)
from dataclasses import dataclass

from AI.engine import policy
from AI.engine.zone import LAND_CONTRIBUTION_COEF

#계수·한도 (policy_rules.json — 출처는 notes)
BUILDING_COEF = float(policy.RULES["building_contribution_coef"])       # 공공임대 건축물 1.0
CASH_COEF = float(policy.RULES["cash_contribution_coef"])               # 현금 0.7
CASH_MAX_SHARE = float(policy.RULES["cash_contribution_max_share"])     # 현금 ≤ 기부면적의 1/2
SITE_VALUE_WEIGHT = float(policy.RULES["site_value_weight"])            # 부지가액 = 공시지가 × 2


#기부면적 비율 (합 1)
@dataclass(frozen=True)
class ContributionMix:
    land: float = 1.0
    public_rental: float = 0.0
    cash: float = 0.0


#버튼(프리셋). 프론트 CONTRIBUTION_PRESETS 와 같은 값 — "토지 + 현금" 은 현금을 한도(절반)까지 채운다.
#  화면은 토지를 먼저 넣어야 다른 칸이 열려(기반시설은 땅으로 낸다) 공공임대도 토지와 반씩이다 (2026-10-08)
PRESETS = {
    "land": ContributionMix(1.0, 0.0, 0.0),
    "land_cash": ContributionMix(1 - CASH_MAX_SHARE, 0.0, CASH_MAX_SHARE),
    "land_rental": ContributionMix(0.5, 0.5, 0.0),
}


#입력 비율(%, 합이 100 이 아니어도 된다) → 합 1 로 맞춘 비율, 현금 한도에 걸렸는가
#  현금이 한도를 넘으면 한도로 자르고 남는 몫을 토지·공공임대에 입력 비율대로 나눈다 (둘 다 0 이면 토지)
#  합이 0 이면 토지로 본다
def normalize_mix(land: float, public_rental: float, cash: float) -> tuple[ContributionMix, bool]:
    land, public_rental, cash = (max(float(v or 0.0), 0.0) for v in (land, public_rental, cash))
    total = land + public_rental + cash
    if total <= 0:
        return PRESETS["land"], False
    land, public_rental, cash = land / total, public_rental / total, cash / total
    if cash <= CASH_MAX_SHARE + 1e-9:
        return ContributionMix(land, public_rental, cash), False
    rest = land + public_rental
    if rest <= 0:
        return ContributionMix(1 - CASH_MAX_SHARE, 0.0, CASH_MAX_SHARE), True
    scale = (1 - CASH_MAX_SHARE) / rest
    return ContributionMix(land * scale, public_rental * scale, CASH_MAX_SHARE), True


#노드의 토지 기부 비율 c → 그 노드 용적률에 필요한 Σ 계수 × α
def contribution_need(land_ratio: float) -> float:
    if land_ratio <= 0:
        return 0.0
    return LAND_CONTRIBUTION_COEF * land_ratio / (1 - land_ratio)


@dataclass
class MixedContribution:
    total_m2: float             # 기부면적 N (환산 포함, ㎡)
    land_ratio: float           # 떼는 토지 (원래 대지 대비)
    cash_area_m2: float         # 현금 환산부지 (㎡). 현금 = 이 면적 × 부지가액
    rental_supply_m2: float     # 기부채납 공공임대 공급면적 (㎡)


#기부면적 비율대로 노드 용적률에 필요한 기여를 채운다
#  min_ratio              : 종상향 최소 공공기여 (순부담, 원래 대지 대비)
#  land_share_per_supply  λ : 주택 공급면적 1㎡ 의 대지지분 (주택 몫 대지 ÷ 주택 공급면적 합계)
#  conversion_per_supply  b : 주택 공급면적 1㎡ 의 설치비 환산부지
#                             = (지상층 기본형건축비 + 지하층면적 비 × 지하층건축비) ÷ 부지가액
#  공공임대 몫이 0 이면 λ·b 는 쓰지 않는다
def mixed_contribution(
    need: float,
    min_ratio: float,
    site_m2: float,
    mix: ContributionMix,
    land_share_per_supply: float = 0.0,
    conversion_per_supply: float = 0.0,
) -> MixedContribution:
    if (need <= 0 and min_ratio <= 0) or site_m2 <= 0:
        return MixedContribution(0.0, 0.0, 0.0, 0.0)
    lam, b = land_share_per_supply, conversion_per_supply
    per_rental = lam + b
    if mix.public_rental > 0 and per_rental <= 0:
        raise ValueError("공공임대 몫이 있는데 대지지분·설치비 환산이 0 입니다")
    land_part = mix.land + (mix.public_rental * lam / per_rental if mix.public_rental > 0 else 0.0)
    building_part = mix.public_rental * b / per_rental if mix.public_rental > 0 else 0.0
    total = 0.0
    if need > 0:
        total = need * site_m2 / (
            LAND_CONTRIBUTION_COEF * land_part + BUILDING_COEF * building_part + CASH_COEF * mix.cash
            + need * land_part
        )
    total = max(total, min_ratio * site_m2)
    return MixedContribution(
        total_m2=total,
        land_ratio=mix.land * total / site_m2,
        cash_area_m2=mix.cash * total,
        rental_supply_m2=mix.public_rental * total / per_rental if mix.public_rental > 0 else 0.0,
    )

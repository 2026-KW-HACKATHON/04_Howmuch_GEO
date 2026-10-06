import { SlidersState } from './useSlider';

//평형 선택 버튼 (백엔드 unit_options)
export interface UnitOption {
    name: string;
    supply_area_m2: number;
    count: number;
    member_price: number;
}

//평형별 분담금 (백엔드 unit_contributions)
//  평형을 고르게 하지 않고 분양 평형 전부를 한 번에 깔아 보여준다.
//  비례율·권리가액은 평형과 무관해서 분양가만 평형별로 다르다
export interface UnitContribution {
    name: string;
    exclusive_area_m2: number;
    supply_area_m2: number;
    count: number;
    member_price: number;
    contribution: number;        //만원. 음수면 환급
    contribution_ratio: number;  //분담금 ÷ 조합원분양가
}

//세부 설정의 평형 한 줄 (전용면적 + 세대수 비율)
//  비율은 세대수 기준이다. 백엔드가 면적 몫으로 환산한다
export interface UnitMixEntry {
    exclusive_area_m2: number;
    household_ratio: number;     //% 로 보낸다 (30 = 30%). 합이 100 이 아니어도 서버가 정규화한다
}

//평형은 최대 4개까지. 그 이상은 화면에 깔 자리가 없고 일반인에게 의미도 없다
export const MAX_UNIT_TYPES = 4;

//필지별 종전자산 원자료 (/zone 의 prior_asset.parcels)
//  /contribution 에 그대로 돌려보낸다. 평가 기준시점(사업시행인가)이 사업기간 슬라이더에
//  따라 달라지고, 그 시점에는 건물이 더 낡고(잔존율 ↓) 재조달원가는 오르는데(공사비 ↑)
//  상쇄 정도가 구조마다 달라 필지 단위로 다시 계산해야 한다. API 추가 호출은 없다
export interface ParcelValuation {
    pnu: string;
    land_area_m2: number;
    land_price_per_m2: number;
    structure: string;
    building_area_m2: number;
    elapsed_years: number;
    household_count: number;
    has_building: boolean;
    land_category: string;
}

//구역 종전자산 집계 (/zone 의 prior_asset)
export interface ZonePriorAsset {
    land_total: number;
    building_total: number;
    total: number;
    official_total: number;
    ratio: number;              //r_구역 = 종전자산 ÷ 공시지가
    member_count: number;       //건축물대장 실측 조합원 수
    parcel_count: number;
    building_parcel_count: number;
    replacement_cost_per_m2: number;
    parcels: ParcelValuation[];
}

//종전자산 분해 (/contribution 의 prior_asset_detail)
//  rho 가 1 이 아니면 건물분으로 약분이 깨져 개인화된 상태다
export interface PriorAssetDetail {
    zone_land_total: number | null;
    zone_building_total: number | null;
    zone_total: number;
    zone_ratio: number | null;
    measured_member_count: number | null;
    building_parcel_count: number | null;
    owner_personalized: boolean;
    rho: number | null;
    owner_share: number | null;              //집합건물에서 적용된 내 몫
    owner_exclusive_total_m2: number | null; //전유면적 합계. 0 이면 세대수 균등분할을 썼다
}

//조합원 수 슬라이더 범위. 용적률에 따라 상한이 바뀐다 (분양 세대수를 넘을 수 없음)
export interface MemberCountRange {
    value: number;
    min: number;
    max: number;
    capped: boolean;
}

//분담금 계산 결과 (/contribution 응답)
export interface ContributionResult {
    contribution: number;        //분담금(만원). 음수면 환급
    member_price: number;        //조합원분양가
    right_value: number;         //권리가액
    prior_asset: number;         //종전자산 추정액
    proportional_rate: number;   //비례율(%)
    project: {
        unit_types: { name: string; supply_area_m2: number; count: number }[];
        rental_count: number;
        commercial_area_m2: number;
        gross_floor_area_m2: number;
        total_cost: number;
        total_post_asset: number;
        total_prior_asset: number;
        warnings: string[];
    };
    unit_options: UnitOption[];
    unit_contributions?: UnitContribution[];
    prior_asset_detail?: PriorAssetDetail;
    rental_exclusive_area_m2?: number;   //계산에 쓴 임대 전용면적. 세부 설정 입력란의 기본 표시값
    member_count_range?: MemberCountRange;
    warnings: string[];
    credits_remaining: number;
}

//구역 정보 (/zone 응답의 zone)
export interface ZoneInfo {
    site_area_m2: number;
    far_min: number;
    far_max: number;
    land_value_total: number;
    region: string | null;
    warnings: string[];
}

//상단 지표 한 줄. sliderKey 가 있으면 누를 때 그 슬라이더로 이동한다
export interface MetricRow {
    label: string;
    value: string;
    sliderKey?: string;
}

const PYEONG = 3.3058;
const toEok = (manwon: number) => `${(manwon / 10000).toFixed(2)}억`;
const toM2 = (m2: number) => `${Math.round(m2).toLocaleString()}㎡`;

//계산 결과를 사이드바 지표 목록으로 바꾼다 (좌우 2열로 번갈아 배치되므로 순서가 중요)
//  필지를 아직 고르지 않았으면 구역에서 나오는 값은 0, 슬라이더 값은 현재 설정값을 보여준다
export function buildMetrics(
    zone: ZoneInfo | null,
    result: ContributionResult | null,
    sliders: SlidersState,
    memberCount: number,
): MetricRow[] {
    const project = result?.project;
    const saleCount = project ? project.unit_types.reduce((sum, unit) => sum + unit.count, 0) : 0;
    const rentalCount = project?.rental_count ?? 0;
    const totalUnits = saleCount + rentalCount;
    const generalPrice = Number(sliders.general_price_per_m2?.value ?? 0);
    const commercialRatio = Number(sliders.commercial_ratio?.value ?? 0);
    const floorAreaRatio = Number(sliders.floor_area_ratio?.value ?? 0);
    const constructionCost = Number(sliders.construction_cost_per_pyeong?.value ?? 0);

    //계산 결과가 없으면 조합원 수도 0으로 둔다 (분양 세대수를 모르는 상태)
    const members = result ? memberCount : 0;

    return [
        { label: '대지면적', value: toM2(zone?.site_area_m2 ?? 0) },
        {
            label: '임대 비율',
            value: totalUnits ? `${((rentalCount / totalUnits) * 100).toFixed(0)}%` : '0%',
        },
        { label: '연면적', value: toM2(project?.gross_floor_area_m2 ?? 0), sliderKey: 'floor_area_ratio' },
        {
            label: '상가 비율 / 가격',
            //상가 가격 배수 0.7 : 서울 10개 구 상업업무용 실거래가 아파트 대비 0.48 + 신축 프리미엄
            //  engine_defaults.commercial_price_ratio 와 같은 값을 써야 한다
            value: `${(commercialRatio * 100).toFixed(0)}% · ${Math.round(generalPrice * 0.7 * PYEONG).toLocaleString()}만원/평`,
            sliderKey: 'commercial_ratio',
        },
        {
            label: '용적률',
            value: `${floorAreaRatio.toFixed(0)}%`,
            sliderKey: 'floor_area_ratio',
        },
        { label: '총 세대수', value: `${totalUnits.toLocaleString()}세대` },
        {
            label: '공사비',
            value: `${constructionCost.toLocaleString()}만원/평`,
            sliderKey: 'construction_cost_per_pyeong',
        },
        { label: '총사업비', value: toEok(project?.total_cost ?? 0) },
        //비례율은 화면에 띄우지 않는다 (2026-10-05 결정).
        //  분담금에는 영향이 없고(개인·구역에 같은 보정률이 들어가 약분된다),
        //  사업기간을 길게 잡을수록 값이 치솟아 오해를 부른다 (13년 247% / 18년 308%).
        //  실제 관리처분 비례율이 80~120% 인 것은 조합이 법인세 부담 때문에 조정하기도 해서다.
        //  (응답 proportional_rate 는 유지 — 권리가액 계산과 디버깅에 쓴다)
        {
            label: '일반분양',
            value: `${Math.max(saleCount - members, 0).toLocaleString()}세대`,
            sliderKey: 'member_count',
        },
        { label: '조합원 수', value: `${members.toLocaleString()}명`, sliderKey: 'member_count' },
        //내 필지를 지정하면 ρ(= r_개인 ÷ r_구역)가 1 에서 벗어난다.
        //  1 보다 크면 내 건물이 구역 평균보다 새것이라 권리가액을 더 받는다는 뜻이다.
        //  지정 전에는 구역 1인분이라 정확히 1.0 이고, 그때는 배수를 적지 않는다
        {
            label: result?.prior_asset_detail?.owner_personalized ? '종전자산(내 필지)' : '종전자산(1인분)',
            value: result?.prior_asset_detail?.rho
                ? `${toEok(result?.prior_asset ?? 0)} · ×${result.prior_asset_detail.rho.toFixed(2)}`
                : toEok(result?.prior_asset ?? 0),
        },
    ];
}

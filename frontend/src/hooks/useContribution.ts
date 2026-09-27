import { SlidersState } from './useSlider';

//평형 선택 버튼 (백엔드 unit_options)
export interface UnitOption {
    name: string;
    supply_area_m2: number;
    count: number;
    member_price: number;
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
    rate_fixed: boolean;
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
    member_count_range?: MemberCountRange;
    warnings: string[];
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
    const generalPrice = sliders.general_price_per_m2?.value ?? 0;
    const commercialRatio = sliders.commercial_ratio?.value ?? 0;

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
            value: `${(commercialRatio * 100).toFixed(0)}% · ${Math.round(generalPrice * 1.2 * PYEONG).toLocaleString()}만원/평`,
            sliderKey: 'commercial_ratio',
        },
        {
            label: '용적률',
            value: `${(sliders.floor_area_ratio?.value ?? 0).toFixed(0)}%`,
            sliderKey: 'floor_area_ratio',
        },
        { label: '총 세대수', value: `${totalUnits.toLocaleString()}세대` },
        {
            label: '공사비',
            value: `${(sliders.construction_cost_per_pyeong?.value ?? 0).toLocaleString()}만원/평`,
            sliderKey: 'construction_cost_per_pyeong',
        },
        { label: '총사업비', value: toEok(project?.total_cost ?? 0) },
        {
            label: '비례율',
            value: `${(result?.proportional_rate ?? 0).toFixed(1)}%`,
            sliderKey: 'proportional_rate',
        },
        {
            label: '일반분양',
            value: `${Math.max(saleCount - members, 0).toLocaleString()}세대`,
            sliderKey: 'member_count',
        },
        { label: '조합원 수', value: `${members.toLocaleString()}명`, sliderKey: 'member_count' },
        { label: '종전자산(내)', value: toEok(result?.prior_asset ?? 0) },
    ];
}

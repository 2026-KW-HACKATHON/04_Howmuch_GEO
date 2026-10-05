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
            //상가 가격 배수 0.7 : 서울 10개 구 상업업무용 실거래가 아파트 대비 0.48 + 신축 프리미엄
            //  engine_defaults.commercial_price_ratio 와 같은 값을 써야 한다
            value: `${(commercialRatio * 100).toFixed(0)}% · ${Math.round(generalPrice * 0.7 * PYEONG).toLocaleString()}만원/평`,
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
        //비례율은 화면에 띄우지 않는다 (2026-10-05 결정).
        //  분담금에는 영향이 없고(개인·구역에 같은 보정률이 들어가 약분된다),
        //  사업기간을 길게 잡을수록 값이 치솟아 오해를 부른다 (13년 247% / 18년 308%).
        //  실제 관리처분 비례율이 80~120% 인 것은 조합이 법인세 부담 때문에 조정하기도 해서다.
        //  우리 값은 "조정 전 날것의 사업성" 이라 성격이 다르다.
        //  사업 종료 시점까지로 범위를 넓히면 더 뛸 값이라 아예 빼는 편이 낫다.
        //  (응답 ProjectResult.proportional_rate 는 유지 — 권리가액 계산과 디버깅에 쓴다)
        {
            label: '일반분양',
            value: `${Math.max(saleCount - members, 0).toLocaleString()}세대`,
            sliderKey: 'member_count',
        },
        { label: '조합원 수', value: `${members.toLocaleString()}명`, sliderKey: 'member_count' },
        { label: '종전자산(내)', value: toEok(result?.prior_asset ?? 0) },
    ];
}

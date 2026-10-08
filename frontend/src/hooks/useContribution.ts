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
    cost_index?: number;     //재조달원가 상대지수 (구조·용도, 아파트 = 1.0)
    owner_type?: string;     //토지 소유구분. 국·공유지면 종전자산·조합원 수에서 빠진다
    //주택 공시가격 (있으면 종전자산 = 공시가격 ÷ 현실화율 — 공동 69% · 단독 53.6%)
    housing_kind?: string;                            //공동 · 단독 · 빈칸
    housing_price?: number;                           //공시가격 합계 (만원)
    housing_units?: number;                           //공동주택가격 호수
    housing_area_prices?: [number, number, number][] | null;  //[전용면적, 호당 공시가격, 호수]
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
    housing_total?: number;          //주택 공시가격으로 잡은 몫 (만원)
    housing_parcel_count?: number;
    replacement_cost_per_m2: number;
    parcels: ParcelValuation[];
}

//종전자산 분해 (/contribution 의 prior_asset_detail)
//  rho 가 1 이 아니면 건물분으로 약분이 깨져 개인화된 상태다
export interface PriorAssetDetail {
    zone_land_total: number | null;
    zone_building_total: number | null;
    zone_housing_total?: number | null;      //주택 공시가격 ÷ 현실화율로 잡은 몫
    housing_parcel_count?: number | null;
    owner_basis?: string | null;             //내 종전자산을 잡은 방법 (공시가격 ÷ 현실화율 / 토지분 + 건물분)
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

//관리처분 확정 → 준공 정산 한 단계 (/contribution 의 timeline.stages)
//  ① 관리처분 확정 ② 분양·임대 시점 반영 ③ 공사비 물가변동 ④ 비물가 초과 증액(= 준공 정산)
export interface TimelineStage {
    label: string;
    proportional_rate: number;
    total_cost: number;                         //만원
    total_post_asset: number;                   //만원
    contribution: number;                       //선택 평형 분담금(만원)
    unit_contributions: Record<string, number>; //평형별 분담금(만원)
}

//공공기여 기부면적 비율 (세부 설정, %). 합이 100 이 아니어도 서버가 비율대로 맞춘다
//  현금과 공공임대 건축비는 부지가액(공시지가 × 2)으로 땅 면적에 환산해 센다 → 서버 AI/engine/public_contribution.py
export interface ContributionMix {
    land: number;           //토지
    public_rental: number;  //공공임대 건축물 기부채납 (대지지분 + 설치비 환산)
    cash: number;           //현금 — 기부면적의 절반까지 (도시정비법 시행령 제14조②)
}

//현금 한도 (기부면적 대비). 서버 rules.cash_contribution_max_share 와 같은 값
export const CASH_MAX_SHARE = 0.5;

//버튼 = 비율 프리셋. 서버 public_contribution.PRESETS 와 같은 값 ("토지 + 현금" 은 현금을 한도인 절반까지 채운다).
//  토지를 먼저 넣어야 다른 칸이 열리므로(도로·공원 같은 기반시설은 땅으로 낸다) 프리셋도 모두 토지를 포함한다 (2026-10-08)
export const CONTRIBUTION_PRESETS: { key: string; label: string; sub?: string; mix: ContributionMix }[] = [
    { key: 'land', label: '토지', mix: { land: 100, public_rental: 0, cash: 0 } },
    { key: 'land_cash', label: '토지 + 현금', sub: '절반값 자동 입력', mix: { land: 50, public_rental: 0, cash: 50 } },
    { key: 'land_rental', label: '토지 + 공공임대', sub: '절반값 자동 입력', mix: { land: 50, public_rental: 50, cash: 0 } },
];

//입력 비율을 「적용」할 수 없는 이유 (없으면 null). 서버도 현금 한도를 넘으면 잘라서 계산한다
export function contributionMixError(mix: ContributionMix): string | null {
    const total = mix.land + mix.public_rental + mix.cash;
    if (!(mix.land > 0)) return '토지 비율을 먼저 입력하세요. 도로·공원 같은 기반시설은 땅으로 냅니다.';
    if (!(total > 0)) return '비율을 하나 이상 입력하세요.';
    if (mix.cash / total > CASH_MAX_SHARE + 1e-9) {
        return `현금은 기부면적의 절반(${CASH_MAX_SHARE * 100}%)까지입니다 (도시정비법 시행령 제14조②).`;
    }
    return null;
}

//두 비율이 같은 배분인가 (합으로 나눠 비교 — 50/50 과 1/1 은 같다)
export function sameContributionMix(a: ContributionMix, b: ContributionMix): boolean {
    const ta = a.land + a.public_rental + a.cash;
    const tb = b.land + b.public_rental + b.cash;
    if (!(ta > 0) || !(tb > 0)) return ta === tb;
    return (['land', 'public_rental', 'cash'] as const).every((k) => Math.abs(a[k] / ta - b[k] / tb) < 1e-6);
}

//사업 일정과 시점별 값 (/contribution 의 timeline)
//  조합원분양가는 고시일(관리처분)에 명목으로 확정되고, 분담금은 최종 인가(준공) 때 정산된다
export interface ContributionTimeline {
    now_ym: string;
    prior_ym: string;                  //종전자산 평가 (사업시행인가)
    mgmt_ym: string;                   //분담금 고시일 (관리처분인가)
    start_ym: string;                  //착공 (일반분양)
    complete_ym: string;               //최종 인가 (준공)
    mgmt_years: number;
    complete_years: number;
    cost_contract_per_pyeong: number;  //공사비 도급단가 (고시일, 만원/평)
    cost_final_per_pyeong: number;     //기성 평균 공사비 (준공 정산, 만원/평)
    escalation_index: number;          //물가변동 배수 (건설공사비지수)
    escalation_excess: number;         //비물가 초과 배수
    escalation_total: number;
    excess_rate: number;               //비물가 초과 연율
    excess_basis: string;              //초과율을 잰 사례 범위 ("서울 전체" 또는 지역명)
    excess_case_count: number;
    excess_span: string;
    general_price_mgmt_per_m2: number;
    general_price_start_per_m2: number;
    project_type?: string;                     //재개발 · 재건축
    prior_basis?: string;                      //종전자산을 잡은 방법 (재건축 : 공동주택가격 ÷ 현실화율)
    member_price_mode: 'auto' | 'manual';      //auto : 관리처분 비례율이 target_rate 가 되도록 서버가 역산
    member_price_target_rate: number | null;   //자동일 때 관리처분 비례율 목표 (%)
    member_price_ratio_solved: number | null;  //범위 제한 전 역산 값
    member_price_ratio_bound: 'min' | 'max' | null;  //역산 값이 범위 끝에 걸렸으면 그 끝
    member_price_ratio: number;                //계산에 쓴 비율 (자동이면 역산 값)
    member_price_per_m2: number;       //조합원분양가 (고시일 확정, 만원/㎡)
    member_price_per_pyeong: number;   //조합원분양가 (고시일 확정, 만원/평)
    public_contribution_ratio: number; //종상향 공공기여율
    net_site_area_m2: number;          //공공기여를 뺀 대지면적
    //공공기여 — 적용된 기부면적 비율(%, 합 100 으로 맞춘 값)·기부면적(㎡), 실제로 뗀 토지 비율, 현금(만원)·환산부지(㎡),
    //  기부채납 공공임대 세대수, 부지가액(만원/㎡), 안내 문장
    contribution_mix?: ContributionMix;
    contribution_total_m2?: number;
    contribution_land_ratio?: number;
    contribution_cash?: number;
    contribution_cash_area_m2?: number;
    contribution_rental_count?: number;
    contribution_site_value_per_m2?: number;
    contribution_note?: string;
    stages: TimelineStage[];
}

//종상향 판정 (/zone 의 upzoning)
//  기준 용도지역 = 필지 원래 용도지역의 면적가중 평균 단계. 그보다 높게 고르면 공공기여율이 붙는다
export interface UpzoningInfo {
    base_zoning: string | null;
    selected_zoning: string | null;
    steps: number;
    contribution_ratio: number;
    note: string;
}

//사업성 보정계수 (/zone 의 business_correction)
//  서울시 평균 공시지가 ÷ 구역 '대' 필지 평균 (1.00~2.00). 허용·상한 용적률을 올린다
export interface BusinessCorrection {
    factor: number;
    raw: number | null;
    zone_avg_price: number | null;
    seoul_avg_price: number;
    basis_year: number;
    parcel_count: number;
    note: string;
    project_type?: string;          //재개발 · 재건축 (재건축은 서울시 공동주택 평균 공시지가 + α + β)
    land_factor?: number | null;    //공시지가 보정계수
    site_factor?: number;           //재건축 α 대지면적 보정계수
    density_factor?: number;        //재건축 β 세대밀도 보정계수
}

//재건축 단지 정보 (/zone 의 reconstruction). /contribution 에 그대로 돌려보낸다
export interface ReconstructionInfo {
    members: number;                          //조합원 수 = 아파트 세대 + 상가 등 비주거 호수
    commercial: {                             //상가 등 비주거 (토지 지분 + 건물 원가법). 없으면 null
        units: number;
        floor_area_m2: number;
        land_share_m2: number;
        land_price_per_m2: number;
        structure: string;
        elapsed_years: number;
        cost_index: number;
    } | null;
    households: number;                       //총괄표제부 세대수
    site_area_m2: number;                     //단지 대지면적 (아파트 필지 + 부속지번)
    current_far: number | null;               //현황용적률 (%) — 과밀단지 판정
    official_year: number | null;             //공동주택가격 기준 년도
    unit_count: number;
    official_total: number;                   //공동주택가격 합계 (만원)
    area_prices: [number, number, number][];  //[전용면적, 호당 공시가격(만원), 호수]
    annex_pnus: string[];
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
    timeline?: ContributionTimeline;     //사업 일정 · 관리처분 확정 → 준공 정산 단계
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
    compact?: boolean;      //값이 길어 두 칸 격자에서 잘리는 항목 — 글자를 줄여 다 보이게 한다
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

    //조합원 분양가(만원/평) : 고시일 확정값. timeline 이 없는 응답(이전 백엔드)이면 평형 분양가에서 되돌린다.
    //  계산 전에는 비워 둔다 — 슬라이더의 오늘 기준 분양가로 채우면 계산 후 값(고시일 기준)과 시점이 달라 헷갈린다
    const firstUnit = result?.unit_contributions?.[0];
    const memberPriceRatio = result?.timeline?.member_price_ratio ?? null;
    const memberPricePerPyeong = result?.timeline?.member_price_per_pyeong
        ?? (firstUnit && firstUnit.supply_area_m2 ? firstUnit.member_price / (firstUnit.supply_area_m2 / PYEONG) : null);

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
            compact: true,
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
        //조합원 분양가 : 분담금 고시일(관리처분)에 명목으로 확정되는 평당 가격.
        //  종전자산 옆에 둔다 — 분담금 = 조합원분양가 − 권리가액(종전자산 × 비례율) 의 두 입력이다.
        //  확정 이후에는 오르지 않는다 (공사비 증액은 비례율을 깎아 분담금으로 돌아온다)
        {
            label: '조합원 분양가',
            //비율을 같이 적는다. 자동이면 관리처분 비례율 100% 가 되도록 서버가 정한 값이다
            value: memberPricePerPyeong
                ? `${Math.round(memberPricePerPyeong).toLocaleString()}만원/평`
                  + (memberPriceRatio ? ` · 일반분양가의 ${Math.round(memberPriceRatio * 100)}%` : '')
                : '–',
            sliderKey: 'member_price_ratio',
            compact: true,
        },
    ];
}

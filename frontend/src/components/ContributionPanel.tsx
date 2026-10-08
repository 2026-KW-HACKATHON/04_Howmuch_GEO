import React, { useState } from 'react';
import { SliderValue, SlidersState } from '../hooks/useSlider';
import {
    BusinessCorrection,
    CONTRIBUTION_PRESETS,
    ContributionMix,
    ContributionResult,
    contributionMixError,
    MAX_UNIT_TYPES,
    MetricRow,
    UnitContribution,
    UnitMixEntry,
    UpzoningInfo,
    ZonePriorAsset,
    sameContributionMix,
} from '../hooks/useContribution';
import Slider from './Slider';

//변수 조절 탭 : 자주 쓰는 값은 일반, 나머지는 세부
const BASIC_KEYS = [
    'floor_area_ratio', 'member_count', 'general_price_per_m2',
    'construction_cost_per_pyeong', 'project_period_years',
];

//공공기여 비율 입력 줄 (세부 설정). 기부면적 기준 % — 현금·공공임대 건축비는 부지가액으로 땅 면적에 환산한다
const CONTRIBUTION_MIX_ROWS: { key: keyof ContributionMix; label: string; limit?: string }[] = [
    { key: 'land', label: '토지' },
    { key: 'cash', label: '현금', limit: '최대 50%' },
    { key: 'public_rental', label: '공공임대 건축물' },
];

//입력 중이거나 서버 안내가 없을 때 보여주는 설명
const CONTRIBUTION_MIX_HINT =
    '토지를 먼저 입력하면 현금·공공임대 칸이 열립니다. 기부면적 기준 비율이고, 현금·공공임대 건축비는 공시지가 × 2 로 땅 면적에 환산해 셉니다.';

//평형 구성 입력란이 하나도 없을 때 보여줄 첫 줄 (아직 계산 결과가 없는 상태)
const EMPTY_MIX_ROW: UnitMixEntry = { exclusive_area_m2: 59, household_ratio: 30 };

interface ContributionPanelProps {
    result: ContributionResult | null;   //분담금 계산 결과 (/contribution 응답). 필지 선택 전에는 null
    metrics: MetricRow[];                //상단 지표 목록
    sliders: SlidersState;
    onSliderChange: (key: string, newValue: SliderValue) => void;
    onSliderAuto?: (key: string) => void;  //자동 슬라이더(조합원 분양가 비율)를 다시 자동으로
    unitMix: UnitMixEntry[] | null;      //사용자가 손댄 평형 구성. null 이면 서버 실측 기본값
    onUnitMixChange: (rows: UnitMixEntry[]) => void;
    rentalExclusive: number | null;      //사용자가 입력한 임대 전용면적. null 이면 서버 기본값
    onRentalExclusiveChange: (value: number | null) => void;
    onApplyUnitMix: () => void;          //평형·비율은 「적용」을 눌러야 계산에 반영된다
    unitMixDirty: boolean;               //입력값이 적용값과 다른가
    contributionMix: ContributionMix;                            //입력 중인 공공기여 비율 (「적용」 전일 수 있다)
    onContributionMixChange: (mix: ContributionMix) => void;
    onApplyContributionMix: () => void;                          //공공기여 비율도 「적용」을 눌러야 계산에 반영된다
    contributionMixDirty: boolean;                               //입력 비율이 적용된 비율과 다른가
    priorAsset: ZonePriorAsset | null;   //구역 종전자산 집계. 내 필지 목록이 여기 있다
    ownerPnu: string;                    //내 필지. 비우면 구역 1인분(ρ=1)
    onSelectOwnerPnu: (pnu: string) => void;
    ownerExclusive: number | null;       //집합건물에서 내 전유면적(㎡)
    onOwnerExclusiveChange: (value: number | null) => void;
    zoningStale: boolean;                //용도지역을 바꿨는데 아직 다시 분석하지 않았다
    upzoning: UpzoningInfo | null;       //종상향 판정 (/zone). steps > 0 이면 공공기여로 대지가 준다
    businessCorrection: BusinessCorrection | null;  //사업성 보정계수 (/zone)
    desiredUnit: string;                 //단계별 내역을 보여줄 평형 (없으면 첫 평형)
    targetYm: string;                    //공사비·분양가 예측 기준 시점 "YYYY-MM"
    loading?: boolean;                   //재계산 중이면 값을 흐리게 표시한다
}

//만원 → 억 표기
const toEok = (manwon: number) => (manwon / 10000).toFixed(2);

//입력칸 공통 스타일. 숫자만 받고 비어 있는 중간 상태를 허용한다
const INPUT_CLASS =
    'w-14 rounded-md border border-gray-200 px-1.5 py-1 text-right text-[12.5px] tabular-nums ' +
    'focus:border-blue-400 focus:outline-none';

//예상 분담금 패널
export default function ContributionPanel({
    result, metrics, sliders, onSliderChange, onSliderAuto,
    unitMix, onUnitMixChange, rentalExclusive, onRentalExclusiveChange,
    onApplyUnitMix, unitMixDirty,
    contributionMix, onContributionMixChange, onApplyContributionMix, contributionMixDirty,
    priorAsset, ownerPnu, onSelectOwnerPnu, ownerExclusive, onOwnerExclusiveChange,
    zoningStale, upzoning, businessCorrection, desiredUnit, targetYm, loading = false,
}: ContributionPanelProps) {
    const [tab, setTab] = useState<'basic' | 'detail'>('basic');

    //지표를 누르면 해당 슬라이더로 이동한다. 세부 탭에 있으면 탭도 같이 바꾼다
    const focusSlider = (key?: string) => {
        if (!key) return;
        setTab(BASIC_KEYS.includes(key) ? 'basic' : 'detail');

        //탭 전환 후 렌더링이 끝난 뒤에 스크롤
        requestAnimationFrame(() => {
            const el = document.getElementById(`field-${key}`);
            el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
    };

    //예상 분담금은 최종 인가(준공) 때 정산되는 금액이다.
    //  사업 기간 슬라이더는 [분담금 고시일, 최종 인가] 이고, 예전 백엔드는 숫자 하나(고시일)를 내려준다
    const timeline = result?.timeline ?? null;
    const projectType = timeline?.project_type ?? null;   //재개발 / 재건축 (사이드바 안내 문구에 쓴다)
    const periodValue = sliders.project_period_years?.value;
    const completeYears = timeline?.complete_years
        ?? (Array.isArray(periodValue) ? periodValue[1] : Number(periodValue ?? 0));
    const completeYear = timeline ? timeline.complete_ym.slice(0, 4) : String(new Date().getFullYear() + completeYears);
    const periodLabel = completeYears > 0
        ? (Array.isArray(periodValue) || timeline ? `최종 인가 ${completeYears}년 후 · ${completeYear}` : `${completeYears}년 후`)
        : '현재';

    const units: UnitContribution[] = result?.unit_contributions ?? [];

    //관리처분 확정 → 준공 정산 단계별 내역 (한 평형 기준)
    const stageUnit = units.some((unit) => unit.name === desiredUnit) ? desiredUnit : units[0]?.name;
    const stages = timeline?.stages ?? [];
    const stageValue = (index: number) => (stageUnit ? stages[index]?.unit_contributions?.[stageUnit] ?? 0 : 0);
    const signedEok = (manwon: number) => `${manwon >= 0 ? '+' : '−'}${toEok(Math.abs(manwon))}`;
    const saleCount = units.reduce((sum, unit) => sum + unit.count, 0);
    const rentalCount = result?.project.rental_count ?? 0;
    const totalCount = saleCount + rentalCount;
    const warnings: string[] = result?.warnings ?? [];

    //평형 구성 입력란에 채울 값.
    //  손대기 전에는 서버가 실제로 배분한 세대수에서 비율을 거꾸로 만들어 보여준다.
    //  그래야 "지금 뭘로 계산했는지" 가 보이고, 한 칸만 고쳐도 나머지가 유지된다
    //  반올림 오차는 가장 큰 줄에 몰아 합계를 정확히 100 으로 맞춘다 (그래야 손대지 않고도 「적용」 조건을 만족한다)
    const derivedRows: UnitMixEntry[] = units.map((unit) => ({
        exclusive_area_m2: unit.exclusive_area_m2,
        household_ratio: saleCount ? Math.round((unit.count / saleCount) * 1000) / 10 : 0,
    }));
    if (derivedRows.length > 0) {
        const drift = 100 - derivedRows.reduce((sum, row) => sum + row.household_ratio, 0);
        const largest = derivedRows.reduce((best, row, i) => (row.household_ratio > derivedRows[best].household_ratio ? i : best), 0);
        derivedRows[largest].household_ratio = Math.round((derivedRows[largest].household_ratio + drift) * 10) / 10;
    }
    const mixRows: UnitMixEntry[] =
        unitMix ?? (derivedRows.length > 0 ? derivedRows : [EMPTY_MIX_ROW]);

    //비율 합계 (세대수 기준 %). 100 을 넘을 수 없고, 100 이어야 적용할 수 있다
    const ratioSum = Math.round(mixRows.reduce((sum, row) => sum + (row.household_ratio || 0), 0) * 10) / 10;
    const ratioComplete = Math.abs(ratioSum - 100) < 0.05;

    //사용 면적 : 평형에 나눠 줄 수 있는 분양 공급면적(주택 공급면적 − 임대 − 기부 공공임대) 중 입력한 비율만큼.
    //  연면적이 아니다 — 지하·상가·공용(공급면적 밖)과 임대 몫은 평형에 쓸 수 없다
    const saleSupplyM2 = result?.project.sale_supply_m2 ?? 0;
    const usedSupplyM2 = saleSupplyM2 * Math.min(ratioSum, 100) / 100;

    //입력칸을 고치면 그 순간부터 사용자 값으로 계산한다 (서버 기본값에서 손 떼는 시점)
    //  비율은 다른 줄과 합쳐 100 을 넘지 않게 자른다
    const editRow = (index: number, key: keyof UnitMixEntry, raw: string) => {
        let value = raw === '' ? 0 : Number(raw);
        if (Number.isNaN(value) || value < 0) return;
        if (key === 'household_ratio') {
            const others = mixRows.reduce((sum, row, i) => (i === index ? sum : sum + (row.household_ratio || 0)), 0);
            value = Math.min(value, Math.max(Math.round((100 - others) * 10) / 10, 0));
        }
        onUnitMixChange(mixRows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
    };

    const addRow = () => {
        if (mixRows.length >= MAX_UNIT_TYPES) return;
        onUnitMixChange([...mixRows, { exclusive_area_m2: 0, household_ratio: 0 }]);
    };

    const removeRow = (index: number) => {
        if (mixRows.length <= 1) return;
        onUnitMixChange(mixRows.filter((_, i) => i !== index));
    };

    //내 필지 지정 시 그 필지의 원자료 (집합건물이면 전유면적 입력란을 띄운다)
    const ownerParcel = priorAsset?.parcels?.find((parcel) => parcel.pnu === ownerPnu) ?? null;
    const detail = result?.prior_asset_detail ?? null;

    const visibleSliders: SlidersState = Object.fromEntries(
        Object.entries(sliders).filter(([key]) =>
            tab === 'basic' ? BASIC_KEYS.includes(key) : !BASIC_KEYS.includes(key)
        )
    );

    return (
        <div className="w-full max-w-sm bg-white rounded-xl border border-gray-200 overflow-hidden">

            {/* 용도지역을 바꾸면 화면 숫자는 이전 용도지역 기준이다.
                /zone 재호출이 크레딧 1개를 더 쓰므로 자동으로 부르지 않는다 — 버튼을 기다린다 */}
            {zoningStale && (
                <div className="bg-amber-50 px-5 py-2.5 text-[11.5px] leading-relaxed text-amber-800">
                    <b>용도지역이 바뀌었습니다.</b> 아래 숫자는 아직 이전 용도지역 기준입니다.
                    위 <b>분담금 계산</b> 버튼을 다시 눌러 주세요 (크레딧 1개).
                </div>
            )}

            {/* 예상 분담금 : 평형을 고르게 하지 않고 분양 평형 전부를 깔아 보여준다.
                일반인은 자기가 고른 조건의 답을 바로 보고 싶어 한다 — 고르는 단계를 없앴다 */}
            <div className={`px-5 pt-4 pb-3 transition-opacity ${loading || zoningStale ? 'opacity-50' : 'opacity-100'}`}>
                <p className="text-xs tracking-wide text-gray-400">얼마GEO</p>
                <h1 className="mt-1 flex items-baseline gap-1.5 text-base font-semibold text-gray-900">
                    예상 분담금
                    {/* 어느 시점 기준인지 숨기지 않는다. 사업기간 슬라이더를 따라 움직인다 */}
                    <span className="text-[11px] font-normal text-gray-400">({periodLabel} 기준)</span>
                </h1>

                {units.length === 0 ? (
                    <p className="mt-2.5 rounded-lg border border-dashed border-gray-200 px-2.5 py-3 text-center text-[11.5px] text-gray-400">
                        {loading ? '필지를 분석하고 있습니다...' : '지도에서 필지를 선택하면 평형별 분담금이 표시됩니다'}
                    </p>
                ) : (
                    <ul className="mt-1.5 divide-y divide-gray-100">
                        {units.map((unit) => (
                            <li key={unit.name} className="flex items-baseline gap-2 py-1.5">
                                <span className="w-[72px] shrink-0 text-[13px] text-gray-500">
                                    <b className="font-semibold text-gray-900">{unit.name}형</b>
                                    {' '}
                                    {saleCount ? `${((unit.count / saleCount) * 100).toFixed(0)}%` : ''}
                                </span>
                                <span
                                    className={`ml-auto text-xl font-bold tabular-nums ${
                                        unit.contribution < 0 ? 'text-blue-600' : 'text-gray-900'
                                    }`}
                                >
                                    {toEok(Math.abs(unit.contribution))}
                                    <span className="ml-0.5 text-[11px] font-medium text-gray-500">
                                        억{unit.contribution < 0 ? ' 환급' : ''}
                                    </span>
                                </span>
                                {/* 명목 금액만 보여주면 공포를 준다. 받는 집값 대비 부담을 같이 적는다 */}
                                <span className="w-[66px] shrink-0 text-right text-[11px] tabular-nums text-gray-400">
                                    분양가 {(unit.contribution_ratio * 100).toFixed(0)}%
                                </span>
                            </li>
                        ))}
                    </ul>
                )}

                {/* 소형 평형 안내 : 모델은 일반분양 평형 지수를 조합원분양가에도 그대로 곱한다.
                    조합은 총회에서 평형별 조합원가를 따로 정하므로 소형은 어긋나기 쉽다 (미미삼 계획 : 39㎡ 가 ㎡당 가장 비쌌다) */}
                {units.some((unit) => parseFloat(unit.name) < 60) && (
                    <p className="mt-1.5 text-[11px] leading-snug text-gray-400">
                        60㎡ 미만 평형의 조합원분양가는 조합이 총회에서 정하는 평형별 구조에 따라 달라질 수 있습니다.
                        모델은 일반분양 평형 지수(청약홈 17개 단지)를 그대로 씁니다.
                    </p>
                )}

                {/* 권리가액은 평형과 무관해서 한 번만 적는다 (분담금 = 조합원분양가 − 권리가액) */}
                <p className="mt-1.5 text-[11px] text-gray-400">
                    권리가액 {toEok(result?.right_value ?? 0)}억
                    {rentalCount > 0 && totalCount > 0 && (
                        <> · 임대 {rentalCount.toLocaleString()}세대({((rentalCount / totalCount) * 100).toFixed(0)}%)는 조합원 분양 대상이 아니라 제외</>
                    )}
                </p>

                {/* 관리처분 확정 → 준공 정산.
                    조합원분양가는 고시일에 명목으로 묶이고 공사비는 기성 때까지 오른다 → 비례율이 깎여 추가분담금이 된다.
                    확정 이후 증액은 물가변동(지수)과 비물가 초과(사례 실측)로 나눠 보여준다 */}
                {timeline && stages.length === 4 && stageUnit && (
                    <div className="mt-2 rounded-lg bg-gray-50 px-2.5 py-2 text-[11px] tabular-nums text-gray-500">
                        <div className="flex justify-between">
                            <span>{stageUnit}형 · 관리처분 확정 ({timeline.mgmt_ym.slice(0, 4)})</span>
                            <span className="font-semibold text-gray-700">{toEok(stageValue(0))}억</span>
                        </div>
                        <div className="flex justify-between">
                            <span>분양·임대 시점 반영</span>
                            <span>{signedEok(stageValue(1) - stageValue(0))}억</span>
                        </div>
                        <div className="flex justify-between">
                            <span>공사비 물가변동 <span className="text-gray-400">(지수 ×{timeline.escalation_index.toFixed(2)})</span></span>
                            <span>{signedEok(stageValue(2) - stageValue(1))}억</span>
                        </div>
                        <div className="flex justify-between">
                            <span>
                                비물가 초과 증액{' '}
                                <span className="text-gray-400">
                                    (연 {(timeline.excess_rate * 100).toFixed(2)}% · {timeline.excess_basis} {timeline.excess_case_count}건)
                                </span>
                            </span>
                            <span>{signedEok(stageValue(3) - stageValue(2))}억</span>
                        </div>
                        <div className="mt-0.5 flex justify-between border-t border-gray-200 pt-0.5 font-semibold text-gray-700">
                            <span>준공 정산 ({timeline.complete_ym.slice(0, 4)})</span>
                            <span>{toEok(stageValue(3))}억</span>
                        </div>
                        <p className="mt-1 text-[10.5px] leading-relaxed text-gray-400">
                            공사비 {Math.round(timeline.cost_contract_per_pyeong).toLocaleString()} →{' '}
                            {Math.round(timeline.cost_final_per_pyeong).toLocaleString()}만원/평 (도급 → 기성 평균).
                            과거 추세가 이어진다고 본 값입니다.
                        </p>
                    </div>
                )}
            </div>
            <div className="mx-5 border-t border-gray-900" />

            {/* 계산 근거 지표 : 누르면 관련 슬라이더로 이동 */}
            <div className="grid grid-cols-2 gap-x-3.5 px-5 pb-2 pt-3">
                {metrics.map((metric) => (
                    <button
                        key={metric.label}
                        type="button"
                        onClick={() => focusSlider(metric.sliderKey)}
                        className="-mx-1.5 flex w-[calc(100%+12px)] items-baseline justify-between gap-1.5 rounded px-1.5 py-1 text-left hover:bg-blue-50"
                    >
                        <span className={`whitespace-nowrap text-gray-500 ${metric.compact ? 'text-[10.5px] tracking-tight' : 'text-[12.5px]'}`}>{metric.label}</span>
                        <span className={`whitespace-nowrap font-semibold tabular-nums text-gray-900 ${metric.compact ? 'text-[10.5px] tracking-tight' : 'text-[12.5px]'}`}>{metric.value}</span>
                    </button>
                ))}
            </div>

            {/* 계산에 반영된 정비계획 조건 : 사업성 보정계수 · 공공기여(상한용적률 산식·종상향) */}
            {((businessCorrection && businessCorrection.factor > 1)
                || (upzoning && upzoning.steps > 0)
                || (timeline?.public_contribution_ratio ?? 0) > 0) && (
                <div className="mx-5 mb-3 space-y-1 rounded-lg bg-blue-50 px-2.5 py-2 text-[11.5px] leading-relaxed text-blue-800">
                    {businessCorrection && businessCorrection.factor > 1 && (
                        <p>
                            사업성 보정계수 <b>×{businessCorrection.factor.toFixed(2)}</b> — {businessCorrection.project_type === '재건축'
                                ? '단지 공시지가가 서울시 공동주택 평균보다 낮아(대지면적·세대밀도 보정 포함)'
                                : '구역 공시지가가 서울시 평균보다 낮아'}
                            {' '}허용·상한 용적률을 올려 계산했습니다 (서울시 정비사업 사업성 개선방안).
                        </p>
                    )}
                    {upzoning && upzoning.steps > 0 && <p>{upzoning.note}</p>}
                    {/* 허용을 넘는 용적률은 공공기여(기부채납)로 받는다. 기부한 땅만큼 건축 대지가 준다 */}
                    {timeline && timeline.public_contribution_ratio > 0 && (
                        <p>
                            공공기여 <b>대지의 {(timeline.public_contribution_ratio * 100).toFixed(1)}%</b>를
                            공공시설 부지로 내놓는 것으로 계산했습니다 — 건축 대지{' '}
                            {Math.round(timeline.net_site_area_m2).toLocaleString()}㎡.
                            상한용적률 = 허용 × (1 + 1.3α), α = 기부 면적 ÷ 남은 대지 (서울시 2030 기본계획).
                            {timeline.public_contribution_ratio > 0.3 && (
                                <> 비율이 커서 실제로는 건축물·현금 기여로 나눠 낼 수 있습니다 (그러면 대지는 덜 줄고 비용이 듭니다).</>
                            )}
                        </p>
                    )}
                </div>
            )}

            {/* 경고 : 계산은 됐지만 결과를 의심해야 할 때 */}
            {warnings.length > 0 && (
                <div className="mx-5 mb-3 rounded-lg bg-amber-50 px-2.5 py-2 text-[11.5px] text-amber-800">
                    {warnings.map((warning) => (
                        <p key={warning} className="mb-1 last:mb-0">{warning}</p>
                    ))}
                </div>
            )}

            {/* 변수 조절 */}
            <div className="border-t border-gray-200 px-5 pb-5 pt-3.5">
                <div className="mb-3 flex items-center gap-2.5">
                    <h2 className="text-sm font-semibold text-gray-900">변수 조절</h2>
                    <div className="ml-auto flex gap-0.5 rounded-lg bg-gray-100 p-0.5" role="tablist">
                        {([['basic', '일반'], ['detail', '세부']] as const).map(([key, label]) => (
                            <button
                                key={key}
                                type="button"
                                role="tab"
                                aria-selected={tab === key}
                                onClick={() => setTab(key)}
                                className={`rounded-md px-3 py-1 text-[12.5px] transition ${
                                    tab === key ? 'bg-white font-semibold text-gray-900 shadow-sm' : 'text-gray-500'
                                }`}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* 평형 구성 : 세부 탭에만 둔다.
                    기본값으로 답을 먼저 보여주고, 직접 정하고 싶은 사람만 여기로 내려온다 */}
                {tab === 'detail' && (
                    <div id="field-unit_mix" className="mb-4 rounded-lg border border-gray-200 px-3 pb-2.5 pt-2.5">
                        <div className="flex items-center gap-2">
                            <h3 className="text-[12.5px] font-semibold text-gray-900">평형 구성</h3>
                            <span className="text-[10.5px] text-gray-400">
                                {mixRows.length}/{MAX_UNIT_TYPES}
                            </span>
                            {/* 사용 면적 (입력 비율만큼 / 분양 공급면적). 계산 결과가 있어야 분모를 안다 */}
                            {saleSupplyM2 > 0 && (
                                <span
                                    className={`text-[10.5px] tabular-nums ${ratioComplete ? 'text-gray-400' : 'text-amber-600'}`}
                                    title="분양 공급면적 = 주택 공급면적 − 임대 − 기부채납 공공임대 (연면적 아님)"
                                >
                                    사용 면적 ({Math.round(usedSupplyM2).toLocaleString()} / {Math.round(saleSupplyM2).toLocaleString()}㎡)
                                </span>
                            )}
                            <button
                                type="button"
                                onClick={addRow}
                                disabled={mixRows.length >= MAX_UNIT_TYPES}
                                className="ml-auto rounded-md border border-gray-200 px-2 py-0.5 text-[11.5px] text-gray-600 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                + 추가
                            </button>
                        </div>

                        {mixRows.map((row, index) => (
                            <div
                                key={index}
                                className="flex items-center gap-1.5 border-t border-dashed border-gray-200 py-1.5 first:border-t-0 first:pt-2"
                            >
                                <span className="text-[11.5px] text-gray-500">전용</span>
                                <input
                                    type="number"
                                    min={0}
                                    step={1}
                                    value={row.exclusive_area_m2 || ''}
                                    onChange={(e) => editRow(index, 'exclusive_area_m2', e.target.value)}
                                    className={INPUT_CLASS}
                                />
                                <span className="text-[11.5px] text-gray-400">㎡</span>
                                <span className="ml-auto text-[11.5px] text-gray-500">비율</span>
                                <input
                                    type="number"
                                    min={0}
                                    max={100}
                                    step={1}
                                    value={row.household_ratio || ''}
                                    onChange={(e) => editRow(index, 'household_ratio', e.target.value)}
                                    className={INPUT_CLASS}
                                />
                                <span className="text-[11.5px] text-gray-400">%</span>
                                <button
                                    type="button"
                                    onClick={() => removeRow(index)}
                                    disabled={mixRows.length <= 1}
                                    aria-label={`${index + 1}번째 평형 삭제`}
                                    className="rounded px-1 text-[12px] text-gray-300 transition hover:text-gray-600 disabled:cursor-not-allowed disabled:opacity-30"
                                >
                                    ✕
                                </button>
                            </div>
                        ))}

                        {/* 임대 : 평형만 고르게 한다. 비율은 용적률 완화분에서 법정으로 정해진다 */}
                        <div className="flex items-center gap-1.5 border-t border-gray-300 pt-2">
                            <span className="text-[11.5px] text-gray-500">임대 전용</span>
                            <input
                                type="number"
                                min={0}
                                step={1}
                                value={rentalExclusive ?? result?.rental_exclusive_area_m2 ?? ''}
                                onChange={(e) => {
                                    const raw = e.target.value;
                                    onRentalExclusiveChange(raw === '' ? null : Number(raw));
                                }}
                                className={INPUT_CLASS}
                            />
                            <span className="text-[11.5px] text-gray-400">㎡</span>
                            <span className="ml-auto text-[11.5px] text-gray-400">
                                비율{' '}
                                <b className="font-semibold text-gray-600 tabular-nums">
                                    {totalCount ? `${((rentalCount / totalCount) * 100).toFixed(0)}%` : '–'}
                                </b>
                                {' '}자동
                            </span>
                        </div>

                        {/* 입력 중간 상태(30 → 3 → 35)가 그대로 계산되면 안 되므로 적용을 분리한다.
                            크레딧은 추가로 들지 않는다 — 같은 토큰으로 다시 계산할 뿐이다 */}
                        <button
                            type="button"
                            onClick={onApplyUnitMix}
                            disabled={!unitMixDirty || !ratioComplete}
                            className={`mt-2 w-full rounded-md py-1.5 text-[12px] font-semibold transition ${
                                unitMixDirty && ratioComplete
                                    ? 'bg-gray-900 text-white hover:bg-gray-800'
                                    : 'bg-gray-100 text-gray-400'
                            }`}
                        >
                            {!ratioComplete
                                ? `비율 합계 ${ratioSum}% — ${Math.round((100 - ratioSum) * 10) / 10}% 남음`
                                : unitMixDirty ? '평형 구성 적용' : '적용됨'}
                        </button>

                        <p className="mt-1.5 text-[10.5px] leading-relaxed text-gray-400">
                            비율은 <b>세대수 기준</b>이고 합계가 100%여야 적용됩니다.
                            사용 면적은 평형에 나눠 줄 수 있는 분양 공급면적(주택 공급면적 − 임대) 기준입니다.
                            임대 비율은 용적률 완화분에서 법정으로 정해져 직접 바꿀 수 없습니다 (도시정비법 제54조).
                        </p>
                    </div>
                )}

                {/* 공공기여 방식 선택 : 평형 구성 아래. 토지 · 현금 · 공공임대 건축물을 기부면적 비율(%)로 섞는다.
                    버튼은 비율 프리셋이다 (토지 100 / 토지 50 + 현금 50 = 절반값 자동 입력 / 공공임대 100).
                    입력만 해서는 계산하지 않고 「적용」을 눌러야 한다. 현금은 기부면적의 절반까지 (시행령 제14조②).
                    아래 안내는 적용 뒤에는 서버가 계산 결과로 만든 문장, 입력 중에는 비율 설명·입력 오류다 */}
                {tab === 'detail' && (() => {
                    const mixError = contributionMixError(contributionMix);
                    const appliedMix = result?.timeline?.contribution_mix;
                    const serverNote = !contributionMixDirty && appliedMix && sameContributionMix(appliedMix, contributionMix)
                        ? result?.timeline?.contribution_note
                        : undefined;
                    return (
                        <div id="field-contribution_mix" className="mb-4 rounded-lg border border-gray-200 px-3 pb-2.5 pt-2.5">
                            <h3 className="text-[12.5px] font-semibold text-gray-900">공공기여 방식 선택</h3>
                            <div className="mt-2 flex gap-0.5 rounded-lg bg-gray-100 p-0.5" role="group" aria-label="공공기여 비율 프리셋">
                                {CONTRIBUTION_PRESETS.map(({ key, label, sub, mix }) => {
                                    const selected = sameContributionMix(contributionMix, mix);
                                    return (
                                        <button
                                            key={key}
                                            type="button"
                                            aria-pressed={selected}
                                            onClick={() => onContributionMixChange({ ...mix })}
                                            className={`flex-1 rounded-md px-1 py-1.5 text-[11.5px] leading-tight transition ${
                                                selected
                                                    ? 'bg-white font-semibold text-gray-900 shadow-sm'
                                                    : 'text-gray-500 hover:text-gray-700'
                                            }`}
                                        >
                                            {label}
                                            {sub && <span className="mt-0.5 block text-[10px] font-normal text-gray-400">{sub}</span>}
                                        </button>
                                    );
                                })}
                            </div>

                            <div className="mt-1.5">
                                {CONTRIBUTION_MIX_ROWS.map(({ key, label, limit }) => {
                                    //도로·공원 같은 기반시설은 땅으로 내므로 토지를 먼저 넣어야 나머지 칸이 열린다
                                    const locked = key !== 'land' && !(contributionMix.land > 0);
                                    return (
                                        <div
                                            key={key}
                                            className={`flex items-center gap-1.5 border-t border-dashed border-gray-200 py-1.5 first:border-t-0 ${
                                                locked ? 'opacity-40' : ''
                                            }`}
                                        >
                                            <span className="text-[11.5px] text-gray-500">{label}</span>
                                            {limit && <span className="text-[10.5px] text-gray-400">{limit}</span>}
                                            <input
                                                type="number"
                                                min={0}
                                                max={100}
                                                step={1}
                                                placeholder="0"
                                                value={contributionMix[key] || ''}
                                                disabled={locked}
                                                onChange={(e) => {
                                                    const raw = e.target.value;
                                                    const value = raw === '' ? 0 : Math.min(Math.max(Number(raw), 0), 100);
                                                    //토지를 비우면 현금·공공임대도 닫히므로 0 으로 되돌린다
                                                    onContributionMixChange(
                                                        key === 'land' && value <= 0
                                                            ? { land: 0, public_rental: 0, cash: 0 }
                                                            : { ...contributionMix, [key]: value }
                                                    );
                                                }}
                                                className={`ml-auto ${INPUT_CLASS} disabled:cursor-not-allowed disabled:bg-gray-50`}
                                            />
                                            <span className="text-[11.5px] text-gray-400">%</span>
                                        </div>
                                    );
                                })}
                            </div>

                            <button
                                type="button"
                                onClick={onApplyContributionMix}
                                disabled={!contributionMixDirty || mixError !== null}
                                className={`mt-1 w-full rounded-md py-1.5 text-[12px] font-semibold transition ${
                                    contributionMixDirty && mixError === null
                                        ? 'bg-gray-900 text-white hover:bg-gray-800'
                                        : 'bg-gray-100 text-gray-400'
                                }`}
                            >
                                {contributionMixDirty ? '공공기여 방식 적용' : '적용됨'}
                            </button>

                            {mixError ? (
                                <p className="mt-1.5 text-[10.5px] leading-relaxed text-red-500">{mixError}</p>
                            ) : (
                                <p className="mt-1.5 text-[10.5px] leading-relaxed text-gray-400">
                                    {serverNote ?? `${CONTRIBUTION_MIX_HINT}${contributionMixDirty ? ' 「적용」을 누르면 다시 계산합니다.' : ''}`}
                                </p>
                            )}
                        </div>
                    );
                })()}

                {/* 내 필지 지정 : 종전자산을 개인화하는 자리.
                    지정하지 않으면 구역 종전자산의 1인분이라 모든 조합원이 같은 분담금을 본다.
                    지정하면 내 토지·건물로 계산되어 "내 집이 구역 평균보다 덜 낡았나" 가 반영된다 */}
                {tab === 'detail' && (priorAsset?.parcels?.length ?? 0) > 0 && (
                    <div id="field-owner_pnu" className="mb-4 rounded-lg border border-gray-200 px-3 pb-2.5 pt-2.5">
                        <h3 className="text-[12.5px] font-semibold text-gray-900">내 필지</h3>
                        <select
                            value={ownerPnu}
                            onChange={(e) => onSelectOwnerPnu(e.target.value)}
                            className="mt-1.5 w-full rounded-md border border-gray-200 px-2 py-1.5 text-[12px] focus:border-blue-400 focus:outline-none"
                        >
                            <option value="">지정 안 함 (구역 평균 1인분)</option>
                            {priorAsset?.parcels?.map((parcel) => (
                                <option key={parcel.pnu} value={parcel.pnu}>
                                    {parcel.pnu.slice(-8)} · {Math.round(parcel.land_area_m2)}㎡
                                    {parcel.has_building
                                        ? ` · ${parcel.structure || '구조 미상'}${
                                            parcel.household_count > 1 ? ` ${parcel.household_count}세대` : ''
                                        }`
                                        : ' · 나대지'}
                                </option>
                            ))}
                        </select>

                        {/* 집합건물이면 내 몫을 나눠야 한다. 전유면적을 모르면 세대수로 균등 분할한다 */}
                        {ownerParcel && ownerParcel.household_count > 1 && (
                            <div className="mt-2 flex items-center gap-1.5 border-t border-dashed border-gray-200 pt-2">
                                <span className="text-[11.5px] text-gray-500">내 전용면적</span>
                                <input
                                    type="number"
                                    min={0}
                                    step={1}
                                    value={ownerExclusive ?? ''}
                                    onChange={(e) => {
                                        const raw = e.target.value;
                                        onOwnerExclusiveChange(raw === '' ? null : Number(raw));
                                    }}
                                    className={INPUT_CLASS}
                                />
                                <span className="text-[11.5px] text-gray-400">㎡</span>
                                {/* 내 몫은 서버가 계산해 돌려준다 (전유합계는 /contribution 에서만 조회한다 —
                                    대단지는 37페이지 9.7초라 구역 전 필지에 받을 수 없다) */}
                                <span className="ml-auto text-[11px] text-gray-400">
                                    {detail?.owner_share
                                        ? `내 몫 ${(detail.owner_share * 100).toFixed(3)}%${
                                            detail.owner_exclusive_total_m2
                                                ? ''
                                                : ` (${ownerParcel.household_count}세대 균등)`
                                        }`
                                        : `비우면 ${ownerParcel.household_count}세대 균등 분할`}
                                </span>
                            </div>
                        )}

                        <p className="mt-1.5 text-[10.5px] leading-relaxed text-gray-400">
                            {ownerPnu
                                ? <>이 필지의 토지·건물로 계산합니다. 건물이 구역 평균보다 새것이면 분담금이 줄어듭니다.</>
                                : <>지정하지 않으면 <b>구역 평균 조합원</b> 기준입니다. 내 필지를 고르면 개인화됩니다.</>}
                        </p>
                    </div>
                )}

                <Slider sliders={visibleSliders} onChange={onSliderChange} onAuto={onSliderAuto} />

                {/* 예측 기준 시점 · 안내 (재초환 문구는 재개발일 때만 — 재건축은 결과 경고에 따로 뜬다) */}
                <p className="mt-1 border-t border-dashed border-gray-200 pt-2.5 text-[10.5px] leading-relaxed text-gray-400">
                    - 공사비·일반분양가 기본값은 <b>{targetYm}</b> 기준 예측값, 건설공사비지수는 시점 보정, 분양가는 인근 분양 사례 기준입니다.
                    예측값이며, 확정 분담금은 감정평가·관리처분계획 인가 후 결정되고 금액은 미래 시점 명목가입니다.
                    {projectType === '재개발' && <> 해당 프로그램의 제시가격은 재초환을 명시하지 않습니다.</>}
                </p>
            </div>
        </div>
    );
}

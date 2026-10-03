import React, { useState } from 'react';
import { SlidersState } from '../hooks/useSlider';
import { ContributionResult, MetricRow, UnitOption } from '../hooks/useContribution';
import Slider from './Slider';

//변수 조절 탭 : 자주 쓰는 값은 일반, 나머지는 세부
const BASIC_KEYS = [
    'floor_area_ratio', 'member_count', 'general_price_per_m2',
    'construction_cost_per_pyeong', 'project_period_years',
];

interface ContributionPanelProps {
    result: ContributionResult | null;   //분담금 계산 결과 (/contribution 응답). 필지 선택 전에는 null
    metrics: MetricRow[];                //상단 지표 목록
    sliders: SlidersState;
    onSliderChange: (key: string, newValue: number | string) => void;
    selectedUnit: string;                //선택한 평형 이름 ("84")
    onSelectUnit: (name: string) => void;
    targetYm: string;                    //공사비·분양가 예측 기준 시점 "YYYY-MM"
    loading?: boolean;                   //재계산 중이면 값을 흐리게 표시한다
}

//만원 → 억 표기
const toEok = (manwon: number) => (manwon / 10000).toFixed(2);

//예상 분담금 패널
export default function ContributionPanel({
    result, metrics, sliders, onSliderChange, selectedUnit, onSelectUnit, targetYm, loading = false,
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

    //사업 기간 : 0 년이면 "현재", 아니면 "N년 후"
    const periodYears = Number(sliders.project_period_years?.value ?? 0);
    const periodLabel = periodYears > 0 ? `${periodYears}년 후` : '현재';

    //분담금이 선택 평형 분양가의 몇 % 인가. 명목 금액의 의미를 읽게 해주는 값이다
    const memberPrice = result?.member_price ?? 0;
    const burdenRatio = memberPrice > 0
        ? (((result?.contribution ?? 0) / memberPrice) * 100).toFixed(1)
        : '0.0';

    const options: UnitOption[] = result?.unit_options ?? [];
    const warnings: string[] = result?.warnings ?? [];
    const visibleSliders: SlidersState = Object.fromEntries(
        Object.entries(sliders).filter(([key]) =>
            tab === 'basic' ? BASIC_KEYS.includes(key) : !BASIC_KEYS.includes(key)
        )
    );

    return (
        <div className="w-full max-w-sm bg-white rounded-xl border border-gray-200 overflow-hidden">

            {/* 예상 분담금 */}
            <div className={`px-5 pt-4 pb-3 transition-opacity ${loading ? 'opacity-50' : 'opacity-100'}`}>
                <p className="text-xs tracking-wide text-gray-400">얼마GEO</p>
                <h1 className="mt-1 flex items-baseline gap-1.5 text-base font-semibold text-gray-900">
                    예상 분담금
                    {/* 어느 시점 기준인지 숨기지 않는다. 사업기간 슬라이더를 따라 움직인다 */}
                    <span className="text-[11px] font-normal text-gray-400">({periodLabel} 기준)</span>
                </h1>
                <p className="mt-1 text-3xl font-bold tracking-tight text-gray-900">
                    {toEok(result?.contribution ?? 0)}
                    <span className="ml-1 text-sm font-medium text-gray-500">억원</span>
                </p>

                {/* 명목 금액만 보여주면 공포를 준다. 받는 집값 대비 부담을 같이 적는다 */}
                {memberPrice > 0 && (
                    <p className="mt-0.5 text-xs text-gray-500">
                        선택 평형 분양가 {toEok(memberPrice)}억의 <b className="text-gray-700">{burdenRatio}%</b>
                    </p>
                )}
                <p className="mt-0.5 text-xs text-gray-400">
                    조합원분양가 {toEok(result?.member_price ?? 0)}억 − 권리가액 {toEok(result?.right_value ?? 0)}억
                </p>
            </div>
            <div className="mx-5 border-t border-gray-900" />

            {/* 희망 평형 선택 : 구역이 정해지기 전에는 평형·세대수를 알 수 없다 */}
            <div className="flex gap-1.5 px-5 py-3">
                {options.length === 0 && (
                    <p className="w-full rounded-lg border border-dashed border-gray-200 px-2.5 py-2.5 text-center text-[11.5px] text-gray-400">
                        {loading ? '필지를 분석하고 있습니다...' : '지도에서 필지를 선택하면 평형이 표시됩니다'}
                    </p>
                )}
                {options.map((option) => (
                    <button
                        key={option.name}
                        type="button"
                        onClick={() => onSelectUnit(option.name)}
                        aria-pressed={option.name === selectedUnit}
                        className={`flex-1 rounded-lg border px-1.5 py-2 text-center transition ${
                            option.name === selectedUnit
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-gray-200 bg-white hover:bg-gray-50'
                        }`}
                    >
                        <span className="block text-[13px] font-semibold text-gray-900">{option.name}형</span>
                        <span className="block text-[10.5px] text-gray-400">
                            {option.count.toLocaleString()}세대
                        </span>
                    </button>
                ))}
            </div>

            {/* 계산 근거 지표 : 누르면 관련 슬라이더로 이동 */}
            <div className="grid grid-cols-2 gap-x-3.5 px-5 pb-2">
                {metrics.map((metric) => (
                    <button
                        key={metric.label}
                        type="button"
                        onClick={() => focusSlider(metric.sliderKey)}
                        className="-mx-1.5 flex w-[calc(100%+12px)] items-baseline justify-between gap-1.5 rounded px-1.5 py-1 text-left hover:bg-blue-50"
                    >
                        <span className="whitespace-nowrap text-[12.5px] text-gray-500">{metric.label}</span>
                        <span className="whitespace-nowrap text-[12.5px] font-semibold tabular-nums text-gray-900">{metric.value}</span>
                    </button>
                ))}
            </div>

            {/* 주의 문구 + 계산식 */}
            <p className="px-5 pb-1.5 text-[11.5px] text-gray-400">
                위 값은 모두 <b>선택한 필지</b> 기준 예측값입니다.
            </p>
            <p className="mx-5 mb-3 rounded-lg bg-gray-50 px-2.5 py-2 text-[11px] leading-relaxed text-gray-400">
                비례율 = (종후자산 − 총사업비) ÷ 종전자산 &nbsp;·&nbsp;
                권리가액 = 종전자산 × 비례율 &nbsp;·&nbsp;
                <b className="text-gray-500">분담금 = 조합원분양가 − 권리가액</b>
            </p>

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

                <Slider sliders={visibleSliders} onChange={onSliderChange} />

                {/* 예측 기준 시점 */}
                <p className="mt-1 border-t border-dashed border-gray-200 pt-2.5 text-[10.5px] leading-relaxed text-gray-400">
                    공사비·일반분양가 기본값은 <b>{targetYm}</b> 기준 예측값,
                    건설공사비지수는 시점 보정, 분양가는 인근 분양 사례 기준
                </p>
            </div>
        </div>
    );
}

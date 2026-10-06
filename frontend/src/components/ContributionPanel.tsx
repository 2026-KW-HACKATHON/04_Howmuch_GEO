import React, { useState } from 'react';
import { SlidersState } from '../hooks/useSlider';
import {
    ContributionResult,
    MAX_UNIT_TYPES,
    MetricRow,
    UnitContribution,
    UnitMixEntry,
    ZonePriorAsset,
} from '../hooks/useContribution';
import Slider from './Slider';

//변수 조절 탭 : 자주 쓰는 값은 일반, 나머지는 세부
const BASIC_KEYS = [
    'floor_area_ratio', 'member_count', 'general_price_per_m2',
    'construction_cost_per_pyeong', 'project_period_years',
];

//평형 구성 입력란이 하나도 없을 때 보여줄 첫 줄 (아직 계산 결과가 없는 상태)
const EMPTY_MIX_ROW: UnitMixEntry = { exclusive_area_m2: 59, household_ratio: 30 };

interface ContributionPanelProps {
    result: ContributionResult | null;   //분담금 계산 결과 (/contribution 응답). 필지 선택 전에는 null
    metrics: MetricRow[];                //상단 지표 목록
    sliders: SlidersState;
    onSliderChange: (key: string, newValue: number | string) => void;
    unitMix: UnitMixEntry[] | null;      //사용자가 손댄 평형 구성. null 이면 서버 실측 기본값
    onUnitMixChange: (rows: UnitMixEntry[]) => void;
    rentalExclusive: number | null;      //사용자가 입력한 임대 전용면적. null 이면 서버 기본값
    onRentalExclusiveChange: (value: number | null) => void;
    onApplyUnitMix: () => void;          //평형·비율은 「적용」을 눌러야 계산에 반영된다
    unitMixDirty: boolean;               //입력값이 적용값과 다른가
    priorAsset: ZonePriorAsset | null;   //구역 종전자산 집계. 내 필지 목록이 여기 있다
    ownerPnu: string;                    //내 필지. 비우면 구역 1인분(ρ=1)
    onSelectOwnerPnu: (pnu: string) => void;
    ownerExclusive: number | null;       //집합건물에서 내 전유면적(㎡)
    onOwnerExclusiveChange: (value: number | null) => void;
    zoningStale: boolean;                //용도지역을 바꿨는데 아직 다시 분석하지 않았다
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
    result, metrics, sliders, onSliderChange,
    unitMix, onUnitMixChange, rentalExclusive, onRentalExclusiveChange,
    onApplyUnitMix, unitMixDirty,
    priorAsset, ownerPnu, onSelectOwnerPnu, ownerExclusive, onOwnerExclusiveChange,
    zoningStale, targetYm, loading = false,
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

    const units: UnitContribution[] = result?.unit_contributions ?? [];
    const saleCount = units.reduce((sum, unit) => sum + unit.count, 0);
    const rentalCount = result?.project.rental_count ?? 0;
    const totalCount = saleCount + rentalCount;
    const warnings: string[] = result?.warnings ?? [];

    //평형 구성 입력란에 채울 값.
    //  손대기 전에는 서버가 실제로 배분한 세대수에서 비율을 거꾸로 만들어 보여준다.
    //  그래야 "지금 뭘로 계산했는지" 가 보이고, 한 칸만 고쳐도 나머지가 유지된다
    const derivedRows: UnitMixEntry[] = units.map((unit) => ({
        exclusive_area_m2: unit.exclusive_area_m2,
        household_ratio: saleCount ? Math.round((unit.count / saleCount) * 1000) / 10 : 0,
    }));
    const mixRows: UnitMixEntry[] =
        unitMix ?? (derivedRows.length > 0 ? derivedRows : [EMPTY_MIX_ROW]);

    //입력칸을 고치면 그 순간부터 사용자 값으로 계산한다 (서버 기본값에서 손 떼는 시점)
    const editRow = (index: number, key: keyof UnitMixEntry, raw: string) => {
        const value = raw === '' ? 0 : Number(raw);
        if (Number.isNaN(value) || value < 0) return;
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

                {/* 권리가액은 평형과 무관해서 한 번만 적는다 (분담금 = 조합원분양가 − 권리가액) */}
                <p className="mt-1.5 text-[11px] text-gray-400">
                    권리가액 {toEok(result?.right_value ?? 0)}억
                    {rentalCount > 0 && totalCount > 0 && (
                        <> · 임대 {rentalCount.toLocaleString()}세대({((rentalCount / totalCount) * 100).toFixed(0)}%)는 조합원 분양 대상이 아니라 제외</>
                    )}
                </p>
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

                {/* 평형 구성 : 세부 탭에만 둔다.
                    기본값으로 답을 먼저 보여주고, 직접 정하고 싶은 사람만 여기로 내려온다 */}
                {tab === 'detail' && (
                    <div id="field-unit_mix" className="mb-4 rounded-lg border border-gray-200 px-3 pb-2.5 pt-2.5">
                        <div className="flex items-center gap-2">
                            <h3 className="text-[12.5px] font-semibold text-gray-900">평형 구성</h3>
                            <span className="text-[10.5px] text-gray-400">
                                {mixRows.length}/{MAX_UNIT_TYPES}
                            </span>
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
                            disabled={!unitMixDirty}
                            className={`mt-2 w-full rounded-md py-1.5 text-[12px] font-semibold transition ${
                                unitMixDirty
                                    ? 'bg-gray-900 text-white hover:bg-gray-800'
                                    : 'bg-gray-100 text-gray-400'
                            }`}
                        >
                            {unitMixDirty ? '평형 구성 적용' : '적용됨'}
                        </button>

                        <p className="mt-1.5 text-[10.5px] leading-relaxed text-gray-400">
                            비율은 <b>세대수 기준</b>입니다. 합이 100%가 아니어도 그 비율대로 맞춥니다.
                            임대 비율은 용적률 완화분에서 법정으로 정해져 직접 바꿀 수 없습니다 (도시정비법 제54조).
                        </p>
                    </div>
                )}

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

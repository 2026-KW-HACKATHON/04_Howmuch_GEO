import React from 'react';
import { SliderConfig, SliderValue, SlidersState } from '../hooks/useSlider';

//Slider Props
interface SliderProps {
    sliders: SlidersState;
    onChange: (key: string, newValue: SliderValue) => void;
    onAuto?: (key: string) => void;   //자동 슬라이더를 다시 자동으로 (조합원 분양가 비율)
}

//Slider Key 별 한글 라벨 매핑 사전
const SLIDER_LABELS: Record<string, string> = {
    floor_area_ratio: "용적률 (%)",
    member_count: "조합원 수 (명)",
    member_price_ratio: "조합원 분양가 비율",
    parking_margin: "주차 여유율 (법정 대비)",
    rental_floor_band: "임대동 층수",
    project_period_years: "사업 기간 (년)",
    other_cost_ratio: "기타 사업비 비율",
    commercial_ratio: "상가 비율",
    construction_cost_per_pyeong: "평당 공사비 (만원)",
    general_price_per_m2: "㎡당 일반분양가 (만원)",
};

//값 표시. 조합원 분양가 비율은 "일반분양가의 49%" 로 읽는다 — 0.49 는 할인율(51%)로 거꾸로 읽히기 쉽다
const formatValue = (key: string, value: SliderConfig['value']) => {
    if (value === null || value === undefined) return '–';
    if (key === 'member_price_ratio' && typeof value === 'number') return `일반분양가의 ${Math.round(value * 100)}%`;
    return String(value);
};

//자동 슬라이더 아래 문구 (키별). 없으면 공통 문구
const AUTO_NOTES: Record<string, { auto: string; manual: string }> = {
    member_price_ratio: {
        auto: '관리처분 비례율이 100%가 되도록 정한 값입니다. 움직이면 직접 정한 비율로 계산합니다.',
        manual: '직접 정한 비율로 계산 중입니다.',
    },
};

//일반 슬라이더 아래 상시 안내 (키별). 값의 근거와 단계에 따라 달라지는 범위를 알려준다
//  기타사업비 : 기본값은 정비계획 단계 중앙값, 관리처분 단계 실제 예산은 더 높다 (서버 engine_defaults 근거와 같은 수치)
const SLIDER_NOTES: Record<string, string> = {
    other_cost_ratio:
        '기본값은 관리처분 단계 실제 예산 중앙값입니다 (재개발 0.71 · 재건축 0.47, 보상비·금융비용 포함). 정비계획 단계 계획서는 0.36 안팎입니다.',
};

//범위 슬라이더 손잡이 지름(px). index.css 의 .range-dual 과 같아야 눈금이 손잡이 중심에 맞는다
const THUMB_PX = 16;

//노드 라벨을 전부 적는 최대 노드 수.
//  패널 폭(max-w-sm, 내용 약 340px)에 이보다 많은 라벨을 늘어놓으면 글자가 붙거나 오른쪽이 잘린다.
//  넘으면(임대동 층수 = 기본형건축비 9구간) 양 끝만 적는다 — 고른 값은 제목 줄에 이미 나온다.
//  용적률 노드(최대 5개)는 지금처럼 전부 적는다
const MAX_NODE_LABELS = 5;

//트랙 위 위치 → CSS left.
//  range input 의 손잡이 중심은 0% 에서 반지름만큼 안쪽, 100% 에서 반지름만큼 안쪽에 있다
const thumbLeft = (pct: number) => `calc(${pct}% + ${(0.5 - pct / 100) * THUMB_PX}px)`;

//손잡이 두 개짜리 범위 슬라이더 (사업 기간)
//   10 ──o────────o──────── 30
//        ↑        ↑
//     고시일    최종 인가
//  두 손잡이를 따로 1년씩 움직인다. 한쪽이 다른 쪽을 밀지 않는다 (2026-10-08).
//  고시일은 최종 인가 − gap.min 까지만, 최종 인가는 고시일 + gap.min 부터만 간다
//  (gap.min = 서울 아파트 공사기간 중앙값을 올린 값 — 관리처분 뒤 최소한 공사는 해야 준공한다)
function RangeSlider({ sliderKey, label, config, onChange }: {
    sliderKey: string;
    label: string;
    config: SliderConfig;
    onChange: (key: string, newValue: SliderValue) => void;
}) {
    const min = config.min ?? 0;
    const max = config.max ?? 30;
    const step = config.step ?? 1;
    const gapMin = config.gap?.min ?? 0;
    const [inner, outer] = Array.isArray(config.value)
        ? config.value
        : [Number(config.value), Number(config.value) + (config.gap?.value ?? 0)];
    const [innerLabel, outerLabel] = config.labels ?? ['시작', '끝'];
    const pct = (v: number) => ((v - min) / (max - min)) * 100;
    const thisYear = new Date().getFullYear();

    //고시일 : 최종 인가 − 최소 간격까지
    const moveInner = (v: number) => {
        onChange(sliderKey, [Math.min(Math.max(v, min), outer - gapMin), outer]);
    };

    //최종 인가 : 고시일 + 최소 간격부터
    const moveOuter = (v: number) => {
        onChange(sliderKey, [inner, Math.min(Math.max(v, inner + gapMin), max)]);
    };

    return (
        <div id={`field-${sliderKey}`} className="space-y-1 scroll-mt-4">
            <div className="flex justify-between text-[12.5px] font-medium text-gray-700">
                <span>{label}</span>
                <span className="font-bold text-blue-600">
                    {inner} → <span className="text-slate-800">{outer}</span>
                </span>
            </div>

            <div className="relative h-5">
                {/* 트랙 + 두 시점 사이 구간 */}
                <div className="absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 rounded-lg bg-gray-200" />
                <div
                    className="absolute top-1/2 h-2 -translate-y-1/2 bg-blue-200"
                    style={{ left: thumbLeft(pct(inner)), width: `calc(${thumbLeft(pct(outer))} - ${thumbLeft(pct(inner))})` }}
                />
                {/* 기준점 (고시일 분위수) */}
                {(config.ticks ?? []).map((t) => (
                    <div
                        key={t}
                        className="absolute top-1/2 h-3 w-px -translate-y-1/2 bg-gray-400"
                        style={{ left: thumbLeft(pct(t)) }}
                    />
                ))}
                <input
                    type="range"
                    aria-label={innerLabel}
                    min={min}
                    max={max}
                    step={step}
                    value={inner}
                    disabled={config.fixed}
                    onChange={(e) => moveInner(Number(e.target.value))}
                    className="range-dual absolute inset-0 h-5 w-full"
                />
                <input
                    type="range"
                    aria-label={outerLabel}
                    min={min}
                    max={max}
                    step={step}
                    value={outer}
                    disabled={config.fixed}
                    onChange={(e) => moveOuter(Number(e.target.value))}
                    className="range-dual range-dual-outer absolute inset-0 h-5 w-full"
                />
            </div>

            {/* 기준점 라벨 */}
            <div className="relative h-3 text-[10px] text-gray-400">
                {(config.ticks ?? []).map((t) => (
                    <span key={t} className="absolute -translate-x-1/2" style={{ left: thumbLeft(pct(t)) }}>
                        {t}
                    </span>
                ))}
            </div>

            {/* 두 시점이 언제인지 연도로 적는다 */}
            <div className="flex justify-between text-[10.5px] text-gray-500">
                <span>
                    <b className="font-semibold text-blue-600">{innerLabel}</b> {inner}년 후 · {thisYear + inner}
                </span>
                <span>
                    <b className="font-semibold text-slate-800">{outerLabel}</b> {outer}년 후 · {thisYear + outer}
                </span>
            </div>
        </div>
    );
}

//Slider 컴포넌트
export default function Slider({ sliders, onChange, onAuto }: SliderProps) {

    //Slider 데이터가 없다면
    if (!sliders || Object.keys(sliders).length === 0) {
        return <div className="text-[12.5px] text-gray-500">슬라이더 데이터가 없습니다. 구역을 먼저 조회해주세요.</div>;
    }

    return (
        <div className="space-y-3.5">
            {Object.entries(sliders).map(([key, config]) => {
                if (!config) return null;
                const isFixed = config.fixed;
                const labelText = SLIDER_LABELS[key] || key.replace(/_/g, ' ');

                //범위 슬라이더 : 손잡이 두 개 (사업 기간)
                if (config.range) {
                    return <RangeSlider key={key} sliderKey={key} label={labelText} config={config} onChange={onChange} />;
                }

                //노드 슬라이더 : 값이 정해진 지점으로만 정해지는 변수
                //  range input 에는 '인덱스' 를 태우고, 바깥으로는 실제 값(문자열 가능)을 넘긴다
                if (config.options) {
                    const nodes = config.options;
                    const idx = Math.max(nodes.indexOf(config.value as number | string), 0);
                    //단계명이 있으면 같이 적는다 (용적률 : 기준/허용/상한/법적상한)
                    const tiers = config.tiers && config.tiers.length === nodes.length ? config.tiers : null;
                    //그 노드에 필요한 토지 공공기여 (상한용적률 산식·종상향)
                    const contribution = config.contributions?.[idx] ?? 0;

                    return (
                    <div key={key} id={`field-${key}`} className="space-y-1 scroll-mt-4">
                        <div className="flex justify-between text-[12.5px] font-medium text-gray-700">
                        <span>{labelText}</span>
                        <span className="text-blue-600 font-bold">
                            {tiers ? `${tiers[idx]} ${String(config.value)}` : String(config.value)}
                            {contribution > 0 && (
                                <span className="ml-1 text-[11px] font-medium text-gray-500">
                                    · 공공기여 {(contribution * 100).toFixed(1)}%
                                </span>
                            )}
                        </span>
                        </div>

                        <input
                            type="range"
                            min={0}
                            max={nodes.length - 1}
                            step={1}
                            value={idx}
                            disabled={isFixed}
                            onChange={(e) => onChange(key, nodes[Number(e.target.value)])}
                            className={`w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer ${
                                isFixed ? 'opacity-50 cursor-not-allowed' : 'accent-blue-600'
                            }`}
                        />

                        {/* 노드 라벨 : 고를 수 있는 지점을 그대로 보여준다.
                            노드가 MAX_NODE_LABELS 보다 많으면 양 끝만 적는다 (칸이 좁아 라벨이 붙는다) */}
                        {nodes.length > MAX_NODE_LABELS ? (
                            <div className="flex justify-between text-[10.5px] text-gray-400">
                                <span>{String(nodes[0])}</span>
                                <span>{String(nodes[nodes.length - 1])}</span>
                            </div>
                        ) : (
                        <div className="flex justify-between text-[10.5px] text-gray-400">
                        {nodes.map((n, i) => (
                            <span
                                key={String(n)}
                                className={`text-center ${i === idx ? 'text-blue-600 font-semibold' : ''}`}
                            >
                                {tiers && <span className="block leading-tight">{tiers[i]}</span>}
                                {String(n)}
                            </span>
                        ))}
                        </div>
                        )}
                    </div>
                    );
                }

                return (
                <div key={key} id={`field-${key}`} className="space-y-1 scroll-mt-4">

                    {/* 상단 레이블 및 현재 값 표시. 자동 슬라이더는 「자동」 표시 또는 「자동으로」 버튼 */}
                    <div className="flex justify-between text-[12.5px] font-medium text-gray-700">
                    <span>{labelText}</span>
                    <span className="flex items-center gap-1.5">
                        {config.auto === true && (
                            <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10.5px] font-semibold text-blue-600">자동</span>
                        )}
                        {config.auto === false && onAuto && (
                            <button
                                type="button"
                                onClick={() => onAuto(key)}
                                className="rounded border border-gray-200 px-1.5 py-0.5 text-[10.5px] font-medium text-gray-500 hover:border-blue-300 hover:text-blue-600"
                            >
                                자동으로
                            </button>
                        )}
                        <span className="text-blue-600 font-bold">{formatValue(key, config.value)}</span>
                    </span>
                    </div>

                    {/* 슬라이더 Input. 자동이고 아직 계산 전이면(값 없음) 손잡이를 최솟값에 둔다 */}
                    <input
                        type="range"
                        min={config.min}
                        max={config.max}
                        step={key.includes('ratio') && !key.includes('construction') ? '0.01' : '1'}
                        value={Number(config.value ?? config.min ?? 0)}
                        disabled={isFixed}
                        onChange={(e) => onChange(key, Number(e.target.value))}
                        className={`w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer ${
                            isFixed ? 'opacity-50 cursor-not-allowed' : 'accent-blue-600'
                    }`}
                    />

                    {/* 하단 Min 및 Max 범위 표시 */}
                    <div className="flex justify-between text-[10.5px] text-gray-400">
                    <span>최소: {formatValue(key, config.min ?? null)}</span>
                    <span>최대: {formatValue(key, config.max ?? null)}</span>
                    </div>

                    {/* 키별 상시 안내 (기타사업비 등) */}
                    {SLIDER_NOTES[key] && (
                        <p className="text-[10.5px] leading-snug text-gray-500">{SLIDER_NOTES[key]}</p>
                    )}

                    {/* 자동 슬라이더 안내 */}
                    {config.auto !== undefined && (
                        <p className="text-[10.5px] leading-snug text-gray-500">
                            {(AUTO_NOTES[key] ?? { auto: '값을 자동으로 정합니다.', manual: '직접 정한 값으로 계산 중입니다.' })[config.auto ? 'auto' : 'manual']}
                        </p>
                    )}
                </div>
                );
            })}
        </div>
    );
}

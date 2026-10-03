import React from 'react';
import { SlidersState } from '../hooks/useSlider';

//Slider Props
interface SliderProps {
    sliders: SlidersState;
    onChange: (key: string, newValue: number | string) => void;
}

//Slider Key 별 한글 라벨 매핑 사전
const SLIDER_LABELS: Record<string, string> = {
    floor_area_ratio: "용적률 (%)",
    member_count: "조합원 수 (명)",
    member_price_ratio: "조합원 분양가 비율",
    parking_per_household: "세대당 주차대수",
    rental_floor_band: "임대동 층수",
    project_period_years: "사업 기간 (년)",
    other_cost_ratio: "기타 사업비 비율",
    commercial_ratio: "상가 비율",
    construction_cost_per_pyeong: "평당 공사비 (만원)",
    general_price_per_m2: "㎡당 일반분양가 (만원)",
};

//Slider 컴포넌트
export default function Slider({ sliders, onChange }: SliderProps) {

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

                //노드 슬라이더 : 값이 네 구간으로만 정해지는 변수
                //  range input 에는 '인덱스' 를 태우고, 바깥으로는 실제 값(문자열 가능)을 넘긴다
                if (config.options) {
                    const nodes = config.options;
                    const idx = Math.max(nodes.indexOf(config.value), 0);

                    return (
                    <div key={key} id={`field-${key}`} className="space-y-1 scroll-mt-4">
                        <div className="flex justify-between text-[12.5px] font-medium text-gray-700">
                        <span>{labelText}</span>
                        <span className="text-blue-600 font-bold">{config.value}</span>
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

                        {/* 노드 라벨 : 고를 수 있는 지점을 그대로 보여준다 */}
                        <div className="flex justify-between text-[10.5px] text-gray-400">
                        {nodes.map((n, i) => (
                            <span key={String(n)} className={i === idx ? 'text-blue-600 font-semibold' : ''}>
                                {String(n)}
                            </span>
                        ))}
                        </div>
                    </div>
                    );
                }

                return (
                <div key={key} id={`field-${key}`} className="space-y-1 scroll-mt-4">

                    {/* 상단 레이블 및 현재 값 표시 */}
                    <div className="flex justify-between text-[12.5px] font-medium text-gray-700">
                    <span>{labelText}</span>
                    <span className="text-blue-600 font-bold">{config.value}</span>
                    </div>

                    {/* 슬라이더 Input */}
                    <input
                        type="range"
                        min={config.min}
                        max={config.max}
                        step={key.includes('ratio') && !key.includes('construction') ? '0.01' : '1'}
                        value={config.value}
                        disabled={isFixed}
                        onChange={(e) => onChange(key, Number(e.target.value))}
                        className={`w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer ${
                            isFixed ? 'opacity-50 cursor-not-allowed' : 'accent-blue-600'
                    }`}
                    />

                    {/* 하단 Min 및 Max 범위 표시 */}
                    <div className="flex justify-between text-[10.5px] text-gray-400">
                    <span>최소: {config.min}</span>
                    <span>최대: {config.max}</span>
                    </div>
                </div>
                );
            })}
        </div>
    );
}
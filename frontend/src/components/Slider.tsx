import React from 'react';
import { SlidersState } from '../hooks/useSlider';

//Slider Props
interface SliderProps {
    sliders: SlidersState;
    onChange: (key: string, newValue: number) => void;
}

//Slider Key 별 한글 라벨 매핑 사전
const SLIDER_LABELS: Record<string, string> = {
    floor_area_ratio: "용적률 (%)",
    member_price_ratio: "조합원 분양가 비율",
    other_cost_ratio: "기타 사업비 비율",
    commercial_ratio: "상가 비율",
    construction_cost_per_pyeong: "평당 공사비 (만원)",
    general_price_per_m2: "㎡당 일반분양가 (만원)",
    proportional_rate: "비례율 (%)",
};

//Slider 컴포넌트
export default function Slider({ sliders, onChange }: SliderProps) {

    //Slider 데이터가 없다면
    if (!sliders || Object.keys(sliders).length === 0) {
        return <div className="p-4 text-gray-500">슬라이더 데이터가 없습니다. 구역을 먼저 조회해주세요.</div>;
    }

    return (
        <div className="p-6 bg-white rounded-xl shadow-md space-y-6 max-w-md mx-auto">
            {Object.entries(sliders).map(([key, config]) => {
                if (!config) return null;
                const isFixed = config.fixed;
                const labelText = SLIDER_LABELS[key] || key.replace(/_/g, ' ');

                return (
                <div key={key} className="space-y-1">

                    {/* 상단 레이블 및 현재 값 표시 */}
                    <div className="flex justify-between text-sm font-medium text-gray-700">
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
                    <div className="flex justify-between text-xs text-gray-400">
                    <span>최소: {config.min}</span>
                    <span>최대: {config.max}</span>
                    </div>
                </div>
                );
            })}
        </div>
    );
}
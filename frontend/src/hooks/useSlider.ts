import { useState, useEffect } from 'react';

//Slider 개별 설정 타입
export interface SliderConfig {
  value: number;
  min: number;
  max: number;
  fixed?: boolean;
}

//전체 Slider 상태 딕셔너리 타입
export type SlidersState = Record<string, SliderConfig>;

//Slider Hook
export function useSlider(initialSliders: SlidersState = {}) {
    const [sliders, setSliders] = useState<SlidersState>(initialSliders);

    //백엔드에서 초기 데이터가 새로 들어왔을 때 상태 동기화
    useEffect(() => {
        if (initialSliders) {
        setSliders(initialSliders);
        }
    }, [initialSliders]);

    //개별 Slider 값 변경 Handler
    const handleSliderChange = (key: string, newValue: number | string) => {
        setSliders((prev) => ({
        ...prev,
        [key]: {
            ...prev[key],
            value: Number(newValue),
        },
        }));
    };

    //value 만 뽑아서 1차원 형식의 Dict 으로 전환
    const getFormattedSlidersForApi = (): Record<string, number> => {
        return Object.fromEntries(
        Object.entries(sliders).map(([key, config]) => [key, config.value])
        );
    };

    return {
        sliders,
        setSliders,
        handleSliderChange,
        getFormattedSlidersForApi,
    };
}
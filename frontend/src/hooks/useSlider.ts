import { useState, useEffect } from 'react';

//Slider 개별 설정 타입
//  options 가 있으면 노드 슬라이더다 (o────o────o────o). 중간값이 의미 없는 값에 쓴다
//    임대동 층수 : 표준건축비 표가 네 구간으로만 나뉜다
//    사업 기간   : 분위수(하위25%/중앙값/상위75%/노원구 실적)에서 뽑은 네 지점
export interface SliderConfig {
  value: number | string;
  min?: number;
  max?: number;
  options?: (number | string)[];
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
    //  노드 슬라이더는 문자열 값("11~20층")을 쓰므로 Number() 로 변환하면 안 된다
    const handleSliderChange = (key: string, newValue: number | string) => {
        setSliders((prev) => ({
        ...prev,
        [key]: {
            ...prev[key],
            value: prev[key]?.options ? newValue : Number(newValue),
        },
        }));
    };

    //value 만 뽑아서 1차원 형식의 Dict 으로 전환
    const getFormattedSlidersForApi = (): Record<string, number | string> => {
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
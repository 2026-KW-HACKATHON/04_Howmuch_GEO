import { useState, useEffect } from 'react';

//Slider 개별 설정 타입
//  options 가 있으면 노드 슬라이더다 (o────o────o────o). 중간값이 의미 없는 값에 쓴다
//    임대동 층수 : 기본형건축비 표가 아홉 층수 구간으로만 나뉜다
//    용적률      : 기준/허용/상한/법적상한 4단 (tiers 에 단계명)
//  range 면 손잡이 두 개짜리 범위 슬라이더다. value 가 [안쪽, 바깥] 이다
//    사업 기간   : [분담금 고시일, 최종 인가]. 두 손잡이를 따로 1년씩 움직이고,
//                  둘 사이는 gap.min(서울 아파트 공사기간 중앙값) 이상만 벌어져 있으면 된다
//  auto 가 있으면 자동 슬라이더다. true 면 값을 서버가 정하고(요청에는 null 로 보낸다),
//    손잡이를 움직이면 false 가 되어 그 값을 보낸다
//    조합원 분양가 비율 : 관리처분 비례율 100% 가 되도록 서버가 역산한다. 계산 전에는 value 가 null
export interface SliderConfig {
  value: number | string | number[] | null;
  auto?: boolean;
  min?: number;
  max?: number;
  step?: number;
  options?: (number | string)[];
  tiers?: string[];                 //노드 이름 (options 와 같은 순서)
  contributions?: number[];         //노드별 토지 공공기여 비율 (용적률 : 종상향 최소 + 상한용적률 산식)
  min_contribution?: number;        //종상향 최소 공공기여 (순부담). 토지가 아닌 공공기여 방식의 하한
  range?: boolean;
  ticks?: number[];                 //범위 슬라이더 트랙에 찍을 기준점
  gap?: { value: number; min: number; max: number };
  labels?: string[];                //범위 슬라이더 손잡이 이름 [안쪽, 바깥]
  fixed?: boolean;
}

//Slider 값 (노드 슬라이더는 문자열, 범위 슬라이더는 [안쪽, 바깥])
export type SliderValue = number | string | number[];

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
    //  노드 슬라이더는 문자열 값("16~25층")을, 범위 슬라이더는 배열을 쓰므로 Number() 로 변환하면 안 된다
    const handleSliderChange = (key: string, newValue: SliderValue) => {
        setSliders((prev) => ({
        ...prev,
        [key]: {
            ...prev[key],
            value: prev[key]?.options || Array.isArray(newValue) ? newValue : Number(newValue),
            //자동 슬라이더는 손잡이를 움직이는 순간 사용자 값이 된다
            ...(prev[key]?.auto !== undefined ? { auto: false } : {}),
        },
        }));
    };

    //value 만 뽑아서 1차원 형식의 Dict 으로 전환. 자동 슬라이더는 null (서버가 정한다)
    const getFormattedSlidersForApi = (): Record<string, SliderValue | null> => {
        return Object.fromEntries(
        Object.entries(sliders).map(([key, config]) => [key, config.auto ? null : config.value])
        );
    };

    return {
        sliders,
        setSliders,
        handleSliderChange,
        getFormattedSlidersForApi,
    };
}
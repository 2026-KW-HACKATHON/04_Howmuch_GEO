import { useState } from 'react';
import { SlidersState } from '../hooks/useSlider';

//예측 폼 Hook Props
export interface ModelPredictFormProps {
    onHandleZoneData: (pnus: string[]) => Promise<any>;
    onCalculateContribution: (requestData: any) => Promise<any>;
    selectedPnus: string[];
}

//예측 폼 Hook 
export function useModelPredictForm({ onHandleZoneData, onCalculateContribution, selectedPnus }: ModelPredictFormProps) {
    //구역 기본 정보 useState 영역
    const [formData, setFormData] = useState({
        name: "사용자 지정 구역",
        project_type: 0, 
        member_count: 2, 
    });

    //조합원 개인 정보 useState 영역
    const [ownerData, setOwnerData] = useState({
        desired_unit: "84",
        official_price: 25000,
    });

    //슬라이더 변수 상태
    const [sliderData, setSliderData] = useState<SlidersState>({
        floor_area_ratio: { value: 200, min: 200, max: 250 },
        member_price_ratio: { value: 0.8, min: 0.7, max: 0.9 },
        other_cost_ratio: { value: 0.35, min: 0.25, max: 0.45 },
        commercial_ratio: { value: 0.03, min: 0.0, max: 0.2 },
        construction_cost_per_pyeong: { value: 850, min: 700, max: 1000 },
        general_price_per_m2: { value: 998.25, min: 700, max: 1300 },
        proportional_rate: { value: 100, min: 80, max: 120, fixed: true },
    });

    //결과 및 로딩 상태 useState 영역
    const [zoneInfo, setZoneInfo] = useState<any>(null);
    const [calcResult, setCalcResult] = useState<any>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    //기본 Input Change Handler
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData((prev: any) => ({
            ...prev,
            [name]: value === '' ? '' : Number(value),
        }));
    };

    //슬라이더 값 변경 Handler
    const handleSliderChange = (key: string, newValue: number) => {
        setSliderData((prev: any) => ({
            ...prev,
            [key]: {
                ...prev[key],
                value: newValue,
            },
        }));
    };

    //Zone 호출 Handler
    const handleZoneData = async () => {
        setLoading(true);
        setError(null);
        try {
            const pnus = selectedPnus;
            const data = await onHandleZoneData(pnus);
            
            if (data && data.zone) {
                setZoneInfo(data.zone);
                if (data.sliders) {
                    setSliderData(data.sliders);
                }
            }
        } catch (err) {
            setError("구역 정보를 불러오는 중 오류가 발생했습니다.");
        } finally {
            setLoading(false);
        }
    };

    //Contribution 호출 Handler
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!zoneInfo) {
            alert("먼저 구역 분석을 진행해주세요!");
            return;
        }

        setLoading(true);
        setError(null);
        setCalcResult(null);

        try {
            //슬라이더 객체에서 value만 뽑아서 1차원 딕셔너리로 변환
            const formattedSliders = Object.fromEntries(
                Object.entries(sliderData).map(([key, config]: [any, any]) => [key, config.value])
            );

            const requestPayload = {
                name: formData.name,
                site_area_m2: zoneInfo.site_area_m2,
                member_count: Number(formData.member_count),
                sliders: formattedSliders,
                far_base: zoneInfo.far_min,
                owner: {
                    desired_unit: ownerData.desired_unit,
                    official_price: Number(ownerData.official_price),
                }
            };
            
            const data = await onCalculateContribution(requestPayload);
            setCalcResult(data);
        } catch (err) {
            setError("분담금 계산 중 오류가 발생했습니다.");
        } finally {
            setLoading(false);
        }
    };

    return {
        formData,
        setFormData,
        ownerData,
        setOwnerData,
        sliderData,
        zoneInfo,
        calcResult,
        loading,
        error,
        handleChange,
        handleSliderChange,
        handleZoneData,
        handleSubmit,
    };
}
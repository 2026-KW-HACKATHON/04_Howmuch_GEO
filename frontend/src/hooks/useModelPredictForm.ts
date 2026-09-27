import { useCallback, useEffect, useRef, useState } from 'react';
import { SlidersState } from '../hooks/useSlider';
import { ContributionResult, MemberCountRange, ZoneInfo } from './useContribution';

//슬라이더를 움직인 뒤 다시 계산하기까지 기다리는 시간
const RECALC_DEBOUNCE_MS = 250;

//필지를 연달아 클릭할 때 마지막 선택만 분석하도록 기다리는 시간
const ZONE_DEBOUNCE_MS = 400;

//세대수 자료가 없을 때 쓰는 임시 조합원 수 슬라이더
//  첫 계산 응답의 member_count_range 로 범위가 교체된다 (분양 세대수 상한 반영)
const MEMBER_COUNT_FALLBACK = { value: 2, min: 1, max: 1000 };

//예측 폼 Hook Props
export interface ModelPredictFormProps {
    onHandleZoneData: (pnus: string[]) => Promise<any>;
    onCalculateContribution: (requestData: any) => Promise<any>;
    selectedPnus: string[];
}

//예측 폼 Hook 
export function useModelPredictForm({ onHandleZoneData, onCalculateContribution, selectedPnus }: ModelPredictFormProps) {
    //API 호출 함수는 부모가 매 렌더 새로 만들 수 있다
    //  의존성에 그대로 넣으면 디바운스 타이머가 매번 취소돼 호출이 영원히 안 나간다
    const zoneApiRef = useRef(onHandleZoneData);
    zoneApiRef.current = onHandleZoneData;

    const contributionApiRef = useRef(onCalculateContribution);
    contributionApiRef.current = onCalculateContribution;

    //구역 기본 정보 useState 영역
    const [formData, setFormData] = useState({
        name: "사용자 지정 구역",
        project_type: 0, 
        member_count: 2, 
    });

    //조합원 개인 정보 useState 영역
    //  공시가격은 입력받지 않는다. 선택 구역 공시지가를 조합원 수로 나눈 1인분을 서버가 쓴다
    const [ownerData, setOwnerData] = useState({
        desired_unit: "84",
    });

    //구역 분석 완료 여부
    const [zoneCalculated, setZoneCalculated] = useState<boolean>(false);

    //슬라이더 변수 상태
    const [sliderData, setSliderData] = useState<SlidersState>({
        floor_area_ratio: { value: 200, min: 200, max: 250 },
        member_count: MEMBER_COUNT_FALLBACK,
        member_price_ratio: { value: 0.8, min: 0.7, max: 0.9 },
        other_cost_ratio: { value: 0.35, min: 0.25, max: 0.45 },
        commercial_ratio: { value: 0.03, min: 0.0, max: 0.2 },
        construction_cost_per_pyeong: { value: 850, min: 700, max: 1000 },
        general_price_per_m2: { value: 998.25, min: 700, max: 1300 },
        proportional_rate: { value: 100, min: 80, max: 120, fixed: true },
    });

    //조합원 수 범위 (/contribution 응답). 슬라이더 범위를 맞추는 데 쓴다
    const [memberRange, setMemberRange] = useState<MemberCountRange | null>(null);

    //공사비·분양가 예측 기준 시점 ("YYYY-MM"). /zone 응답값으로 덮어쓴다
    const [targetYm, setTargetYm] = useState<string>(new Date().toISOString().slice(0, 7));

    //결과 및 로딩 상태 useState 영역
    const [zoneInfo, setZoneInfo] = useState<ZoneInfo | null>(null);
    const [calcResult, setCalcResult] = useState<ContributionResult | null>(null);
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

    //희망 평형 선택 Handler (패널의 평형 버튼)
    const handleSelectUnit = (name: string) => {
        setOwnerData((prev) => ({ ...prev, desired_unit: name }));
    };

    //Zone 호출 Handler
    const handleZoneData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const pnus = selectedPnus;
            const data = await zoneApiRef.current(pnus);
            
            if (data && data.zone) {
                setZoneInfo(data.zone);
                if (data.target_ym) {
                    setTargetYm(data.target_ym);
                }
                if (data.sliders) {
                    //세대수 자료가 없으면 백엔드가 조합원 수 슬라이더를 만들지 않으므로 임시값을 채운다
                    setSliderData({
                        ...data.sliders,
                        member_count: data.sliders.member_count ?? MEMBER_COUNT_FALLBACK,
                    });
                }
                setZoneCalculated(true);
            }
        } catch (err) {
            setError("구역 정보를 불러오는 중 오류가 발생했습니다.");
        } finally {
            setLoading(false);
        }
    }, [selectedPnus]);

    //지도에서 필지를 고르면 바로 분석한다. 선택을 모두 지우면 값을 0으로 되돌린다
    useEffect(() => {
        if (selectedPnus.length === 0) {
            setZoneInfo(null);
            setCalcResult(null);
            setMemberRange(null);
            setZoneCalculated(false);
            setError(null);
            return;
        }

        const timer = setTimeout(() => { handleZoneData(); }, ZONE_DEBOUNCE_MS);
        return () => clearTimeout(timer);
    }, [handleZoneData, selectedPnus]);

    //Contribution 호출 (슬라이더가 바뀔 때마다 자동으로 다시 계산된다)
    const calculate = useCallback(async () => {
        if (!zoneInfo) return;

        setLoading(true);
        setError(null);

        try {
            //슬라이더 객체에서 value만 뽑아서 1차원 딕셔너리로 변환
            const formattedSliders = Object.fromEntries(
                Object.entries(sliderData).map(([key, config]: [any, any]) => [key, config.value])
            );

            //조합원 수는 ProjectParams 슬라이더가 아니라 별도 필드로 넘긴다
            const { member_count, ...engineSliders } = formattedSliders;
            const sentMemberCount = Number(member_count ?? formData.member_count);

            const requestPayload = {
                name: formData.name,
                site_area_m2: zoneInfo.site_area_m2,
                member_count: sentMemberCount,
                sliders: engineSliders,
                far_base: zoneInfo.far_min,
                land_value_total: zoneInfo.land_value_total,
                owner: {
                    desired_unit: ownerData.desired_unit,
                }
            };
            
            const data = await contributionApiRef.current(requestPayload);

            const range: MemberCountRange | undefined = data?.member_count_range;
            if (range) {
                setMemberRange(range);
            }

            //구역을 처음 분석할 때는 조합원 수를 몰라서 임시값(MEMBER_COUNT_FALLBACK)으로 호출한다
            //  그 결과는 화면에 쓰지 않고 버린다. 범위를 반영해 곧 다시 계산되기 때문이다
            const provisional = range && (sentMemberCount < range.min || sentMemberCount > range.max);
            if (!provisional) {
                setCalcResult(data);
            }
        } catch (err) {
            setError("분담금 계산 중 오류가 발생했습니다.");
        } finally {
            setLoading(false);
        }
    }, [zoneInfo, sliderData, ownerData, formData.name, formData.member_count]);

    //구역 분석 후에는 값이 바뀔 때마다 자동 재계산 (연속 드래그는 마지막 값만 호출)
    useEffect(() => {
        if (!zoneCalculated || !zoneInfo) return;

        const timer = setTimeout(() => { calculate(); }, RECALC_DEBOUNCE_MS);
        return () => clearTimeout(timer);
    }, [zoneCalculated, zoneInfo, calculate]);

    //조합원 수 슬라이더 범위 갱신 : 용적률·상가비율에 따라 분양 세대수가 바뀌면 상한도 바뀐다
    //  범위를 벗어난 값(구역 분석 직후의 임시값)은 최솟값으로 맞춘다
    useEffect(() => {
        const range = memberRange;
        if (!range) return;

        setSliderData((prev) => {
            const current = prev.member_count;
            const value = Math.min(Math.max(current?.value ?? range.min, range.min), range.max);

            //같은 범위면 상태를 그대로 둔다 (재계산 반복 방지)
            if (current && current.min === range.min && current.max === range.max && current.value === value) {
                return prev;
            }
            return { ...prev, member_count: { value, min: range.min, max: range.max } };
        });
    }, [memberRange]);

    //수동 재계산 (폼 submit)
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!zoneInfo) {
            alert("먼저 구역 분석을 진행해주세요!");
            return;
        }
        await calculate();
    };

    return {
        formData,
        setFormData,
        ownerData,
        setOwnerData,
        sliderData,
        zoneInfo,
        targetYm,
        calcResult,
        loading,
        error,
        handleChange,
        handleSliderChange,
        handleSelectUnit,
        handleZoneData,
        handleSubmit,
        zoneCalculated,
    };
}

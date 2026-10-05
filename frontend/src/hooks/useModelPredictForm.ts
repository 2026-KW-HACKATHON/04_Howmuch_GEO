import { useCallback, useEffect, useRef, useState } from 'react';
import { SlidersState } from '../hooks/useSlider';
import { ContributionResult, MemberCountRange, ZoneInfo } from './useContribution';

//슬라이더를 움직인 뒤 다시 계산하기까지 기다리는 시간
const RECALC_DEBOUNCE_MS = 250;

//세대수 자료가 없을 때 쓰는 임시 조합원 수 슬라이더
//  첫 계산 응답의 member_count_range 로 범위가 교체된다 (분양 세대수 상한 반영)
const MEMBER_COUNT_FALLBACK = { value: 2, min: 1, max: 1000 };

//용도지역 버튼 초기 목록 (서버 응답 전에 쓰는 값. AI/engine/zone.py SELECTABLE_ZONING 과 같아야 한다)
//  재개발은 사실상 주거지역에서만 일어나므로 주거지역만 연다
const DEFAULT_ZONING_OPTIONS = [
    '제1종전용주거지역',
    '제2종전용주거지역',
    '제1종일반주거지역',
    '제2종일반주거지역',
    '제3종일반주거지역',
    '준주거지역',
];

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
        member_price_ratio: { value: 0.8, min: 0.75, max: 0.95 },
        other_cost_ratio: { value: 0.35, min: 0.25, max: 0.45 },
        parking_per_household: { value: 1.3, min: 1.0, max: 2.0 },
        //상한은 용도지역별로 다르다 (전용 0.03 / 1종 0.05 / 2·3종 0.10 / 준주거 0.30).
        //  서버가 zone 응답에서 대표 용도지역에 맞는 max 를 내려주므로 여기 값은 그때 교체된다
        commercial_ratio: { value: 0.02, min: 0.0, max: 0.1 },
        construction_cost_per_pyeong: { value: 850, min: 700, max: 1000 },
        general_price_per_m2: { value: 998.25, min: 700, max: 1300 },
        rental_floor_band: { value: '11~20층', options: ['5층 이하', '6~10층', '11~20층', '21층 이상'] },
        project_period_years: { value: 13, options: [11, 13, 16, 18] },
    });

    //조합원 수 범위 (/contribution 응답). 슬라이더 범위를 맞추는 데 쓴다
    const [memberRange, setMemberRange] = useState<MemberCountRange | null>(null);

    //공사비·분양가 예측 기준 시점 ("YYYY-MM"). /zone 응답값으로 덮어쓴다
    //사용자가 고른 용도지역
    //  목록 초기값을 두는 이유 : 서버가 zoning_options 를 내려주려면 먼저 계산해야 하는데,
    //  계산하려면 용도지역을 골라야 해서 서로 물린다. 초기값으로 먼저 고르게 하고
    //  첫 응답이 오면 서버 목록으로 덮어쓴다 (엔진 FAR_TABLE 과 어긋나지 않게)
    const [selectedZoning, setSelectedZoning] = useState<string>('');
    const [zoningOptions, setZoningOptions] = useState<string[]>(DEFAULT_ZONING_OPTIONS);

    const [targetYm, setTargetYm] = useState<string>(new Date().toISOString().slice(0, 7));

    //결과 및 로딩 상태 useState 영역
    const [zoneInfo, setZoneInfo] = useState<ZoneInfo | null>(null);
    const [calcResult, setCalcResult] = useState<ContributionResult | null>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const [initialCalculationPending, setInitialCalculationPending] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    //기본 Input Change Handler
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData((prev: any) => ({
            ...prev,
            [name]: value === '' ? '' : Number(value),
        }));
    };

    //용도지역 선택 Handler
    //  용도지역이 바뀌면 용적률 범위가 달라지므로 구역을 다시 분석해야 한다.
    //  값만 담아두고, 실제 계산은 사용자가 계산 버튼을 눌렀을 때 일어난다
    const handleSelectZoning = (zoning: string) => {
        setSelectedZoning(zoning);
        setZoneCalculated(false);
    };

    //슬라이더 값 변경 Handler
    //  노드 슬라이더(임대동 층수)는 문자열 값을 쓰므로 number 로 좁히면 안 된다
    const handleSliderChange = (key: string, newValue: number | string) => {
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
        setInitialCalculationPending(true);
        setLoading(true);
        setError(null);
        try {
            const pnus = selectedPnus;
            const data = await zoneApiRef.current(pnus, selectedZoning || undefined);
            
            if (data && data.zone) {
                setZoneInfo(data.zone);
                if (data.zoning_options) {
                    setZoningOptions(data.zoning_options);
                }
                if (data.target_ym) {
                    setTargetYm(data.target_ym);
                }
                if (data.sliders) {
                    //비례율은 슬라이더가 아니다. 백엔드가 아예 내려주지 않고 사업 수지로 계산한다
                    //세대수 자료가 없으면 백엔드가 조합원 수 슬라이더를 만들지 않으므로 임시값을 채운다
                    setSliderData({
                        ...data.sliders,
                        member_count: data.sliders.member_count ?? MEMBER_COUNT_FALLBACK,
                    });
                }
                setZoneCalculated(true);
            } else {
                setInitialCalculationPending(false);
            }
        } catch (err) {
            setError("구역 정보를 불러오는 중 오류가 발생했습니다.");
            setInitialCalculationPending(false);
        } finally {
            setLoading(false);
        }
    }, [selectedPnus, selectedZoning]);

    //필지 선택이 바뀌면 이전 결과를 무효로 돌린다.
    //  자동으로 다시 계산하지는 않는다 — 구역 선택 → 용도지역 선택 → 계산 버튼 순서이고,
    //  필지를 여러 개 고르는 동안 매번 서버를 부르면 느리고 중간 결과가 혼란을 준다
    useEffect(() => {
        setZoneCalculated(false);
        if (selectedPnus.length === 0) {
            setZoneInfo(null);
            setCalcResult(null);
            setMemberRange(null);
            setError(null);
        }
    }, [selectedPnus]);

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
                setInitialCalculationPending(false);
            }
        } catch (err) {
            setError("분담금 계산 중 오류가 발생했습니다.");
            setInitialCalculationPending(false);
        } finally {
            setLoading(false);
        }
    //슬라이더 값을 개별로 나열한다 (sliderData 통째로 넣으면 객체 참조가 매번 바뀌어 깜빡인다).
    //  ※ 슬라이더를 추가·삭제하면 이 목록도 같이 고쳐야 한다.
    //    추가한 키가 빠지면 그 슬라이더를 움직여도 다시 계산되지 않는다.
    //  ※ 반드시 옵셔널(?.)로 읽는다.
    //    sliderData 는 zone 응답으로 통째로 교체되므로, 백엔드가 아직 배포되지 않아
    //    새 슬라이더를 안 내려주면 키가 사라진다. 그때 .value 를 직접 읽으면
    //    렌더가 통째로 죽어 화면이 하얘진다 (실제로 겪었다 — 프론트만 먼저 배포된 상황)
    }, [
        zoneInfo,
        sliderData.floor_area_ratio?.value,
        sliderData.member_count?.value,
        sliderData.member_price_ratio?.value,
        sliderData.other_cost_ratio?.value,
        sliderData.commercial_ratio?.value,
        sliderData.construction_cost_per_pyeong?.value,
        sliderData.general_price_per_m2?.value,
        sliderData.parking_per_household?.value,
        sliderData.rental_floor_band?.value,
        sliderData.project_period_years?.value,
        ownerData.desired_unit,
        formData.name,
        formData.member_count,
    ]);

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
        loading: loading || initialCalculationPending,
        error,
        handleChange,
        selectedZoning,
        zoningOptions,
        handleSelectZoning,
        handleSliderChange,
        handleSelectUnit,
        handleZoneData,
        handleSubmit,
        zoneCalculated,
    };
}

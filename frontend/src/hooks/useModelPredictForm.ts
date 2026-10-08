import { useCallback, useEffect, useRef, useState } from 'react';
import { SliderValue, SlidersState } from '../hooks/useSlider';
import { getProjectTypePreview } from '../api/realestate_api';
import { ParcelInfo } from '../utils/parcel';
import { OrganizationMapView, OrganizationScenario } from '../api/organization_api';
import {
    BusinessCorrection, ContributionMix, ContributionResult, CONTRIBUTION_PRESETS, MemberCountRange, MAX_UNIT_TYPES, ReconstructionInfo, UnitMixEntry,
    UpzoningInfo, ZoneInfo, ZonePriorAsset,
} from './useContribution';

//슬라이더를 움직인 뒤 다시 계산하기까지 기다리는 시간
const RECALC_DEBOUNCE_MS = 250;

//필지 선택이 멈춘 뒤 사업 유형 미리 판정을 부르기까지 기다리는 시간 (필지를 연달아 고르는 동안 매번 부르지 않게)
const PREVIEW_DEBOUNCE_MS = 600;

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

//종상향 판정용 용도지역 사다리 (아래 → 위). AI/engine/zone.py ZONING_LADDER 와 같아야 한다
const ZONING_LADDER = [
    '제1종전용주거지역',
    '제2종전용주거지역',
    '제1종일반주거지역',
    '제2종일반주거지역',
    '제3종일반주거지역',
    '준주거지역',
];

//용도지역 선택 즉시 보여주는 종상향 미리보기.
//  기준 용도지역(필지 원래 용도지역의 면적가중 평균)은 첫 구역 분석 뒤에야 알 수 있다
export interface UpzoningPreview {
    baseZoning: string;
    selectedZoning: string;
    steps: number;      //0 이하면 종상향 아님
}

//예측 폼 Hook Props
export interface ModelPredictFormProps {
    onHandleZoneData: (pnus: string[], zoning?: string, parcels?: ParcelInfo[], targetYm?: string, householdCount?: number) => Promise<any>;
    onCalculateContribution: (requestData: any) => Promise<any>;
    selectedPnus: string[];
    selectedParcels: ParcelInfo[];
    onRestoreSelection: (pnus: string[], parcels: ParcelInfo[], mapView: OrganizationMapView) => void;
    mapView: OrganizationMapView | null;
}

//예측 폼 Hook 
export function useModelPredictForm({
    onHandleZoneData,
    onCalculateContribution,
    selectedPnus,
    selectedParcels,
    onRestoreSelection,
    mapView,
}: ModelPredictFormProps) {
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

    //평형 구성 (세부 설정).
    //  null 이면 서버가 실측 기본값(UNIT_MIX : 59·84·114)을 쓴다.
    //  사용자가 한 번이라도 손대면 그 값을 보내기 시작한다 — 기본 상태에서 세대수 비율로
    //  환산한 값을 되돌려 보내면 반올림 때문에 기본 결과와 미세하게 달라져서다
    const [unitMix, setUnitMix] = useState<UnitMixEntry[] | null>(null);

    //임대 1세대 전용면적(㎡). null 이면 서버 기본값(39㎡)
    //  임대 비율은 입력받지 않는다 — 용적률 완화분에서 법정으로 정해진다 (도시정비법 제54조)
    const [rentalExclusive, setRentalExclusive] = useState<number | null>(null);

    //내 필지 지정. 비우면 구역 종전자산의 1인분(ρ=1)으로 계산된다 — 구역 평균 조합원
    const [ownerPnu, setOwnerPnu] = useState<string>('');

    //집합건물에서 내 전유면적(㎡). 없으면 세대수로 균등 분할한다
    const [ownerExclusive, setOwnerExclusive] = useState<number | null>(null);

    //구역 종전자산 집계 (/zone 의 prior_asset). 필지 원자료를 /contribution 에 돌려보낸다
    const [priorAsset, setPriorAsset] = useState<ZonePriorAsset | null>(null);

    //평형·비율·임대 평형은 입력 중간 상태가 그대로 계산에 들어가면 안 되므로
    //  「적용」을 눌러야 반영한다 (슬라이더는 실시간, 크레딧은 어느 쪽도 추가로 안 든다).
    //  applied* 가 실제 계산에 쓰이는 값이고, unitMix/rentalExclusive 는 입력 중인 값이다
    const [appliedUnitMix, setAppliedUnitMix] = useState<UnitMixEntry[] | null>(null);
    const [appliedRentalExclusive, setAppliedRentalExclusive] = useState<number | null>(null);

    //공공기여 기부면적 비율 (세부 설정, %) : 토지 / 공공임대 건축물 / 현금. 버튼은 비율 프리셋이다.
    //  평형 구성처럼 입력만 해서는 계산하지 않고 「적용」을 눌러야 반영한다.
    //  contributionMix 가 입력 중인 값, appliedContributionMix 가 계산에 쓰는 값이다 (기본 토지 100%)
    const [contributionMix, setContributionMix] = useState<ContributionMix>(CONTRIBUTION_PRESETS[0].mix);
    const [appliedContributionMix, setAppliedContributionMix] = useState<ContributionMix>(CONTRIBUTION_PRESETS[0].mix);

    //구역 분석 완료 여부
    const [zoneCalculated, setZoneCalculated] = useState<boolean>(false);

    //용도지역이 바뀌었는데 아직 다시 분석하지 않은 상태.
    //  이 동안 화면의 결과는 이전 용도지역 기준이라 그대로 믿으면 안 된다.
    //  /zone 재호출은 크레딧 1개를 더 쓰므로 자동으로 부르지 않고 버튼을 기다린다
    const [zoningStale, setZoningStale] = useState<boolean>(false);

    //슬라이더 변수 상태
    const [sliderData, setSliderData] = useState<SlidersState>({
        floor_area_ratio: { value: 200, min: 200, max: 250 },
        member_count: MEMBER_COUNT_FALLBACK,
        //조합원 분양가 비율 : 자동(관리처분 비례율 100% 역산). 값은 /contribution 응답으로 채워진다 (zone 응답으로 교체된다)
        member_price_ratio: { value: null, min: 0, max: 1, auto: true },
        //기타사업비 비율 : 관리처분 단계 중앙값 (재개발 0.707 · 재건축 0.474), 범위 0.19~0.75 (서버 engine_defaults 와 같은 값, zone 응답으로 교체된다)
        other_cost_ratio: { value: 0.707, min: 0.19, max: 0.75 },
        //주차 여유율 = 실제 ÷ 법정 주차대수 (법정 대수는 서버가 평형 구성에서 계산한다)
        parking_margin: { value: 1.29, min: 1.0, max: 1.59 },
        //상한은 용도지역별로 다르다 (전용 0.03 / 1종 0.05 / 2·3종 0.10 / 준주거 0.30).
        //  서버가 zone 응답에서 대표 용도지역에 맞는 max 를 내려주므로 여기 값은 그때 교체된다
        commercial_ratio: { value: 0.02, min: 0.0, max: 0.1 },
        construction_cost_per_pyeong: { value: 850, min: 700, max: 1000 },
        general_price_per_m2: { value: 998.25, min: 700, max: 1300 },
        //임대동 층수 : 기본형건축비 고시 표의 아홉 구간. 서버 rental_cost.FLOOR_BANDS 와 같은 값 (zone 응답으로 교체된다)
        rental_floor_band: {
            value: '16~25층',
            options: ['5층 이하', '6~10층', '11~15층', '16~25층', '26~30층', '31~35층', '36~40층', '41~45층', '46~49층'],
        },
        //사업 기간 : [분담금 고시일, 최종 인가]. 서버 slider_builder 와 같은 기본값 (zone 응답으로 교체된다)
        project_period_years: {
            value: [13, 21], min: 10, max: 30, step: 1, range: true,
            ticks: [11, 13, 16, 18], gap: { value: 8, min: 3, max: 20 },
            labels: ['분담금 고시일', '최종 인가'],
        },
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

    //제54조 임대 의무의 기준점 (/zone 의 far_base) = 정비계획 상한용적률 (보정계수 반영)
    const [farBase, setFarBase] = useState<number | null>(null);

    //종상향 판정과 사업성 보정계수 (/zone 응답). 공공기여율은 /contribution 에 그대로 돌려보낸다
    const [upzoning, setUpzoning] = useState<UpzoningInfo | null>(null);
    const [businessCorrection, setBusinessCorrection] = useState<BusinessCorrection | null>(null);

    //사업 유형 판정 (/zone) : 아파트 단지(들)만 고르면 재건축, 아파트 외 사유 필지가 섞이면 재개발.
    //  선택한 필지 칸의 개수 옆에 띄우고, 재건축 단지 정보는 /contribution 에 그대로 돌려보낸다
    const [projectType, setProjectType] = useState<string | null>(null);
    const [projectTypeReason, setProjectTypeReason] = useState<string>('');

    //사업 유형 미리 판정 (필지를 고르는 즉시, 분석 전). 분석하면 projectType(최종)이 이 값을 대신한다
    const [previewType, setPreviewType] = useState<string | null>(null);
    const [previewTypeReason, setPreviewTypeReason] = useState<string>('');

    //필지 선택이 바뀌면 잠깐 기다렸다가 판정만 받아 온다 (크레딧 없음, 서버 캐시).
    //  미리보기라 실패해도 분석 흐름에는 영향이 없다 — 배지만 안 뜬다
    useEffect(() => {
        setPreviewType(null);
        setPreviewTypeReason('');
        if (selectedPnus.length === 0) return;
        let cancelled = false;
        const timer = setTimeout(async () => {
            try {
                const data = await getProjectTypePreview(selectedPnus);
                if (!cancelled) {
                    setPreviewType(data.project_type ?? null);
                    setPreviewTypeReason(data.project_type_reason ?? '');
                }
            } catch {
                //배지만 띄우지 않는다
            }
        }, PREVIEW_DEBOUNCE_MS);
        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [selectedPnus]);
    const [reconstruction, setReconstruction] = useState<ReconstructionInfo | null>(null);
    const [creditToken, setCreditToken] = useState<string | null>(null);
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
        //이미 결과가 있는 상태에서 용도지역을 바꾸면, 화면의 숫자는 이전 용도지역 기준이다.
        //  결과를 지우지 않고 "낡음" 으로 표시한다 — 지워버리면 비교할 대상이 사라진다
        if (calcResult) {
            setZoningStale(true);
        }
        setSelectedZoning(zoning);
        setZoneCalculated(false);
    };

    //슬라이더 값 변경 Handler
    //  노드 슬라이더(임대동 층수)는 문자열, 범위 슬라이더(사업 기간)는 [고시일, 최종 인가] 라 number 로 좁히면 안 된다
    const handleSliderChange = (key: string, newValue: SliderValue) => {
        setSliderData((prev: any) => ({
            ...prev,
            [key]: {
                ...prev[key],
                value: newValue,
                //자동 슬라이더(조합원 분양가 비율)는 손잡이를 움직이는 순간 사용자 값이 된다
                ...(prev[key]?.auto !== undefined ? { auto: false } : {}),
            },
        }));
    };

    //자동 슬라이더를 다시 자동으로 돌린다 (조합원 분양가 비율 : 관리처분 비례율 100% 역산)
    const handleSliderAuto = (key: string) => {
        setSliderData((prev: any) => (prev[key] ? { ...prev, [key]: { ...prev[key], auto: true } } : prev));
    };

    //희망 평형 선택 Handler (패널의 평형 버튼)
    const handleSelectUnit = (name: string) => {
        setOwnerData((prev) => ({ ...prev, desired_unit: name }));
    };

    //평형 구성 Handler (세부 설정) — 입력만 받는다. 계산은 「적용」을 눌러야 한다
    //  빈 칸을 지우는 중간 상태를 허용해야 한다 (30 → 3 → 35 로 고치는 중에 3 으로 계산되면 안 된다)
    const handleUnitMixChange = (rows: UnitMixEntry[]) => {
        setUnitMix(rows.slice(0, MAX_UNIT_TYPES));
    };

    //임대 평형 Handler. 0·빈 칸이면 서버 기본값으로 되돌린다
    const handleRentalExclusiveChange = (value: number | null) => {
        setRentalExclusive(value && value > 0 ? value : null);
    };

    //평형 구성 「적용」 — 여기서만 계산에 반영된다
    const handleApplyUnitMix = () => {
        setAppliedUnitMix(unitMix);
        setAppliedRentalExclusive(rentalExclusive);
    };

    //공공기여 비율 Handler (프리셋 버튼·% 입력) — 입력만 받는다. 계산은 「적용」을 눌러야 한다
    const handleContributionMixChange = (mix: ContributionMix) => {
        setContributionMix(mix);
    };

    //공공기여 비율 「적용」
    const handleApplyContributionMix = () => {
        setAppliedContributionMix(contributionMix);
    };

    const contributionMixDirty = JSON.stringify(contributionMix) !== JSON.stringify(appliedContributionMix);

    //입력값이 적용값과 다른가 (「적용」 버튼을 활성화할지 판단)
    const unitMixDirty =
        JSON.stringify(unitMix) !== JSON.stringify(appliedUnitMix)
        || rentalExclusive !== appliedRentalExclusive;

    //내 필지 지정 Handler. 필지를 바꾸면 전유면적 입력은 의미가 없어져 비운다
    const handleSelectOwnerPnu = (pnu: string) => {
        setOwnerPnu(pnu);
        setOwnerExclusive(null);
    };

    const handleOwnerExclusiveChange = (value: number | null) => {
        setOwnerExclusive(value && value > 0 ? value : null);
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
                setCreditToken(data.credit_token);
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
                //구역 종전자산 집계. parcels 를 /contribution 에 돌려보내 평가시점으로 재집계한다
                if (data.prior_asset) {
                    setPriorAsset(data.prior_asset);
                }
                //제54조 임대 의무의 기준점은 서버가 계산해 내려준다 (정비계획 상한용적률, 보정계수 반영).
                //  zone.far_min 은 조례용적률이라 2종일반(조례 200 < 상한 250)에서 임대 의무가 과대해진다
                if (typeof data.far_base === 'number') {
                    setFarBase(data.far_base);
                }
                //종상향 : 고른 용도지역이 기준(필지 원래 용도지역의 평균 단계)보다 높으면 공공기여율이 붙는다
                setUpzoning(data.upzoning ?? null);
                setBusinessCorrection(data.business_correction ?? null);
                setProjectType(data.project_type ?? null);
                setProjectTypeReason(data.project_type_reason ?? '');
                setReconstruction(data.reconstruction ?? null);
                setZoningStale(false);
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

    const createSharedScenario = useCallback((): OrganizationScenario | null => {
        if (
            !zoneCalculated
            || !selectedZoning
            || selectedPnus.length === 0
            || selectedParcels.length !== selectedPnus.length
            || !mapView
        ) {
            return null;
        }

        const unitMix = appliedUnitMix?.filter(
            (row) => row.exclusive_area_m2 > 0 && row.household_ratio > 0
        );

        return {
            pnus: selectedPnus,
            parcels: selectedParcels,
            map_view: mapView,
            zoning: selectedZoning,
            target_ym: targetYm,
            //조합원분양가 비율 자동(null)은 저장하지 않는다 — 불러올 때 기본값(자동)으로 남는다
            sliders: Object.fromEntries(
                Object.entries(sliderData)
                    .filter(([, config]) => config.value !== null && config.value !== undefined)
                    .map(([key, config]) => [key, config.value as SliderValue])
            ),
            unit_mix: unitMix?.length ? unitMix : null,
            rental_exclusive_area_m2: appliedRentalExclusive,
        };
    }, [
        zoneCalculated,
        selectedZoning,
        selectedPnus,
        selectedParcels,
        mapView,
        targetYm,
        sliderData,
        appliedUnitMix,
        appliedRentalExclusive,
    ]);

    const loadSharedScenario = useCallback(async (scenario: OrganizationScenario) => {
        onRestoreSelection(scenario.pnus, scenario.parcels, scenario.map_view);
        setLoading(true);
        setInitialCalculationPending(true);
        setError(null);
        setZoneCalculated(false);
        setCalcResult(null);
        setZoneInfo(null);
        setCreditToken(null);

        try {
            const data = await zoneApiRef.current(
                scenario.pnus,
                scenario.zoning,
                scenario.parcels,
                scenario.target_ym,
                Number(scenario.sliders.member_count ?? MEMBER_COUNT_FALLBACK.value),
            );
            if (!data?.zone) {
                throw new Error('공유 기준안의 구역 정보를 불러오지 못했습니다.');
            }

            const nextSliders: SlidersState = {
                ...(data.sliders ?? {}),
                member_count: data.sliders?.member_count ?? MEMBER_COUNT_FALLBACK,
            };
            Object.entries(scenario.sliders).forEach(([key, value]) => {
                if (nextSliders[key]) {
                    nextSliders[key] = { ...nextSliders[key], value };
                }
            });
            if (!data.sliders?.member_count && scenario.sliders.member_count !== undefined) {
                nextSliders.member_count = {
                    ...MEMBER_COUNT_FALLBACK,
                    value: Number(scenario.sliders.member_count),
                };
            }

            setSelectedZoning(scenario.zoning);
            setZoneInfo(data.zone);
            setCreditToken(data.credit_token);
            setZoningOptions(data.zoning_options ?? DEFAULT_ZONING_OPTIONS);
            setTargetYm(data.target_ym ?? scenario.target_ym);
            setSliderData(nextSliders);
            setPriorAsset(data.prior_asset ?? null);
            setFarBase(typeof data.far_base === 'number' ? data.far_base : data.zone.far_min);
            setUnitMix(scenario.unit_mix);
            setAppliedUnitMix(scenario.unit_mix);
            setRentalExclusive(scenario.rental_exclusive_area_m2);
            setAppliedRentalExclusive(scenario.rental_exclusive_area_m2);
            setOwnerPnu((current) => scenario.pnus.includes(current) ? current : '');
            setOwnerExclusive(null);
            setZoningStale(false);
            setZoneCalculated(true);
        } catch (loadError) {
            setError(loadError instanceof Error ? loadError.message : '조합 기준안을 불러오는 중 오류가 발생했습니다.');
            setInitialCalculationPending(false);
            throw loadError;
        } finally {
            setLoading(false);
        }
    }, [onRestoreSelection]);

    //필지 선택이 바뀌면 이전 결과를 무효로 돌린다.
    //  자동으로 다시 계산하지는 않는다 — 구역 선택 → 용도지역 선택 → 계산 버튼 순서이고,
    //  필지를 여러 개 고르는 동안 매번 서버를 부르면 느리고 중간 결과가 혼란을 준다
    useEffect(() => {
        setZoneCalculated(false);
        setCreditToken(null);
        setZoningStale(false);
        //판정은 고른 필지 전체로 하므로 선택이 바뀌면 지운다 (다시 분석하면 새로 판정된다)
        setProjectType(null);
        setProjectTypeReason('');
        setReconstruction(null);
        if (selectedPnus.length === 0) {
            setZoneInfo(null);
            setCalcResult(null);
            setMemberRange(null);
            setPriorAsset(null);
            setFarBase(null);
            setUpzoning(null);
            setBusinessCorrection(null);
            setOwnerPnu('');
            setOwnerExclusive(null);
            setError(null);
        }
    }, [selectedPnus]);

    //조합원 분양가 비율의 "보내는 값". 자동이면 서버가 정하므로 손잡이 위치(응답으로 채운 값)는 재계산 대상이 아니다
    const memberPriceInput = sliderData.member_price_ratio?.auto ? 'auto' : sliderData.member_price_ratio?.value;

    //Contribution 호출 (슬라이더가 바뀔 때마다 자동으로 다시 계산된다)
    const calculate = useCallback(async () => {
        if (!zoneInfo || !creditToken) return;

        setLoading(true);
        setError(null);

        try {
            //슬라이더 객체에서 value만 뽑아서 1차원 딕셔너리로 변환.
            //  자동 슬라이더는 null 로 보낸다 → 서버가 정한다 (조합원 분양가 비율 : 관리처분 비례율 100% 역산)
            const formattedSliders = Object.fromEntries(
                Object.entries(sliderData).map(([key, config]: [any, any]) => [key, config.auto ? null : config.value])
            );

            //조합원 수는 ProjectParams 슬라이더가 아니라 별도 필드로 넘긴다
            const { member_count, ...engineSliders } = formattedSliders;
            const sentMemberCount = Number(member_count ?? formData.member_count);

            //고른 용적률 노드의 토지 공공기여 비율 (서버가 노드마다 계산해 내려준다).
            //  예전 응답(노드별 값이 없음)이면 종상향 최소 비율만 쓴다
            const far = sliderData.floor_area_ratio;
            const farIndex = far?.options ? far.options.indexOf(far.value as number) : -1;
            const farContribution = farIndex >= 0 ? far?.contributions?.[farIndex] : undefined;

            const requestPayload = {
                credit_token: creditToken,
                name: formData.name,
                site_area_m2: zoneInfo.site_area_m2,
                member_count: sentMemberCount,
                sliders: engineSliders,
                far_base: farBase ?? zoneInfo.far_min,
                //토지 공공기여율 (원래 대지 대비). 토지 방식이면 서버가 이만큼 건축 대지를 줄인다.
                //  다른 방식이면 서버가 이 값에서 노드 용적률에 필요한 기여량을 되돌려 구해 방식대로 채운다
                public_contribution_ratio: farContribution ?? upzoning?.contribution_ratio ?? 0,
                //공공기여 기부면적 비율 (「적용」을 누른 값)과 종상향 최소 공공기여 (순부담 하한)
                contribution_mix: appliedContributionMix,
                min_contribution_ratio: far?.min_contribution ?? 0,
                land_value_total: zoneInfo.land_value_total,
                //사업 유형과 재건축 단지 정보 (/zone 판정 그대로). 재건축이면 의무 임대 0 · 종전자산 = 공동주택가격 기준
                ...(projectType ? { project_type: projectType } : {}),
                ...(reconstruction ? { reconstruction } : {}),
                //「적용」을 누른 값만 보낸다. 손대지 않았으면 아예 안 보내고 서버 실측 기본값을 쓴다
                //  비율이 0 인 줄과 면적이 비어 있는 줄은 입력 중인 상태라 빼고 보낸다
                ...(appliedUnitMix
                    ? {
                        unit_mix: appliedUnitMix.filter(
                            (row) => row.exclusive_area_m2 > 0 && row.household_ratio > 0
                        ),
                    }
                    : {}),
                ...(appliedRentalExclusive ? { rental_exclusive_area_m2: appliedRentalExclusive } : {}),
                //필지 원자료를 그대로 돌려보낸다 → 서버가 평가시점(사업시행인가) 기준으로
                //  종전자산을 토지분+건물분 재집계한다. 이게 없으면 건물분이 빠져 약분된다
                ...(priorAsset?.parcels?.length ? { parcel_valuations: priorAsset.parcels } : {}),
                owner: {
                    desired_unit: ownerData.desired_unit,
                    //내 필지를 지정하면 그 필지 기준으로 개인화된다. 비우면 구역 1인분(ρ=1)
                    ...(ownerPnu ? { pnu: ownerPnu } : {}),
                    ...(ownerExclusive ? { exclusive_area_m2: ownerExclusive } : {}),
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

                //자동이면 서버가 역산한 비율을 손잡이 위치로 보여준다.
                //  자동일 때는 값이 재계산 의존성(memberPriceInput)에 없으므로 여기서 바꿔도 다시 계산되지 않는다
                const solved = data?.timeline?.member_price_ratio;
                if (data?.timeline?.member_price_mode === 'auto' && typeof solved === 'number') {
                    setSliderData((prev) => {
                        const current = prev.member_price_ratio;
                        if (!current?.auto || current.value === solved) return prev;
                        return { ...prev, member_price_ratio: { ...current, value: solved } };
                    });
                }
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
        creditToken,
        sliderData.floor_area_ratio?.value,
        sliderData.floor_area_ratio?.contributions,
        sliderData.floor_area_ratio?.min_contribution,
        sliderData.member_count?.value,
        memberPriceInput,
        sliderData.other_cost_ratio?.value,
        sliderData.commercial_ratio?.value,
        sliderData.construction_cost_per_pyeong?.value,
        sliderData.general_price_per_m2?.value,
        sliderData.parking_margin?.value,
        sliderData.rental_floor_band?.value,
        sliderData.project_period_years?.value,
        ownerData.desired_unit,
        appliedUnitMix,
        appliedRentalExclusive,
        appliedContributionMix,
        priorAsset,
        farBase,
        upzoning,
        projectType,
        reconstruction,
        ownerPnu,
        ownerExclusive,
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
            const value = Math.min(Math.max(Number(current?.value ?? range.min), range.min), range.max);

            //같은 범위면 상태를 그대로 둔다 (재계산 반복 방지)
            if (current && current.min === range.min && current.max === range.max && current.value === value) {
                return prev;
            }
            return { ...prev, member_count: { value, min: range.min, max: range.max } };
        });
    }, [memberRange]);

    //종상향 미리보기 : 용도지역을 고르는 즉시 기준 대비 몇 단계 올렸는지 보여준다.
    //  실제 계산(공공기여로 대지 축소)은 계산 버튼으로 구역을 다시 분석한 뒤 반영된다
    const baseZoning = upzoning?.base_zoning ?? null;
    const upzoningPreview: UpzoningPreview | null =
        baseZoning && selectedZoning && ZONING_LADDER.includes(selectedZoning) && ZONING_LADDER.includes(baseZoning)
            ? {
                baseZoning,
                selectedZoning,
                steps: ZONING_LADDER.indexOf(selectedZoning) - ZONING_LADDER.indexOf(baseZoning),
            }
            : null;

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
        handleSliderAuto,
        handleSelectUnit,
        unitMix,
        handleUnitMixChange,
        rentalExclusive,
        handleRentalExclusiveChange,
        handleApplyUnitMix,
        unitMixDirty,
        contributionMix,
        handleContributionMixChange,
        handleApplyContributionMix,
        contributionMixDirty,
        priorAsset,
        ownerPnu,
        handleSelectOwnerPnu,
        ownerExclusive,
        handleOwnerExclusiveChange,
        zoningStale,
        upzoning,
        upzoningPreview,
        businessCorrection,
        projectType,
        projectTypeReason,
        previewType,
        previewTypeReason,
        handleZoneData,
        handleSubmit,
        zoneCalculated,
        createSharedScenario,
        loadSharedScenario,
    };
}

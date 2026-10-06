import React from 'react';
import ContributionPanel from './ContributionPanel';
import { buildMetrics } from '../hooks/useContribution';
import { useModelPredictForm } from '../hooks/useModelPredictForm';

//예측 폼 Props
interface ModelPredictFormProps {
    onHandleZoneData: (pnus: string[], zoning?: string) => Promise<any>;
    onCalculateContribution: (requestData: any) => Promise<any>;
    selectedPnus: string[];
    isOpen: boolean;
    dailyCredits: number | null;
    creditsUnavailable: boolean;
}

//예측 폼 컴포넌트
const ModelPredictForm: React.FC<ModelPredictFormProps> = ({ 
    onHandleZoneData, 
    onCalculateContribution,
    selectedPnus,
    isOpen,
    dailyCredits,
    creditsUnavailable,
}) => {
    const {
        formData,
        sliderData,
        zoneInfo,
        targetYm,
        calcResult,
        loading,
        error,
        selectedZoning,
        zoningOptions,
        handleSelectZoning,
        handleSliderChange,
        unitMix,
        handleUnitMixChange,
        rentalExclusive,
        handleRentalExclusiveChange,
        handleApplyUnitMix,
        unitMixDirty,
        priorAsset,
        ownerPnu,
        handleSelectOwnerPnu,
        ownerExclusive,
        handleOwnerExclusiveChange,
        zoningStale,
        handleZoneData,
    } = useModelPredictForm({ onHandleZoneData, onCalculateContribution, selectedPnus });

    //계산 버튼을 누를 수 있는 조건 : 필지를 골랐고, 용도지역을 정했을 때
    //  용도지역이 용적률 범위를 정하므로 이것 없이 계산하면 가정값으로 돌아간다
    const canCalculate = selectedPnus.length > 0
        && !!selectedZoning
        && !loading
        && !creditsUnavailable
        && dailyCredits !== null
        && dailyCredits > 0;

    //조합원 수는 슬라이더 값을 쓰고, 아직 없으면 폼 기본값을 쓴다
    const memberCount = Number(sliderData.member_count?.value ?? formData.member_count);
    const metrics = buildMetrics(zoneInfo, calcResult, sliderData, memberCount);

    return (
        <div className={`h-full w-full bg-slate-50/50 flex flex-col items-center p-6 font-sans overflow-y-auto transition-opacity ${isOpen ? 'opacity-100 duration-500' : 'opacity-0 pointer-events-none duration-100'}`}>
            <div className="max-w-md w-full flex flex-col items-center gap-4">

                {/* 1단계 : 선택한 필지 */}
                <div className="w-full flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5">
                    <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10.5px] font-semibold text-slate-500">1</span>
                    <span className="text-[12.5px] text-slate-500">선택한 필지</span>
                    <span className="ml-auto text-[12.5px] font-semibold text-slate-900">{selectedPnus.length}개</span>
                </div>

                {/* 2단계 : 용도지역 선택
                    용적률 범위를 정하는 값이라 계산 전에 반드시 골라야 한다.
                    정비사업은 정비계획에서 용도지역을 새로 정하므로 현황 조회값을 그대로 쓰지 않는다.
                    재개발은 사실상 주거지역에서만 일어나므로 서버가 주거지역만 내려준다 */}
                <div className="w-full bg-white rounded-xl border border-slate-200 p-4">
                    <div className="mb-2 flex items-center gap-2">
                        <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10.5px] font-semibold text-slate-500">2</span>
                        <label className="text-xs font-bold tracking-wider text-slate-700">용도지역</label>
                        {!selectedZoning && (
                            <span className="text-[11px] text-amber-600">계산하려면 선택하세요</span>
                        )}
                    </div>

                    <div className="grid grid-cols-2 gap-1.5">
                        {zoningOptions.map((z) => (
                            <button
                                key={z}
                                type="button"
                                onClick={() => handleSelectZoning(z)}
                                className={`rounded-lg border px-2 py-1.5 text-[11.5px] transition ${
                                    selectedZoning === z
                                        ? 'border-blue-600 bg-blue-50 font-semibold text-blue-700'
                                        : 'border-slate-200 text-slate-600 hover:border-slate-300'
                                }`}
                            >
                                {z.replace('지역', '')}
                            </button>
                        ))}
                    </div>
                </div>

                {/* 3단계 : 계산 버튼
                    슬라이더를 움직일 때는 자동으로 다시 계산되지만,
                    필지·용도지역을 바꾼 뒤에는 이 버튼을 눌러야 반영된다 */}
                <button
                    type="button"
                    onClick={handleZoneData}
                    disabled={!canCalculate}
                    className="w-full rounded-xl bg-emerald-600 px-3 py-3 text-[13px] font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                    {loading
                        ? '계산 중...'
                        : creditsUnavailable
                            ? '크레딧 정보를 불러올 수 없습니다'
                        : dailyCredits === null
                            ? '크레딧 확인 중...'
                        : dailyCredits <= 0
                            ? '오늘의 크레딧을 모두 사용했습니다'
                        : selectedPnus.length === 0
                            ? '지도에서 필지를 선택하세요'
                            : !selectedZoning
                                ? '용도지역을 선택하세요'
                                : `분담금 계산 · 크레딧 ${dailyCredits}개`}
                </button>

                {/* 예상 분담금 패널 : 필지 선택 전에는 0, 선택하면 그 필지만큼 계산된다 */}
                <ContributionPanel
                    result={calcResult}
                    metrics={metrics}
                    sliders={sliderData}
                    onSliderChange={handleSliderChange}
                    unitMix={unitMix}
                    onUnitMixChange={handleUnitMixChange}
                    rentalExclusive={rentalExclusive}
                    onRentalExclusiveChange={handleRentalExclusiveChange}
                    onApplyUnitMix={handleApplyUnitMix}
                    unitMixDirty={unitMixDirty}
                    priorAsset={priorAsset}
                    ownerPnu={ownerPnu}
                    onSelectOwnerPnu={handleSelectOwnerPnu}
                    ownerExclusive={ownerExclusive}
                    onOwnerExclusiveChange={handleOwnerExclusiveChange}
                    zoningStale={zoningStale}
                    targetYm={targetYm}
                    loading={loading}
                />

                {error && (
                    <div className="w-full p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs break-all">
                        {error}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ModelPredictForm;

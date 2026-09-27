import React from 'react';
import ContributionPanel from './ContributionPanel';
import { buildMetrics } from '../hooks/useContribution';
import { useModelPredictForm } from '../hooks/useModelPredictForm';

//예측 폼 Props
interface ModelPredictFormProps {
    onHandleZoneData: (pnus: string[]) => Promise<any>;
    onCalculateContribution: (requestData: any) => Promise<any>;
    selectedPnus: string[];
    isOpen: boolean;
}

//예측 폼 컴포넌트
const ModelPredictForm: React.FC<ModelPredictFormProps> = ({ 
    onHandleZoneData, 
    onCalculateContribution,
    selectedPnus,
    isOpen 
}) => {
    const {
        formData,
        setFormData,
        ownerData,
        sliderData,
        zoneInfo,
        targetYm,
        calcResult,
        loading,
        error,
        handleSliderChange,
        handleSelectUnit,
        handleZoneData,
    } = useModelPredictForm({ onHandleZoneData, onCalculateContribution, selectedPnus });

    //조합원 수는 슬라이더 값을 쓰고, 아직 없으면 폼 기본값을 쓴다
    const memberCount = sliderData.member_count?.value ?? formData.member_count;
    const metrics = buildMetrics(zoneInfo, calcResult, sliderData, memberCount);

    return (
        <div className={`h-full w-full bg-slate-50/50 flex flex-col items-center p-6 font-sans overflow-y-auto transition-opacity ${isOpen ? 'opacity-100 duration-500' : 'opacity-0 pointer-events-none duration-100'}`}>
            <div className="max-w-md w-full flex flex-col items-center gap-4">

                {/* 선택 상태 : 필지를 고르면 자동으로 분석된다. 버튼은 다시 불러올 때만 쓴다 */}
                <div className="w-full flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5">
                    <span className="text-[12.5px] text-slate-500">선택한 필지</span>
                    <span className="text-[12.5px] font-semibold text-slate-900">{selectedPnus.length}개</span>
                    <button
                        type="button"
                        onClick={handleZoneData}
                        disabled={loading || selectedPnus.length === 0}
                        className="ml-auto rounded-lg bg-emerald-600 px-3 py-1.5 text-[12px] font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-40"
                    >
                        {loading ? '분석 중...' : '다시 분석'}
                    </button>
                </div>

                {/* 구역 이름만 직접 입력. 평형과 조합원 수는 아래 패널에서 조절한다 */}
                {/* 공시가격은 선택 필지의 개별공시지가에서 자동으로 계산된다 */}
                <div className="w-full bg-white rounded-xl border border-slate-200 p-4">
                    <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">구역 이름</label>
                    <input
                        type="text"
                        name="name"
                        value={formData.name}
                        onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                        className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white text-slate-800 text-sm transition"
                    />
                </div>

                {/* 예상 분담금 패널 : 필지 선택 전에는 0, 선택하면 그 필지만큼 계산된다 */}
                <ContributionPanel
                    result={calcResult}
                    metrics={metrics}
                    sliders={sliderData}
                    onSliderChange={handleSliderChange}
                    selectedUnit={ownerData.desired_unit}
                    onSelectUnit={handleSelectUnit}
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

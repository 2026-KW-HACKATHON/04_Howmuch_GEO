import React from 'react';
import Slider from './Slider';
import { useModelPredictForm } from '../hooks/useModelPredictForm';

//예측 폼 Props
interface ModelPredictFormProps {
    onHandleZoneData: (pnus: string[]) => Promise<any>;
    onCalculateContribution: (requestData: any) => Promise<any>;
    selectedPnus: string[];
    isOpen: boolean;
}

//예측 폼 컨포넌트
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
        zoneCalculated
    } = useModelPredictForm({ onHandleZoneData, onCalculateContribution, selectedPnus });

    return (
        <div className={`h-full w-full bg-slate-700 flex flex-col items-center p-6 font-sans overflow-y-auto transition-opacity ${isOpen ? 'opacity-100 duration-500' : 'opacity-0 pointer-events-none duration-100'}`}>
            <div className="max-w-md w-full bg-slate-600 rounded-2xl shadow-lg border border-slate-500 p-8 flex flex-col items-center">
                <h1 className="text-2xl font-bold text-slate-300 mb-5">얼마 GEO</h1>

                {/* 구역 분석 버튼 */}
                <button
                    type="button"
                    onClick={handleZoneData}
                    disabled={loading}
                    className="w-full py-2 mb-6 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg transition duration-200"
                >
                    {loading ? '분석 중...' : '구역 필지 분석하기'}
                </button>

                <form onSubmit={handleSubmit} className="space-y-4 w-full">
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-1">구역 이름</label>
                        <input
                            type="text"
                            name="name"
                            value={formData.name}
                            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-1">조합원 수</label>
                        <input
                            type="number"
                            name="member_count"
                            value={formData.member_count}
                            onChange={handleChange}
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-1">원하는 평형 (예: 84)</label>
                        <input
                            type="text"
                            value={ownerData.desired_unit}
                            onChange={(e) => setOwnerData(prev => ({ ...prev, desired_unit: e.target.value }))}
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-1">소유 토지/건물 공시가격 (만원)</label>
                        <input
                            type="number"
                            value={ownerData.official_price}
                            onChange={(e) => setOwnerData(prev => ({ ...prev, official_price: Number(e.target.value) }))}
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none"
                        />
                    </div>

                    {/* 필지 분석을 한 경우에만 렌더링 */}
                    {zoneCalculated ? (
                        <>
                            <div className="my-4 p-4 bg-slate-700 rounded-xl">
                                <Slider sliders={sliderData} onChange={handleSliderChange} />
                            </div>

                            <button
                                type="submit"
                                disabled={loading || !zoneInfo}
                                className="w-full py-3 mt-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition duration-200 disabled:opacity-50"
                            >
                                {loading ? '계산 중...' : '분담금 및 사업성 최종 계산'}
                            </button>
                        </>
                    ) : (
                        <div className="mt-4 p-4 bg-slate-800 rounded-lg text-center text-sm text-slate-400">
                            구역 필지 분석을 먼저 진행해주세요.
                        </div>
                    )}
                </form>

                {error && (
                    <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs w-full break-all">
                        {error}
                    </div>
                )}

                {calcResult && (
                    <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg text-center w-full space-y-1">
                        <span className="text-sm font-medium text-green-700 block mb-2 font-bold">🎉 계산 결과</span>
                        <p className="text-sm text-gray-700">예상 분담금: <span className="font-extrabold text-green-900">{calcResult.contribution?.toLocaleString()} 만원</span></p>
                        <p className="text-sm text-gray-700">비례율: <span className="font-extrabold text-green-900">{calcResult.proportional_rate}%</span></p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ModelPredictForm;
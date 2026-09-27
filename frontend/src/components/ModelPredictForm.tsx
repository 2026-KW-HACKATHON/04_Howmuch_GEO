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
        <div className={`h-full w-full bg-slate-50/50 flex flex-col items-center p-6 font-sans overflow-y-auto transition-opacity ${isOpen ? 'opacity-100 duration-500' : 'opacity-0 pointer-events-none duration-100'}`}>
            <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200 p-8 flex flex-col items-center">
                <h1 className="text-2xl font-extrabold text-slate-900 mb-6 tracking-tight">얼마 GEO 분석</h1>

                {/* 구역 분석 버튼 */}
                <button
                    type="button"
                    onClick={handleZoneData}
                    disabled={loading}
                    className="w-full py-3 mb-6 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl shadow-md transition duration-200 disabled:opacity-50"
                >
                    {loading ? '분석 중...' : '구역 필지 분석하기'}
                </button>
                {/* 필지 분석을 한 경우에만 렌더링 */}
                {zoneCalculated ? (
                    <>
                        <form onSubmit={handleSubmit} className="space-y-4 w-full">
                            <div>
                                <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">구역 이름</label>
                                <input
                                    type="text"
                                    name="name"
                                    value={formData.name}
                                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white text-slate-800 text-sm transition"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">조합원 수</label>
                                <input
                                    type="number"
                                    name="member_count"
                                    value={formData.member_count}
                                    onChange={handleChange}
                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white text-slate-800 text-sm transition"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">원하는 평형 (예: 84)</label>
                                <input
                                    type="text"
                                    value={ownerData.desired_unit}
                                    onChange={(e) => setOwnerData(prev => ({ ...prev, desired_unit: e.target.value }))}
                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white text-slate-800 text-sm transition"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">소유 토지/건물 공시가격 (만원)</label>
                                <input
                                    type="number"
                                    value={ownerData.official_price}
                                    onChange={(e) => setOwnerData(prev => ({ ...prev, official_price: Number(e.target.value) }))}
                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white text-slate-800 text-sm transition"
                                />
                            </div>
                            
                                <div className="my-4 p-4 bg-slate-50 border border-slate-200 rounded-xl shadow-inner">
                                    <Slider sliders={sliderData} onChange={handleSliderChange} />
                                </div>

                                <button
                                    type="submit"
                                    disabled={loading || !zoneInfo}
                                    className="w-full py-3 mt-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl shadow-md transition duration-200 disabled:opacity-50"
                                >
                                    {loading ? '계산 중...' : '분담금 및 사업성 최종 계산'}
                                </button>
                            </form>
                        </>
                    ) : (
                        <div className="mt-4 p-4 bg-slate-50 border border-dashed border-slate-300 rounded-xl text-center text-sm font-medium text-slate-500">
                            구역 필지 분석을 먼저 진행해주세요.
                        </div>
                    )}

                {error && (
                    <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs w-full break-all">
                        {error}
                    </div>
                )}

                {calcResult && (
                    <div className="mt-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-center w-full space-y-1.5 shadow-sm">
                        <span className="text-sm font-bold text-emerald-800 block mb-2">🎉 계산 결과</span>
                        <p className="text-sm text-slate-700">예상 분담금: <span className="font-extrabold text-emerald-900">{calcResult.contribution?.toLocaleString()} 만원</span></p>
                        <p className="text-sm text-slate-700">비례율: <span className="font-extrabold text-emerald-900">{calcResult.proportional_rate}%</span></p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ModelPredictForm;
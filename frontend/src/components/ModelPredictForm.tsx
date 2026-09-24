import React, { useState } from 'react'

//컴포넌트 Props 타입 정의
interface ModelPredictFormProps {
    onPredictModel: (requestData: {
        area: number;
        floor: number;
        building_age: number;
        subway_distance: number;
    }) => Promise<any>;
    isOpen: boolean;
}

//AI 예측 모델 Form 컴포넌트 ( Dummy Model )
const ModelPredictForm: React.FC<ModelPredictFormProps> = ({onPredictModel, isOpen}) => {
    //useState 정의부
    const [formData, setFormData] = useState({
        area: 0,
        floor: 0,
        building_age: 0,
        subway_distance: 0,
    })
    const [predictedPrice, setPredictedPrice] = useState<number | null>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    //Form 의 Input 값 변화시의 Handler
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {

        //변화한 값 구조 분해 할당
        const { name, value } = e.target;
        setFormData((prev) => ({

            //다른 Input 값 보존을 위한 로직
            ...prev,
            [name]: value === '' ? '' : Number(value),
        }))
    }

    //Form 제출시의 Handler
    const handleSubmit = async (e: any) => {
        //불필요한 페이지 Reload 방지
        e.preventDefault();

        //예측 전 초기화 단계
        setLoading(true);
        setPredictedPrice(null);
        setError(null);

        try {
            // 백엔드 요청 스키마 반영 (Dummy Model)
            const requestData = {
                area: Number(formData.area),
                floor: Number(formData.floor),
                building_age: Number(formData.building_age),
                subway_distance: Number(formData.subway_distance)
            }
            
            //AI 예측 모델 API 호출
            const data = await onPredictModel(requestData);

            if (data && data.predicted_price !== undefined) {
                setPredictedPrice(data.predicted_price);
            } else {
                throw new Error("예측 결과를 받아오지 못했습니다.");
            }
        } catch (err) {
            setError("가격 예측 중 오류가 발생했습니다.");
        } finally {
            setLoading(false); //예측 후 로딩 해제
        }
    }

    return (
        <div className={`h-full w-full bg-slate-700 flex flex-col items-center p-6 font-sans overflow-y-auto transition-opacity ${isOpen ? 'opacity-100 duration-500' : 'opacity-0 pointer-events-none duration-100'}`}>

            {/* 예측 Form 박스 영역 */}
            <div className="max-w-md w-full bg-slate-600 rounded-2xl shadow-lg border border-slate-500 p-8 flex flex-col items-center ">
                <h1 className="text-2xl font-bold text-slate-300 mb-5">가격 예측 모델</h1>
                <form onSubmit={handleSubmit} className="space-y-4">

                    {/* 면적 입력 영역 */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-1">면적</label>
                        <input
                            type="number"
                            name="area"
                            step="any"
                            onChange={handleChange}
                            placeholder="예: 84"
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>

                    {/* 층수 입력 영역 */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-1">층수</label>
                        <input
                            type="number"
                            name="floor"
                            step="any"
                            onChange={handleChange}
                            placeholder="예: 5"
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>

                    {/* 건물 연식 입력 영역 */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-1">건물 연식</label>
                        <input
                            type="number"
                            name="building_age"
                            step="any"
                            onChange={handleChange}
                            placeholder="예: 10"
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>

                    {/* 역 거리 입력 영역 */}
                    <div>
                        <label className="block text-sm font-semibold text-slate-300 mb-1">역 거리</label>
                        <input
                            type="number"
                            name="subway_distance"
                            step="any"
                            onChange={handleChange}
                            placeholder="예: 300"
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>

                    {/* Form 요청 버튼 영역 */}
                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full py-3 mt-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition duration-200 disabled:opacity-50"
                    >
                        {loading ? '예측 요청 중...' : '가격 예측하기'}
                    </button>
                </form>
                    {error && (
                        //모델 예측 API 오류 발생시 Error 메시지 Div 삽입
                        <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs break-all">
                            {error}
                        </div>
                    )}

                    {predictedPrice !== null && (
                        //모델 예측 API 성공적으로 반환시 예측 결과 Div 삽입
                        <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg text-center">
                            <span className="text-sm font-medium text-green-700 block mb-1">예측 가격</span>
                            <span className="text-2xl font-extrabold text-green-900">
                            {predictedPrice.toLocaleString('ko-KR', { maximumFractionDigits: 0 })} 만원
                            </span>
                        </div>
                    )}
            </div>
        </div>
    );
};

export default ModelPredictForm;
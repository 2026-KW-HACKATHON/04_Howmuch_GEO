import { useKakaoMap } from '../hooks/useKakaoMap';
import { useMapDragSelect } from '../hooks/useMapDragSelect';
import MapLegend from './MapLegend';

const KakaoMap = ({ onLoadCadastralData }) => {
    //지도 및 필지 관리 훅
    const { mapRef, map, selectedPnus, setSelectedPnus, featuresMapRef } = useKakaoMap(onLoadCadastralData);
    
    //드래그 선택 훅
    const { isDragSelectMode, setIsDragSelectMode } = useMapDragSelect(map, featuresMapRef, setSelectedPnus);

    return (
        <div className="w-full h-screen relative">
            
            {/* 우측 상단 드래그 기능 토글 영역 */}
            <div className="absolute top-4 right-4 z-10 bg-white p-2 rounded shadow-md flex gap-2 items-center">
                <button
                    onClick={() => setIsDragSelectMode(!isDragSelectMode)}
                    className={`px-3 py-1.5 rounded text-sm font-semibold transition-colors ${
                        isDragSelectMode 
                            ? 'bg-blue-600 text-white' 
                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                >
                    {isDragSelectMode ? '드래그 모드' : '일반 이동 모드'}
                </button>
                <button
                    onClick={() => setSelectedPnus([])}
                    className="px-3 py-1.5 bg-red-100 text-red-600 rounded text-sm font-semibold hover:bg-red-200"
                >
                    선택 초기화
                </button>
            </div>

            {/* 지도 DOM 컨테이너 */}
            <div ref={mapRef} className="w-full h-full" />
            <MapLegend />
        </div>
    );
};

export default KakaoMap;
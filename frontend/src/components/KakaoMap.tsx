import React, { useEffect, useRef } from 'react';
import { useKakaoMap } from '../hooks/useKakaoMap';
import { useMapDragSelect } from '../hooks/useMapDragSelect';
import MapLegend from './MapLegend';
import { ParcelInfo, parcelFromFeature } from '../utils/parcel';

//카카오맵 Props
interface KakaoMapProps {
    onLoadCadastralData: () => Promise<any>;
    //★ 부모에게 선택된 PNU와 그 필지의 면적·공시지가를 알려주는 콜백
    onSelectionChange?: (pnus: string[], parcels: ParcelInfo[]) => void;
    onRegionNameChange?: (regionName: string) => void;
}

//카카오맵 컴포넌트
const KakaoMap: React.FC<KakaoMapProps> = ({ onLoadCadastralData, onSelectionChange, onRegionNameChange }) => {
    //지도 및 필지 관리 훅
    const { mapRef, map, selectedPnus, setSelectedPnus, regionName, featuresMapRef } = useKakaoMap(onLoadCadastralData);
    
    //드래그 선택 훅
    const { isDragSelectMode, setIsDragSelectMode } = useMapDragSelect(map, featuresMapRef, setSelectedPnus);

    //콜백은 부모가 매 렌더 새로 만들 수 있다. 의존성에 넣으면 무한 루프가 되므로 ref 로 잡는다
    const onSelectionChangeRef = useRef(onSelectionChange);
    onSelectionChangeRef.current = onSelectionChange;

    useEffect(() => {
        onRegionNameChange?.(regionName);
    }, [regionName, onRegionNameChange]);

    //selectedPnus 가 바뀔 때만 갱신
    useEffect(() => {
        const notify = onSelectionChangeRef.current;
        if (!notify) return;

        //지적도 응답에 면적(폴리곤)과 개별공시지가(jiga)가 있어서 그대로 넘긴다
        const parcels = selectedPnus
            .map((pnu) => parcelFromFeature(featuresMapRef.current[pnu]))
            .filter((parcel): parcel is ParcelInfo => parcel !== null);

        notify(selectedPnus, parcels);
    }, [selectedPnus, featuresMapRef]);

    return (
        <div className="w-full h-screen relative">
            {/* 지도 DOM 컨테이너 */}
            <div ref={mapRef} className="w-full h-full" />
            {regionName && (
                <div className="absolute right-6 top-20 z-10 rounded-lg border border-slate-200 bg-white/95 px-4 py-2 text-sm font-semibold text-slate-800 shadow-md backdrop-blur-sm">
                    {regionName}
                </div>
            )}
            <div className="absolute bottom-6 right-6 z-10 flex flex-col items-end gap-2">
                <MapLegend />
                <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white/95 p-2 shadow-xl backdrop-blur-md">
                    <button
                        type="button"
                        onClick={() => setIsDragSelectMode(!isDragSelectMode)}
                        className={`rounded px-3 py-1.5 text-sm font-semibold transition-colors ${
                            isDragSelectMode
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        }`}
                    >
                        {isDragSelectMode ? '드래그 모드' : '일반 이동 모드'}
                    </button>
                    <button
                        type="button"
                        onClick={() => setSelectedPnus([])}
                        className="rounded bg-red-100 px-3 py-1.5 text-sm font-semibold text-red-600 hover:bg-red-200"
                    >
                        선택 초기화
                    </button>
                </div>
            </div>
        </div>
    );
};

export default KakaoMap;
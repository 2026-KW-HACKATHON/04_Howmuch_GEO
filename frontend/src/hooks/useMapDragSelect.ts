import { useState, useEffect, useRef, Dispatch, SetStateAction } from 'react';

//지도 드래그 다중 선택 Handler
export const useMapDragSelect = (
    map: any,
    featuresMapRef: { current: Record<string, any> },
    setSelectedPnus: Dispatch<SetStateAction<string[]>>
) => {
    const [isDragSelectMode, setIsDragSelectMode] = useState<boolean>(false);
    
    const isDragSelectModeRef = useRef<boolean>(isDragSelectMode);
    isDragSelectModeRef.current = isDragSelectMode;

    //지도 드래그 다중 선택용 useEffect
    useEffect(() => {
        if (!map) return;

        const kakaoMap = (window as any).kakao.maps;

        let isDragging = false;
        let startPoint: any = null;
        let rectOverlay: any = null;

        const handleMouseDown = (mouseEvent: any) => {
            if (!isDragSelectModeRef.current) return;
            
            isDragging = true;
            startPoint = mouseEvent.latLng;
            map.setDraggable(false);
        };

        const handleMouseMove = (mouseEvent: any) => {
            if (!isDragging || !startPoint) return;

            const currentPoint = mouseEvent.latLng;

            if (rectOverlay) {
                rectOverlay.setMap(null);
            }

            const sw = new kakaoMap.LatLng(
                Math.min(startPoint.getLat(), currentPoint.getLat()),
                Math.min(startPoint.getLng(), currentPoint.getLng())
            );
            const ne = new kakaoMap.LatLng(
                Math.max(startPoint.getLat(), currentPoint.getLat()),
                Math.max(startPoint.getLng(), currentPoint.getLng())
            );

            rectOverlay = new kakaoMap.Rectangle({
                bounds: new kakaoMap.LatLngBounds(sw, ne),
                strokeWeight: 1,
                strokeColor: '#0066ff',
                strokeOpacity: 0.8,
                fillColor: '#0066ff',
                fillOpacity: 0.2
            });
            rectOverlay.setMap(map);
        };

        const handleMouseUp = () => {
            if (!isDragging) return;
            isDragging = false;
            map.setDraggable(true);

            if (rectOverlay) {
                const bounds = rectOverlay.getBounds();
                rectOverlay.setMap(null);
                rectOverlay = null;

                const newlySelected: string[] = [];

                Object.entries(featuresMapRef.current).forEach(([pnu, feature]: [string, any]) => {
                    const geometry = feature.geometry;
                    const coordinates = geometry.coordinates;

                    let rings: any[] = [];
                    if (geometry.type === 'Polygon') {
                        rings = [coordinates[0]];
                    } else if (geometry.type === 'MultiPolygon') {
                        rings = coordinates.map((poly: any[]) => poly[0]);
                    }

                    let isCompletelyInside = true;

                    for (const ring of rings) {
                        for (const [lng, lat] of ring) {
                            const point = new kakaoMap.LatLng(lat, lng);
                            if (!bounds.contain(point)) {
                                isCompletelyInside = false;
                                break;
                            }
                        }
                        if (!isCompletelyInside) break;
                    }

                    if (isCompletelyInside) {
                        newlySelected.push(pnu);
                    }
                });

                setSelectedPnus((prev) => Array.from(new Set([...prev, ...newlySelected])));
            }
        };

        kakaoMap.event.addListener(map, 'mousedown', handleMouseDown);
        kakaoMap.event.addListener(map, 'mousemove', handleMouseMove);
        kakaoMap.event.addListener(map, 'mouseup', handleMouseUp);

        return () => {
            kakaoMap.event.removeListener(map, 'mousedown', handleMouseDown);
            kakaoMap.event.removeListener(map, 'mousemove', handleMouseMove);
            kakaoMap.event.removeListener(map, 'mouseup', handleMouseUp);
        };
    }, [map, featuresMapRef, setSelectedPnus]);

    return {
        isDragSelectMode,
        setIsDragSelectMode,
    };
};
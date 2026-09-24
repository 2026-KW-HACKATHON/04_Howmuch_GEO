import { useState, useEffect, useRef } from 'react';

//지도 드래그 다중 선택 Handler
export const useMapDragSelect = (map, featuresMapRef, setSelectedPnus) => {
    const [isDragSelectMode, setIsDragSelectMode] = useState(false);
    
    const isDragSelectModeRef = useRef(isDragSelectMode);
    isDragSelectModeRef.current = isDragSelectMode;

    //지도 드래그 다중 선택용 useEffect
    useEffect(() => {
        if (!map) return;

        let isDragging = false;
        let startPoint = null;
        let rectOverlay = null;

        const handleMouseDown = (mouseEvent) => {
            if (!isDragSelectModeRef.current) return;
            
            isDragging = true;
            startPoint = mouseEvent.latLng;
            map.setDraggable(false);
        };

        const handleMouseMove = (mouseEvent) => {
            if (!isDragging || !startPoint) return;

            const currentPoint = mouseEvent.latLng;

            if (rectOverlay) {
                rectOverlay.setMap(null);
            }

            const sw = new window.kakao.maps.LatLng(
                Math.min(startPoint.getLat(), currentPoint.getLat()),
                Math.min(startPoint.getLng(), currentPoint.getLng())
            );
            const ne = new window.kakao.maps.LatLng(
                Math.max(startPoint.getLat(), currentPoint.getLat()),
                Math.max(startPoint.getLng(), currentPoint.getLng())
            );

            rectOverlay = new window.kakao.maps.Rectangle({
                bounds: new window.kakao.maps.LatLngBounds(sw, ne),
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

                const newlySelected = [];

                Object.entries(featuresMapRef.current).forEach(([pnu, feature]) => {
                    const geometry = feature.geometry;
                    const coordinates = geometry.coordinates;

                    let rings = [];
                    if (geometry.type === 'Polygon') {
                        rings = [coordinates[0]];
                    } else if (geometry.type === 'MultiPolygon') {
                        rings = coordinates.map((poly) => poly[0]);
                    }

                    let isCompletelyInside = true;

                    for (const ring of rings) {
                        for (const [lng, lat] of ring) {
                            const point = new window.kakao.maps.LatLng(lat, lng);
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

        window.kakao.maps.event.addListener(map, 'mousedown', handleMouseDown);
        window.kakao.maps.event.addListener(map, 'mousemove', handleMouseMove);
        window.kakao.maps.event.addListener(map, 'mouseup', handleMouseUp);

        return () => {
            window.kakao.maps.event.removeListener(map, 'mousedown', handleMouseDown);
            window.kakao.maps.event.removeListener(map, 'mousemove', handleMouseMove);
            window.kakao.maps.event.removeListener(map, 'mouseup', handleMouseUp);
        };
    }, [map, featuresMapRef, setSelectedPnus]);

    return {
        isDragSelectMode,
        setIsDragSelectMode,
    };
};
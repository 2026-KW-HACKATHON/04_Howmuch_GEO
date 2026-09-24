import { useEffect, useState, useRef } from 'react';

//KakaoMap Hook
export const useKakaoMap = (onLoadCadastralData) => {
    const mapRef = useRef(null);
    const polygonsRef = useRef({});
    const featuresMapRef = useRef({});

    const [map, setMap] = useState(null);
    const [selectedPnus, setSelectedPnus] = useState([]);
    
    const selectedPnusRef = useRef(selectedPnus);
    selectedPnusRef.current = selectedPnus;

    //Kakao Map 로드용 useEffect
    useEffect(() => {
        const apiKey = import.meta.env.VITE_KAKAO_JS_KEY;

        const initMap = () => {
            const container = mapRef.current;
            if (!container) return;

            const options = {
                center: new window.kakao.maps.LatLng(37.621, 127.059),
                level: 2,
            };
            
            const kakaoMap = new window.kakao.maps.Map(container, options);
            setMap(kakaoMap);
        };

        if (document.getElementById('kakao-map-sdk')) {
            if (window.kakao && window.kakao.maps) {
                window.kakao.maps.load(initMap);
            }
            return;
        }

        const script = document.createElement('script');
        script.id = 'kakao-map-sdk';
        script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${apiKey}&libraries=services&autoload=false`;
        script.async = true;
        script.onload = () => window.kakao.maps.load(initMap);
        document.head.appendChild(script);

    }, []);

    //필지 Polygon 렌더링 및 이동 Handler
    useEffect(() => {
        if (!map) return;

        const useDistrictType = window.kakao.maps.MapTypeId.USE_DISTRICT;
        map.addOverlayMapTypeId(useDistrictType);

        const fetchCadastralData = async () => {
            try {
                const response = await onLoadCadastralData();

                Object.values(polygonsRef.current).forEach((poly) => poly.setMap(null));
                polygonsRef.current = {};
                
                const featureCollection = response?.response?.result?.featureCollection;
                if (!featureCollection || !featureCollection.features) return;

                featureCollection.features.forEach((feature) => {
                    const { geometry, properties } = feature;
                    const pnu = properties.pnu;
                    const coordinates = geometry.coordinates;
                    
                    featuresMapRef.current[pnu] = feature;

                    const makePath = (ring) => ring.map(([lng, lat]) => new window.kakao.maps.LatLng(lat, lng));
                    let paths = [];

                    if (geometry.type === 'Polygon') {
                        paths = [makePath(coordinates[0])];
                    } else if (geometry.type === 'MultiPolygon') {
                        paths = coordinates.map((polygon) => makePath(polygon[0]));
                    }

                    paths.forEach((path) => {
                        const isSelected = selectedPnusRef.current.includes(pnu);
                        
                        const polygon = new window.kakao.maps.Polygon({
                            path: path,
                            strokeWeight: 2,
                            strokeColor: '#ff7800',
                            strokeOpacity: 0.8,
                            fillColor: isSelected ? '#FF5733' : '#fff', 
                            fillOpacity: isSelected ? 0.6 : 0.2,
                        });
                        polygon.setMap(map);
                        
                        window.kakao.maps.event.addListener(polygon, 'click', () => {
                            setSelectedPnus((prev) => {
                                if (prev.includes(pnu)) {
                                    return prev.filter((item) => item !== pnu);
                                } else {
                                    return [...prev, pnu];
                                }
                            });
                        });
                        polygonsRef.current[pnu] = polygon;
                    });
                });
            } catch (err) {
                console.log("[ fetchCadastralData 오류 발생 ] : ", err);
            }
        };

        //지도 움직임 Handler
        const handleMapMovement = async () => {
            const currentLevel = map.getLevel();
            if (currentLevel > 2) {
                Object.values(polygonsRef.current).forEach((poly) => poly.setMap(null));
                polygonsRef.current = {};
                return;
            }
            await fetchCadastralData();
        };

        handleMapMovement();
        window.kakao.maps.event.addListener(map, 'idle', handleMapMovement);

        return () => {
            window.kakao.maps.event.removeListener(map, 'idle', handleMapMovement);
        };
    }, [map]);

    //selectedPnus 변경시 폴리곤 색상 업데이트
    useEffect(() => {
        Object.entries(polygonsRef.current).forEach(([pnu, polygon]) => {
            const isSelected = selectedPnus.includes(pnu);
            polygon.setOptions({
                fillColor: isSelected ? '#FF5733' : '#fff',
                fillOpacity: isSelected ? 0.6 : 0.2,
            });
        });
    }, [selectedPnus]);

    return {
        mapRef,
        map,
        selectedPnus,
        setSelectedPnus,
        featuresMapRef,
    };
};
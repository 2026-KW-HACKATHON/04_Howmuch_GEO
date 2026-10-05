/// <reference types="vite/client" />
import { useEffect, useState, useRef } from 'react';

type CadastralDataLoader = (geomFilter: string) => Promise<any>;

//KakaoMap Hook
export const useKakaoMap = (onLoadCadastralData : CadastralDataLoader) => {
    const mapRef = useRef<HTMLDivElement | null>(null);
    const polygonsRef = useRef<Record<string, any>>({});
    const featuresMapRef = useRef<Record<string, any>>({});

    const [map, setMap] = useState<any>(null);
    const [selectedPnus, setSelectedPnus] = useState<string[]>([]);
    const [regionName, setRegionName] = useState('');

    const selectedPnusRef = useRef<string[]>(selectedPnus);
    selectedPnusRef.current = selectedPnus;

    //Kakao Map 로드용 useEffect
    useEffect(() => {
        const apiKey = import.meta.env.VITE_KAKAO_JS_KEY;

        const initMap = () => {
            const container = mapRef.current;
            if (!container) return;

            const options = {
                center: new (window as any).kakao.maps.LatLng(37.621, 127.059),
                level: 2,
            };
            
            const kakaoMap = new (window as any).kakao.maps.Map(container, options);
            setMap(kakaoMap);
        };

        if (document.getElementById('kakao-map-sdk')) {
            if ((window as any).kakao && (window as any).kakao.maps) {
                (window as any).kakao.maps.load(initMap);
            }
            return;
        }

        const script = document.createElement('script');
        script.id = 'kakao-map-sdk';
        script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${apiKey}&libraries=services&autoload=false`;
        script.async = true;
        script.onload = () => (window as any).kakao.maps.load(initMap);
        document.head.appendChild(script);

    }, []);

    //필지 Polygon 렌더링 및 이동 Handler
    useEffect(() => {
        if (!map) return;

        const useDistrictType = (window as any).kakao.maps.MapTypeId.USE_DISTRICT;
        map.addOverlayMapTypeId(useDistrictType);
        const geocoder = new window.kakao.maps.services.Geocoder();

        const fetchCadastralData = async (geomFilter: any) => {
            try {
                const response = await onLoadCadastralData(geomFilter);

                Object.values(polygonsRef.current).forEach((poly: any) => poly.setMap(null));
                polygonsRef.current = {};
                
                const featureCollection = response?.response?.result?.featureCollection;
                if (!featureCollection || !featureCollection.features) return;

                featureCollection.features.forEach((feature: any) => {
                    const { geometry, properties } = feature;
                    const pnu = properties.pnu;
                    const coordinates = geometry.coordinates;
                    
                    featuresMapRef.current[pnu] = feature;

                    const makePath = (ring: Number[][]) => ring.map(([lng, lat]) => new (window as any).kakao.maps.LatLng(lat, lng));
                    let paths: Array<Array<any>> = [];

                    if (geometry.type === 'Polygon') {
                        paths = [makePath(coordinates[0])];
                    } else if (geometry.type === 'MultiPolygon') {
                        paths = coordinates.map((polygon: any[]) => makePath(polygon[0]));
                    }

                    paths.forEach((path: any[]) => {
                        const isSelected = selectedPnusRef.current.includes(pnu);
                        
                        const polygon = new (window as any).kakao.maps.Polygon({
                            path: path,
                            strokeWeight: 2,
                            strokeColor: '#ff7800',
                            strokeOpacity: 0.8,
                            fillColor: isSelected ? '#FF5733' : '#fff', 
                            fillOpacity: isSelected ? 0.6 : 0.2,
                        });
                        polygon.setMap(map);
                        
                        (window as any).kakao.maps.event.addListener(polygon, 'click', () => {
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

        const fetchRegionName = () => {
            const center = map.getCenter();
            
            geocoder.coord2RegionCode(center.getLng(), center.getLat(), (result, status) => {
                if (status === window.kakao.maps.services.Status.OK) {
                    const regionH = result.find((item) => item.region_type === 'H');
                    if (regionH) {
                        setRegionName(regionH.address_name);
                        console.log("[ fetchRegionName ] regionName: ", regionH.address_name);
                    }
                }
            });
        };

        //지도 움직임 Handler
        const handleMapMovement = async () => {
            fetchRegionName();
            const currentLevel = map.getLevel();
            if (currentLevel > 2) {
                Object.values(polygonsRef.current).forEach((poly: any) => poly.setMap(null));
                polygonsRef.current = {};
                return;
            }

            //현재 화면 좌표 및 geomFilter 계산
            const bounds = map.getBounds();
            const sw = bounds.getSouthWest();
            const ne = bounds.getNorthEast();
            const geomFilter = `BOX(${sw.getLng()},${sw.getLat()},${ne.getLng()},${ne.getLat()})`;
            console.log("[ handleMapMovement ] geomFilter: ", geomFilter);
            await fetchCadastralData(geomFilter);
        };

        handleMapMovement();
        (window as any).kakao.maps.event.addListener(map, 'idle', fetchRegionName);
        (window as any).kakao.maps.event.addListener(map, 'idle', handleMapMovement);

        return () => {
            (window as any).kakao.maps.event.removeListener(map, 'idle', fetchRegionName);
            (window as any).kakao.maps.event.removeListener(map, 'idle', handleMapMovement);
        };
    }, [map]);

    //selectedPnus 변경시 폴리곤 색상 업데이트
    useEffect(() => {
        Object.entries(polygonsRef.current).forEach(([pnu, polygon]: [string, any]) => {
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
        regionName,
        featuresMapRef,
    };
};
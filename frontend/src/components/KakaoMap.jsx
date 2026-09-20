import { useEffect, useState, useRef } from 'react';

//KakaoMap 컴포넌트
const KakaoMap = ({onLoadCadastralData}) => {
    const mapRef = useRef(null);
    const polygonsRef = useRef({});

    const [map, setMap] = useState(null);
    const [selectedPnus, setSelectedPnus] = useState([]);
    const featuresMapRef = useRef({});

    //Kakao Map 로드용 useEffect
    useEffect(() => {
        //API Key 설정값
        const apiKey = import.meta.env.VITE_KAKAO_JS_KEY;

        //Map 초기화
        const initMap = () => {
            const container = mapRef.current;
            if (!container) return;

            const options = {
                center: new window.kakao.maps.LatLng(37.621, 127.059), //광운대 근처의 좌표 설정
                level: 3,
            };

            const kakaoMap = new window.kakao.maps.Map(container, options);

            //useState 로 map 저장
            setMap(kakaoMap);
        };

        //이미 SDK 스크립트가 로드되어 있는 경우
        if (document.getElementById('kakao-map-sdk')) {
            if (window.kakao && window.kakao.maps) {
                window.kakao.maps.load(initMap);
            }
            return;
        }

        //카카오 지도 SDK 동적 로드
        const script = document.createElement('script');
        script.id = 'kakao-map-sdk';
        script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${apiKey}&libraries=services&autoload=false`;
        script.async = true;

        script.onload = () => {
            window.kakao.maps.load(initMap);
        };

        document.head.appendChild(script);
    }, []);

    //필지 Polygon 렌더링
    useEffect(() => {
        if (!map) return;

        //Cadastral 데이터를 받아오는 내부 함수
        const fetchCadastralData = async () => {
            try {
                const response = await onLoadCadastralData();

                //polygon 초기화
                Object.values(polygonsRef.current).forEach((poly) => poly.setMap(null));
                polygonsRef.current = {};
                
                //response 의 featureCollection 부분 (JSON)
                const featureCollection = response?.response?.result?.featureCollection;
                if (!featureCollection || !featureCollection.features) return;

                //featureCollection 에 대한 모든 feature 정보 추출
                featureCollection.features.forEach((feature) => {
                    const { geometry, properties } = feature;
                    const pnu = properties.pnu;
                    const coordinates = geometry.coordinates;
                    
                    //pnu 정보를 key 값으로 좌표정보까지 저장
                    featuresMapRef.current[pnu] = feature;

                    const makePath = (ring) => ring.map(([lng, lat]) => new window.kakao.maps.LatLng(lat, lng));

                    let paths = [];

                    if (geometry.type === 'Polygon') {
                        paths = [makePath(coordinates[0])];
                    } else if (geometry.type === 'MultiPolygon') {
                        paths = coordinates.map((polygon) => makePath(polygon[0]));
                    }

                    //조회한 모든 
                    paths.forEach((path) => {
                        const isSelected = selectedPnus.includes(pnu);

                        const polygon = new window.kakao.maps.Polygon({
                            path: path,
                            strokeWeight: 2,
                            strokeColor: '#ff7800',
                            strokeOpacity: 0.8,
                            fillColor: isSelected ? '#FF5733' : '#fff', 
                            fillOpacity: isSelected ? 0.6 : 0.2,
                        });

                        polygon.setMap(map);
                        
                        //Polygon 클릭시 상호작용 이벤트
                        window.kakao.maps.event.addListener(polygon, 'click', () => {
                            setSelectedPnus((prev) => {
                                if (prev.includes(pnu)) {
                                    //이미 선택되어 있으면 해제
                                    return prev.filter((item) => item !== pnu);
                                } else {
                                    //선택되어 있지 않다면 추가
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

        fetchCadastralData();
    }, [map]);

    //selectedPnus 변경시 업데이트용 useEffect
    useEffect(() => {
        Object.entries(polygonsRef.current).forEach(([pnu, polygon]) => {
            const isSelected = selectedPnus.includes(pnu);
            polygon.setOptions({
                fillColor: isSelected ? '#FF5733' : '#fff',
                fillOpacity: isSelected ? 0.6 : 0.2,
            });
        });

        //다중 선택한 필지들에 대한 정보 테스트 출력부
        //const selectedFeatures = selectedPnus.map(pnu => featuresMapRef.current[pnu]);
        //console.log(selectedFeatures);
    }, [selectedPnus]);

    return (
        <div className="w-full h-screen">
            <div ref={mapRef} className="w-full h-full" />
        </div>
    );
};

export default KakaoMap;
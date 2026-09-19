import { useEffect, useRef } from 'react';

//KakaoMap 컴포넌트
const KakaoMap = () => {
    const mapRef = useRef(null);

    useEffect(() => {
        //API Key 설정값
        const apiKey = import.meta.env.VITE_KAKAO_JS_KEY;

        //Map 초기화
        const initMap = () => {
            const container = mapRef.current;
            if (!container) return;

            const options = {
                center: new window.kakao.maps.LatLng(37.618, 127.059), //광운대 근처의 좌표 설정
                level: 3,
            };

            new window.kakao.maps.Map(container, options);
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

    return (
        <div className="w-full h-screen">
            <div ref={mapRef} className="w-full h-full" />
        </div>
    );
};

export default KakaoMap;
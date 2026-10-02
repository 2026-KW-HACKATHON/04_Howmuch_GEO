/// <reference types="vite/client" />

import { useCallback, useState } from 'react';
import KakaoMap from "../components/KakaoMap"
import SideBar from '../components/SideBar';
import ModelPredictForm from '../components/ModelPredictForm';
import { getVWorldCadastral } from '../api/cadastral_api';
import { getZoneInfo, getContributionInfo } from '../api/realestate_api';
import { ParcelInfo } from '../utils/parcel';
import ReCAPTCHA from 'react-google-recaptcha';

//메인
function App() {
    const [isOpen, setIsOpen] = useState<boolean>(true);
    const [isVerified, setIsVerified] = useState<boolean>(false);
    const [selectedPnus, setSelectedPnus] = useState<string[]>([]);

    //선택 필지의 면적·공시지가 (지적도 응답에서 뽑은 값)
    const [selectedParcels, setSelectedParcels] = useState<ParcelInfo[]>([]);

    //선택 필지 갱신 Handler
    //  같은 필지 목록이면 상태를 그대로 둔다. 매번 새 배열을 넣으면 렌더가 무한히 반복된다
    const handleSelectionChange = useCallback((pnus: string[], parcels: ParcelInfo[]) => {
        setSelectedPnus((prev) => (prev.join(',') === pnus.join(',') ? prev : pnus));
        setSelectedParcels((prev) =>
            prev.map((p) => p.pnu).join(',') === parcels.map((p) => p.pnu).join(',') ? prev : parcels
        );
    }, []);

    //사이드바 토글시 isOpen 값 전환
    const toggleSidebar = () => {
        setIsOpen(!isOpen);
    };

    //ReCaptcha Handler
    const handleCaptchaChange = (token: string | null) => {
        if (token) {
            setIsVerified(true);
        }
    };

    //필지 정보 API 호출 Handler
    const handleCadastralData = useCallback(async (geomFilter?: any) => {
        try {
            const response = await getVWorldCadastral(geomFilter);
            return response;
        } catch (err){
            console.log("[ handleCadastralData 오류 발생 ] : ", err);
            throw err;
        }
    }, []);

    //Zone 데이터 API 호출 Handler
    const handleZoneData = useCallback(async (pnus: string[]) => {
        try {
            const response = await getZoneInfo(pnus, { parcels: selectedParcels });
            return response;
        } catch (err){
            console.log("[ handleZoneData 오류 발생 ] : ", err);
            throw err;
        }
    }, [selectedParcels]);

    //Contribution 데이터 API 호출 Handler
    const handleContributionData = useCallback(async (requestData: any) => {
        try {
            const response = await getContributionInfo(requestData);
            return response;
        } catch (err) {
            console.log("[ handleContributionData 오류 발생 ] : ", err);
            throw err;
        }
    }, []);

    return (
        <div className="relative w-screen h-screen overflow-hidden">

            {/* ReCaptcha V2 를 사용하여 트레픽 관리 */}
            {!isVerified ? (

                //ReCaptcha 인증 전 화면
                <div className="flex flex-col items-center justify-center h-full bg-gray-100">
                    <ReCAPTCHA
                        sitekey= {import.meta.env.VITE_GOOGLE_RECAPTCHA_API}
                        onChange={handleCaptchaChange}
                    />
                </div>
            ) : (
                //ReCaptcha 인증 후 화면
                <>
                
                    {/* 카카오 맵 영역 */}
                    <main className="absolute inset-0 w-full h-full">
                        <KakaoMap
                            onLoadCadastralData={handleCadastralData}
                            onSelectionChange={handleSelectionChange}
                        />
                    </main>

                    {/* 사이드바 영역 */}
                    <SideBar isOpen={isOpen} onToggleSidebar={toggleSidebar} 
                        children={
                            <ModelPredictForm onHandleZoneData={handleZoneData} onCalculateContribution={handleContributionData} isOpen={isOpen} selectedPnus={selectedPnus}/>
                        }
                    />
                </>
            )}                
        </div>
    );
};

export default App
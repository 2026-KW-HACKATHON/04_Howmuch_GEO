/// <reference types="vite/client" />

import { useState } from 'react';
import KakaoMap from "./components/KakaoMap"
import SideBar from './components/SideBar';
import ModelPredictForm from './components/ModelPredictForm';
import { predictModel } from './api/ai_model_api';
import { getVWorldCadastral } from './api/cadastral_api';
import { getZoneInfo, getContributionInfo } from './api/realestate_api';
import ReCAPTCHA from 'react-google-recaptcha';

//메인
function App() {
    const [isOpen, setIsOpen] = useState<boolean>(true);
    const [isVerified, setIsVerified] = useState<boolean>(false);
    const [selectedPnus, setSelectedPnus] = useState<string[]>([]);

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

    //AI 모델 API 호출 Handler
    const handlePredictModel = async (requestData: any) => {
        try {
            const response = await predictModel(requestData);
            return response
        } catch (err){
            console.log("[ handlePredictModel 오류 발생 ] : ", err);
            throw err;
        }
	};

    //필지 정보 API 호출 Handler
    const handleCadastralData = async (geomFilter?: any) => {
        try {
            const response = await getVWorldCadastral(geomFilter);
            return response;
        } catch (err){
            console.log("[ handleCadastralData 오류 발생 ] : ", err);
            throw err;
        }
    };

    //Zone 데이터 API 호출 Handler
    const handleZoneData = async (pnus: string[]) => {
        try {
            const response = await getZoneInfo(pnus);
            return response;
        } catch (err){
            console.log("[ handleZoneData 오류 발생 ] : ", err);
            throw err;
        }
    };

    //Contribution 데이터 API 호출 Handler
    const handleContributionData = async (requestData: any) => {
        try {
            const response = await getContributionInfo(requestData);
            return response;
        } catch (err) {
            console.log("[ handleContributionData 오류 발생 ] : ", err);
            throw err;
        }
    };

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
                        <KakaoMap onLoadCadastralData={handleCadastralData} onSelectionChange={(pnus) => setSelectedPnus(pnus)}/>
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
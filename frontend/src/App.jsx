import React, { useState } from 'react';
import KakaoMap from "./components/KakaoMap"
import SideBar from './components/SideBar';
import ModelPredictForm from './components/ModelPredictForm';
import { predictModel } from './api/ai_model_api';
import { getVWorldCadastral } from './api/cadastral_api';
import ReCAPTCHA from 'react-google-recaptcha';

function App() {
    const [isOpen, setIsOpen] = useState(true);
    const [isVerified, setIsVerified] = useState(false);

    //사이드바 토글시 isOpen 값 전환
    const toggleSidebar = () => {
        setIsOpen(!isOpen);
    };

    //ReCaptcha Handler
    const handleCaptchaChange = (token) => {
        if (token) {
            setIsVerified(true);
        }
    };

    //AI 모델 API 호출 Handler
    const handlePredictModel = async (requestData) => {
        try {
            const response = await predictModel(requestData);
            return response
        } catch (err){
            console.log("[ handlePredictModel 오류 발생 ] : ", err);
            throw err;
        }
	};

    //V-World 필지 정보 API 호출 Handler
    const handleCadastralData = async (requestBody) => {
        try {
            const response = await getVWorldCadastral(requestBody);
            return response;
        } catch (err){
            console.log("[ handleCadastralData 오류 발생 ] : ", err);
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
                        <KakaoMap onLoadCadastralData={handleCadastralData}/>
                    </main>

                    {/* 사이드바 영역 */}
                    <SideBar isOpen={isOpen} onToggleSidebar={toggleSidebar} children={<ModelPredictForm onPredictModel={handlePredictModel} isOpen={isOpen}/>} />
                </>
            )}                
        </div>
    );
};

export default App
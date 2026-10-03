/// <reference types="vite/client" />

import KakaoMap from "../components/KakaoMap"
import SideBar from '../components/SideBar';
import ModelPredictForm from '../components/ModelPredictForm';
import ReCAPTCHA from 'react-google-recaptcha';
import { useMainPage } from '../hooks/useMainPage';

//메인 페이지
export default function MainPage() {

    //MainPage Hook 사용
    const {
        isOpen,
        isVerified,
        selectedPnus,
        selectedParcels,
        handleSelectionChange,
        toggleSidebar,
        handleCaptchaChange,
        handleCadastralData,
        handleZoneData,
        handleContributionData
    } = useMainPage();

    //메인 페이지 렌더링
    return (
        <div className="relative w-screen h-screen overflow-hidden">

            {/* 사용자 인증 창 */}
            {!isVerified ? (

                //사용자 인증 전 화면
                <div className="flex flex-col items-center justify-center h-full bg-gray-100">
                    <h1 className="text-2xl font-bold mb-4">사용자 인증</h1>
                    <p className="text-gray-600 mb-8">서비스를 이용하기 위해서는 사용자 인증이 필요합니다.</p>
                    <ReCAPTCHA
                        sitekey= {import.meta.env.VITE_GOOGLE_RECAPTCHA_API}
                        onChange={handleCaptchaChange}
                    />
                </div>
            ) : (
                //사용자 인증 후 화면
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

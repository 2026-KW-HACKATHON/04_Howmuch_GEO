/// <reference types="vite/client" />

import KakaoMap from "../components/KakaoMap"
import SideBar from '../components/SideBar';
import ModelPredictForm from '../components/ModelPredictForm';
import NewsPanel from '../components/NewsPanel';
import ReCAPTCHA from 'react-google-recaptcha';
import { useMainPage } from '../hooks/useMainPage';
import { useEffect, useRef, useState } from 'react';

//메인 페이지
export default function MainPage() {
    const [isProfileOpen, setIsProfileOpen] = useState(false);
    const [activePanel, setActivePanel] = useState<'news' | 'prediction'>('news');
    const [regionName, setRegionName] = useState('');
    const profileRef = useRef<HTMLDivElement>(null);

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
        handleContributionData,
        logoutButtonAction,
        userName,
        userEmail,
        dailyCredits,
        creditsUnavailable,
        resettingCredits,
        resetCreditsAction,
    } = useMainPage();

    //프로필 메뉴 외부 클릭 시 닫기 및 ESC 키로 닫기
    useEffect(() => {
        if (!isProfileOpen) return;

        const closeProfileOnOutsideClick = (event: PointerEvent) => {
            if (!(event.target instanceof Node) || !profileRef.current?.contains(event.target)) {
                setIsProfileOpen(false);
            }
        };
        const closeProfileOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setIsProfileOpen(false);
        };

        document.addEventListener('pointerdown', closeProfileOnOutsideClick);
        document.addEventListener('keydown', closeProfileOnEscape);
        return () => {
            document.removeEventListener('pointerdown', closeProfileOnOutsideClick);
            document.removeEventListener('keydown', closeProfileOnEscape);
        };
    }, [isProfileOpen]);

    //메인 페이지 렌더링
    return (
        <div className="relative w-screen h-screen overflow-hidden">

            {/* 카카오 맵 영역 */}
            <main className="absolute inset-0 w-full h-full">
                <KakaoMap
                    onLoadCadastralData={handleCadastralData}
                    onSelectionChange={handleSelectionChange}
                    onRegionNameChange={setRegionName}
                />
            </main>

            <div ref={profileRef} className="absolute top-4 right-4 z-30">
                <button
                    type="button"
                    aria-label="프로필 열기"
                    aria-expanded={isProfileOpen}
                    onClick={() => setIsProfileOpen((open) => !open)}
                    className="flex h-12 w-12 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-700 shadow-lg transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                >
                <svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6 fill-current">
                    <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-4.42 0-8 2.24-8 5v1h16v-1c0-2.76-3.58-5-8-5Z" />
                </svg>
                </button>

                {isProfileOpen && (
                    <div className="absolute right-0 mt-3 w-64 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
                        <div className="border-b border-slate-100 px-4 py-4">
                            <p className="font-semibold text-slate-900">내 프로필</p>
                            <p className="mt-1 text-sm text-slate-500">{userName}</p>
                            <p className="text-xs text-slate-400">{userEmail}</p>
                            <p className="mt-3 text-sm font-medium text-slate-700">
                                오늘 크레딧 {dailyCredits ?? '-'} / 5
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={resetCreditsAction}
                            disabled={resettingCredits || creditsUnavailable}
                            className="w-full border-b border-slate-100 px-4 py-3 text-left text-sm font-medium text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {resettingCredits ? '초기화 중...' : '크레딧 초기화'}
                        </button>
                        <button
                            type="button"
                            onClick={logoutButtonAction}
                            className="w-full px-4 py-3 text-left text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                        >
                        로그아웃
                        </button>
                    </div>
                )}
            </div>

            {/* 사이드바 영역 */}
            <SideBar
                isOpen={isOpen}
                onToggleSidebar={toggleSidebar}
                activePanel={activePanel}
                onPanelChange={setActivePanel}
                children={
                    <>
                        {activePanel === 'news' ? (
                            <NewsPanel onNewsPanelOpen={activePanel === 'news'} query={regionName}/>
                        ) : (
                            <ModelPredictForm onHandleZoneData={handleZoneData} onCalculateContribution={handleContributionData} isOpen={isOpen} selectedPnus={selectedPnus} dailyCredits={dailyCredits} creditsUnavailable={creditsUnavailable}/>
                        )}
                    </>
                }
            />               
        </div>
    );
};

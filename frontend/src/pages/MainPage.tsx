/// <reference types="vite/client" />

import KakaoMap from "../components/KakaoMap"
import SideBar from '../components/SideBar';
import ModelPredictForm from '../components/ModelPredictForm';
import NewsPanel from '../components/NewsPanel';
import StartupModal from '../components/StartupModal'
import { useMainPage } from '../hooks/useMainPage';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import type { OrganizationMapView } from '../api/organization_api';
import type { ParcelInfo } from '../utils/parcel';

//메인 페이지
export default function MainPage() {
    const [isProfileOpen, setIsProfileOpen] = useState(false);
    const [activePanel, setActivePanel] = useState<'news' | 'prediction'>('prediction');
    const [regionName, setRegionName] = useState('');
    const [mapView, setMapView] = useState<OrganizationMapView | null>(null);
    const [requestedMapView, setRequestedMapView] = useState<OrganizationMapView | null>(null);
    const profileRef = useRef<HTMLDivElement>(null);
    
    //MainPage Hook 사용
    const {
        isOpen,
        isAuthenticated,
        isVerified,
        selectedPnus,
        selectedParcels,
        handleSelectionChange,
        restoreScenarioSelection,
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
        organizationOverview,
    } = useMainPage();

    const handleRestoreScenario = (pnus: string[], parcels: ParcelInfo[], savedMapView: OrganizationMapView) => {
        restoreScenarioSelection(pnus, parcels);
        setRequestedMapView(savedMapView);
    };

    const [startupModalOpen, setStartupModalOpen] = useState<boolean>(true);

    const toggleModal = () => {
        if (startupModalOpen) {
            setStartupModalOpen(false);
        } else {
            setStartupModalOpen(true);
        }
    }

    //페이지 처음 오픈시 기본동작
    useEffect(() => {
        setStartupModalOpen(true);
    },[]);

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
                    selectedPnus={selectedPnus}
                    selectedParcels={selectedParcels}
                    requestedMapView={requestedMapView}
                    onMapViewChange={setMapView}
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
                        {isAuthenticated ? <div className="border-b border-slate-100 px-4 py-4">
                            <p className="font-semibold text-slate-900">내 프로필</p>
                            <p className="mt-1 text-sm text-slate-500">{userName}</p>
                            <p className="text-xs text-slate-400">{userEmail}</p>
                            <p className="mt-3 text-sm font-medium text-slate-700">
                                {dailyCredits === -1 ? '조합 무제한 크레딧' : `사용 가능 크레딧 ${dailyCredits ?? '-'}`}
                            </p>
                        </div> : <div className="border-b border-slate-100 px-4 py-4">
                            <p className="font-semibold text-slate-900">로그인이 필요합니다</p>
                        </div>}
                        {isAuthenticated ? <Link
                            to="/organization"
                            onClick={() => setIsProfileOpen(false)}
                            className="block w-full border-b border-slate-100 px-4 py-3 text-left text-sm font-medium text-emerald-700 transition hover:bg-emerald-50"
                        >
                            조합·가입 관리
                        </Link> : <>
                            <Link to="/login" onClick={() => setIsProfileOpen(false)} className="block w-full border-b border-slate-100 px-4 py-3 text-left text-sm font-medium text-blue-700 transition hover:bg-blue-50">로그인</Link>
                            <Link to="/signup" onClick={() => setIsProfileOpen(false)} className="block w-full px-4 py-3 text-left text-sm font-medium text-slate-700 transition hover:bg-slate-50">회원가입</Link>
                        </>}
                        {isAuthenticated && dailyCredits !== -1 && <Link
                            to="/credits/payment"
                            onClick={() => setIsProfileOpen(false)}
                            className="block w-full border-b border-slate-100 px-4 py-3 text-left text-sm font-medium text-blue-700 transition hover:bg-blue-50"
                        >
                            크레딧 구매 · 5회 ₩500
                        </Link>}
                        {isAuthenticated && <button
                            type="button"
                            onClick={logoutButtonAction}
                            className="w-full px-4 py-3 text-left text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                        >
                        로그아웃
                        </button>}
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
                            <ModelPredictForm
                                onHandleZoneData={handleZoneData}
                                onCalculateContribution={handleContributionData}
                                isOpen={isOpen}
                                selectedPnus={selectedPnus}
                                selectedParcels={selectedParcels}
                                onRestoreSelection={handleRestoreScenario}
                                mapView={mapView}
                                organizationRole={organizationOverview?.role}
                                canUseSharedScenario={Boolean(organizationOverview?.unlimited_credits)}
                                dailyCredits={dailyCredits}
                                creditsUnavailable={creditsUnavailable}
                            />
                        )}
                    </>
                }
            />           

            {startupModalOpen && (
                <StartupModal onToggleModal={toggleModal}/>
            )}    
        </div>
    );
};

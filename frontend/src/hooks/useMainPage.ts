import { getVWorldCadastral } from '../api/cadastral_api';
import { getZoneInfo, getContributionInfo } from '../api/realestate_api';
import { ParcelInfo } from '../utils/parcel';
import { useCallback, useState, useEffect } from 'react';
import { userLogout, userInfo, userCredits } from '../api/user_api';
import { getOrganizationOverview, OrganizationOverview } from '../api/organization_api';
import axios from 'axios';

//MainPage Hook
export const useMainPage = () => {
    const [isOpen, setIsOpen] = useState<boolean>(true);
    const [isVerified, setIsVerified] = useState<boolean>(false);
    const [selectedPnus, setSelectedPnus] = useState<string[]>([]);

    const [userName, setUserName] = useState<string>('');
    const [userEmail, setUserEmail] = useState<string>('');
    const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
    const [dailyCredits, setDailyCredits] = useState<number | null>(null);
    const [creditsUnavailable, setCreditsUnavailable] = useState<boolean>(false);
    const [creditsResetAt, setCreditsResetAt] = useState<string | null>(null);
    const [kakaoPayPopUpOn, setKakaoPayPopUpOn] = useState<boolean>(false);
    //선택 필지의 면적·공시지가 (지적도 응답에서 뽑은 값)
    const [selectedParcels, setSelectedParcels] = useState<ParcelInfo[]>([]);
    const [organizationOverview, setOrganizationOverview] = useState<OrganizationOverview | null>(null);

    //로그인 상태 확인
    const checkLoginStatus = useCallback(async () => {
        try {
            const response = await userInfo();
            if (response && response.user_name && response.email) {
                setIsAuthenticated(true);
                setUserName(response.user_name);
                setUserEmail(response.email);
                try {
                    setOrganizationOverview(await getOrganizationOverview());
                } catch (organizationError) {
                    setOrganizationOverview(null);
                    console.error('[ 조합 정보 조회 오류 발생 ] : ', organizationError);
                }
                const credits = await userCredits();
                setDailyCredits(credits.credits_remaining);
                setCreditsResetAt(credits.resets_at);
                setCreditsUnavailable(false);
            } else {
                setIsAuthenticated(false);
                setDailyCredits(null);
            }
        } catch (err: any) {
            if (err.response && err.response.status === 401) {
                setIsAuthenticated(false);
                setUserName('');
                setUserEmail('');
                setDailyCredits(null);
                setCreditsUnavailable(false);
                setOrganizationOverview(null);
            } else {
                setCreditsUnavailable(true);
                console.error("[ 크레딧 조회 오류 발생 ] : ", err);
            }
        }
    }, []);

    //로그인 되어있는지 확인
    useEffect(() => {
        void checkLoginStatus();
    }, [checkLoginStatus]);

    useEffect(() => {
        if (!isAuthenticated) return;

        const refreshCredits = async () => {
            if (document.visibilityState !== 'visible') return;
            try {
                const credits = await userCredits();
                setDailyCredits(credits.credits_remaining);
                setCreditsResetAt(credits.resets_at);
                setCreditsUnavailable(false);
            } catch (err) {
                setCreditsUnavailable(true);
                console.error('[ 크레딧 새로고침 오류 발생 ] : ', err);
            }
        };

        window.addEventListener('focus', refreshCredits);
        document.addEventListener('visibilitychange', refreshCredits);
        return () => {
            window.removeEventListener('focus', refreshCredits);
            document.removeEventListener('visibilitychange', refreshCredits);
        };
    }, [isAuthenticated]);

    //페이지를 열어둔 채 날짜가 바뀌어도 일일 크레딧 잔액을 갱신
    useEffect(() => {
        if (!creditsResetAt) return;

        const delay = Math.max(0, Date.parse(creditsResetAt) - Date.now()) + 1000;
        const timer = window.setTimeout(async () => {
            try {
                const credits = await userCredits();
                setDailyCredits(credits.credits_remaining);
                setCreditsResetAt(credits.resets_at);
                setCreditsUnavailable(false);
            } catch (err) {
                setCreditsUnavailable(true);
                console.error("[ 일일 크레딧 갱신 오류 발생 ] : ", err);
            }
        }, delay);

        return () => window.clearTimeout(timer);
    }, [creditsResetAt]);

    //로그아웃 버튼 클릭시 로그아웃 처리
    const logoutButtonAction = async () => {
        try {
            await userLogout();
            alert("정상적으로 로그아웃 되었습니다.");
            window.location.href = "/";
        } catch (err) {
            console.error("[ logoutButtonAction 오류 발생 ] : ", err);
            alert("로그아웃 중 오류가 발생했습니다. 다시 시도해주세요.");
        }
    }

    //선택 필지 갱신 Handler
    //  같은 필지 목록이면 상태를 그대로 둔다. 매번 새 배열을 넣으면 렌더가 무한히 반복된다
    const handleSelectionChange = useCallback((pnus: string[], parcels: ParcelInfo[]) => {
        setSelectedPnus((prev) => (prev.join(',') === pnus.join(',') ? prev : pnus));
        setSelectedParcels((prev) =>
            prev.map((p) => p.pnu).join(',') === parcels.map((p) => p.pnu).join(',') ? prev : parcels
        );
    }, []);

    const restoreScenarioSelection = useCallback((pnus: string[], parcels: ParcelInfo[]) => {
        setSelectedPnus(pnus);
        setSelectedParcels(parcels);
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
    const handleZoneData = useCallback(async (
        pnus: string[],
        zoning?: string,
        parcels?: ParcelInfo[],
        targetYm?: string,
        householdCount?: number,
    ) => {
        try {
            const response = await getZoneInfo(pnus, {
                parcels: parcels ?? selectedParcels,
                zoning,
                targetYm,
                householdCount,
            });
            if (Number.isInteger(response.credits_remaining)) {
                setDailyCredits(response.credits_remaining);
                setCreditsUnavailable(false);
            } else {
                setCreditsUnavailable(true);
            }
            return response;
        } catch (err){
            if (axios.isAxiosError(err) && err.response?.status === 429) {
                setDailyCredits(0);
            }
            console.log("[ handleZoneData 오류 발생 ] : ", err);
            throw err;
        }
    }, [selectedParcels]);

    //Contribution 데이터 API 호출 Handler
    const handleContributionData = useCallback(async (requestData: any) => {
        try {
            const response = await getContributionInfo(requestData);
            if (Number.isInteger(response.credits_remaining)) {
                setDailyCredits(response.credits_remaining);
                setCreditsUnavailable(false);
            }
            return response;
        } catch (err) {
            console.log("[ handleContributionData 오류 발생 ] : ", err);
            throw err;
        }
    }, []);

    const toggleResetCredit = () => {
        if(kakaoPayPopUpOn === true){
            setKakaoPayPopUpOn(false);
        } else{
            setKakaoPayPopUpOn(true);
        }
    }

    return {
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
        toggleResetCredit,
        kakaoPayPopUpOn,
    };
}
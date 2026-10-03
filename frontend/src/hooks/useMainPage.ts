import { getVWorldCadastral } from '../api/cadastral_api';
import { getZoneInfo, getContributionInfo } from '../api/realestate_api';
import { ParcelInfo } from '../utils/parcel';
import { useCallback, useState, useEffect } from 'react';
import { userLogout, userInfo, userCredits, resetUserCredits } from '../api/user_api';
import axios from 'axios';

//MainPage Hook
export const useMainPage = () => {
    const [isOpen, setIsOpen] = useState<boolean>(true);
    const [isVerified, setIsVerified] = useState<boolean>(false);
    const [selectedPnus, setSelectedPnus] = useState<string[]>([]);

    const [userName, setUserName] = useState<string>('');
    const [userEmail, setUserEmail] = useState<string>('');
    const [dailyCredits, setDailyCredits] = useState<number | null>(null);
    const [creditsUnavailable, setCreditsUnavailable] = useState<boolean>(false);
    const [creditsResetAt, setCreditsResetAt] = useState<string | null>(null);
    const [resettingCredits, setResettingCredits] = useState<boolean>(false);

    //선택 필지의 면적·공시지가 (지적도 응답에서 뽑은 값)
    const [selectedParcels, setSelectedParcels] = useState<ParcelInfo[]>([]);

    //로그인 상태 확인
    const checkLoginStatus = useCallback(async () => {
        try {
            const response = await userInfo();
            if (response && response.user_name && response.email) {
                setUserName(response.user_name);
                setUserEmail(response.email);
                const credits = await userCredits();
                setDailyCredits(credits.credits_remaining);
                setCreditsResetAt(credits.resets_at);
                setCreditsUnavailable(false);
            } else {
                alert("계정 정보에 오류가 생겼습니다. 다시 로그인해주세요.");
                window.location.href = "/login";
            }
        } catch (err: any) {
            if (err.response && err.response.status === 401) {
                alert("로그인이 필요합니다.");
                window.location.href = "/login";
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
            window.location.href = "/login";
        } catch (err) {
            console.error("[ logoutButtonAction 오류 발생 ] : ", err);
            alert("로그아웃 중 오류가 발생했습니다. 다시 시도해주세요.");
        }
    }

    const resetCreditsAction = async () => {
        if (!window.confirm("오늘 사용할 크레딧을 5개로 초기화할까요?")) return;

        setResettingCredits(true);
        try {
            const credits = await resetUserCredits();
            setDailyCredits(credits.credits_remaining);
            setCreditsResetAt(credits.resets_at);
            setCreditsUnavailable(false);
        } catch (err) {
            console.error("[ 크레딧 초기화 오류 발생 ] : ", err);
            alert("크레딧 초기화에 실패했습니다. 잠시 후 다시 시도해주세요.");
        } finally {
            setResettingCredits(false);
        }
    };


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
            return response;
        } catch (err) {
            console.log("[ handleContributionData 오류 발생 ] : ", err);
            throw err;
        }
    }, []);

    return {
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
    };
}
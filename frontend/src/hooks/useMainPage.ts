import { getVWorldCadastral } from '../api/cadastral_api';
import { getZoneInfo, getContributionInfo } from '../api/realestate_api';
import { ParcelInfo } from '../utils/parcel';
import { useCallback, useState, useEffect } from 'react';

//MainPage Hook
export const useMainPage = () => {
    const [isOpen, setIsOpen] = useState<boolean>(true);
    const [isVerified, setIsVerified] = useState<boolean>(false);
    const [selectedPnus, setSelectedPnus] = useState<string[]>([]);

    //선택 필지의 면적·공시지가 (지적도 응답에서 뽑은 값)
    const [selectedParcels, setSelectedParcels] = useState<ParcelInfo[]>([]);
    
    //로그인 되어있는지 확인
    useEffect(() => {
        const token = localStorage.getItem('token');
        if (!token) {
            alert("로그인이 필요합니다.");
            window.location.href = "/login";
        }
    }, []);


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
        handleContributionData
    };
}
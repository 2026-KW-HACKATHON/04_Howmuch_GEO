/// <reference types="vite/client" />

import { useEffect, useState } from 'react';
import { getNews } from '../api/news_api';

//NewsPanel Hook
export const useNewsPanel = () => {

    const handleGetNews = async (query : string) => {
        try {
            const response = await getNews({ query });
            return response
        } catch(err : any) {
            alert("뉴스 로드 과정에서 오류가 발생했습니다. 다시 시도해주세요.");
        }
    }
    
    useEffect(() => {
    }, []);

    return {
        handleGetNews
    };
};
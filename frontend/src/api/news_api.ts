import { api } from './client';

//뉴스 조회 요청 스키마
export interface NewsRequest {
    query: string
}

//뉴스 조회 요청 API HTTP Handler
export async function getNews(newsRequest: NewsRequest): Promise<any> {
    const response = await api.post('/api/v1/news', newsRequest);
    return response.data;
}
import { api } from './client';

//지적도 데이터 API HTTP Handler 
export const getCadastral = async (requestData) => {
    const response = await api.post('/cadastral', requestData);
    return response.data;
};
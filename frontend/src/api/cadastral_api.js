import { api } from './client';

//지적도 Mock 데이터 API HTTP Handler (테스트 용)
export const getMockCadastral = async () => {
    const response = await api.post('/cadastral/mock');
    return response.data;
};

//지적도 데이터 API HTTP Handler 
export const getVWorldCadastral = async (requestData) => {
    const response = await api.post('/cadastral/vworld', requestData);
    return response.data;
};
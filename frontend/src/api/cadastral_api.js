import { api } from './client';

//지적도 데이터 API HTTP Handler 
export const getVWorldCadastral = async (requestData) => {
    const response = await api.post('/cadastral/vworld', requestData);
    return response.data;
};
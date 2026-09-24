import { api } from './client';

//지적도 데이터 API HTTP Handler 
export const getVWorldCadastral = async () => {
  const response = await api.get('/cadastral');
  return response.data;
};
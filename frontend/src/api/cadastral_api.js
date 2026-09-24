import { api } from './client';

//지적도 데이터 API HTTP Handler 
export const getVWorldCadastral = async (geomFilter) => {
  const response = await api.post('/api/cadastral', geomFilter);
  return response.data;
};
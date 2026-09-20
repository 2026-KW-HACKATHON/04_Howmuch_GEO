import { api } from './client';

//AI 모델 예측 API HTTP Handler
export const predictModel = async (requestData) => {
  const response = await api.post('/predict', requestData);
  return response.data;
};
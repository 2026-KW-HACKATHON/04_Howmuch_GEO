import { api } from './client';

//예측 요청 스키마
export interface PredictRequestDto {
    area: number;
    floor: number;
    building_age: number;
    subway_distance: number;
}

//예측 응답 스키마
export interface PredictResponseDto {
    predicted_price: number;
}

//AI 모델 예측 API HTTP Handler
export const predictModel = async (requestData: PredictRequestDto): Promise<PredictResponseDto> => {
  const response = await api.post<PredictResponseDto>('/predict', requestData);
  return response.data;
};
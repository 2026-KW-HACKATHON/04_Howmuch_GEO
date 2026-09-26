import { api } from './client';

//지오메트리 정보 스키마
export interface VWorldGeometry {
    type: string;
    coordinates: number[][][][];
}

//개별 필지 정보 스키마
export interface VWorldFeature {
    type: string;
    geometry: VWorldGeometry;
    properties?: Record<string, any>;
    [key: string]: any;
}

//FeatureCollection 스키마
export interface VWorldFeatureCollection {
    type: string;
    bbox: number[];
    features: VWorldFeature[];
}

//VWorld API 응답 스키마
export interface VWorldCadastralResponse {
    response: {
        service: {
            name: string;
            version: string;
            operation: string;
            time: string;
        };
        status: string;
        record?: {
            total: string;
            current: string;
        };
        page?: {
            total: string;
            current: string;
            size: string;
        };
        result: {
            featureCollection: VWorldFeatureCollection;
        };
    };
}

//백엔드로 보낼 요청 스키마
export interface CadastralRequest {
    geom_filter: string;
}

//지적도 데이터 API HTTP Handler
export const getVWorldCadastral = async (geomFilter: string): Promise<VWorldCadastralResponse> => {
    const response = await api.post<VWorldCadastralResponse>('/api/v1/cadastral', {
        geom_filter: geomFilter,
    });
    return response.data;
};
import { api } from './client';

//ZoneInfo API HTTP Handler
export async function getZoneInfo(pnus: string[]): Promise<any> {
    const response = await api.post('/api/v1/zone', { pnus });
    return response.data;
}

//Contribution 요청 프론트 스키마
export interface ContributionRequest {
    name: string;
    site_area_m2: number;
    member_count: number;
    far_base: number;
    sliders: {
        floor_area_ratio: number;
        member_price_ratio: number;
        other_cost_ratio: number;
        commercial_ratio: number;
        construction_cost_per_pyeong: number;
        general_price_per_m2: number;
        proportional_rate: number;
        [key: string]: number;
    };
    owner: {
        desired_unit: string;
        official_price: number;
    };
}

//getContributionInfo API HTTP Handler
export async function getContributionInfo(requestData: ContributionRequest): Promise<any> {
    const response = await api.post('/api/v1/contribution', requestData);
    return response.data;
}
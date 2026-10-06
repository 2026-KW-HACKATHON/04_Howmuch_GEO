import { api } from './client';
import { ParcelInfo } from '../utils/parcel';

//ZoneInfo API 옵션
//  parcels : 선택 필지의 면적·공시지가. 지적도 응답에서 뽑은 값이라 데이터 API 권한이 없어도 쓸 수 있다
//  targetYm : 공사비·분양가 예측 기준 시점 "YYYY-MM" (착공 예상 연월). 없으면 서버가 현재 연월을 쓴다
//  householdCount : 구역 세대수. 조합원 수 슬라이더 범위를 만드는 데 쓰인다
//  zoning : 사용자가 고른 용도지역. 주면 선택 필지 전체에 적용되어 용적률 범위가 정해진다
export interface ZoneInfoOptions {
    parcels?: ParcelInfo[];
    targetYm?: string;
    householdCount?: number;
    zoning?: string;
}

//ZoneInfo API HTTP Handler
export async function getZoneInfo(pnus: string[], options: ZoneInfoOptions = {}): Promise<any> {
    const response = await api.post('/api/v1/zone', {
        pnus,
        parcels: options.parcels,
        target_ym: options.targetYm,
        household_count: options.householdCount,
        zoning: options.zoning,
    });
    return response.data;
}

//Contribution 요청 프론트 스키마
export interface ContributionRequest {
    credit_token: string;
    name: string;
    site_area_m2: number;
    member_count: number;
    far_base: number;
    household_count?: number;   //조합원 수 슬라이더 범위를 다시 계산하는 데 쓴다
    land_value_total?: number;  //선택 구역 공시지가 총액(만원). 조합원 종전자산 추정에 쓴다
    //노드 슬라이더(임대동 층수)는 문자열 값이라 number 로 좁히면 안 된다.
    //  비례율 슬라이더는 사라졌다 — 사업 수지에서 계산되는 값이라 조절 대상이 아니다
    sliders: {
        floor_area_ratio: number;
        member_price_ratio: number;
        other_cost_ratio: number;
        commercial_ratio: number;
        construction_cost_per_pyeong: number;
        general_price_per_m2: number;
        [key: string]: number | string;
    };
    //평형 구성 (세부 설정). 손대지 않으면 보내지 않고 서버 실측 기본값(59·84·114)을 쓴다.
    //  household_ratio 는 세대수 비율(%)이고, 서버가 면적 몫으로 환산한다
    unit_mix?: { exclusive_area_m2: number; household_ratio: number }[];
    //임대 1세대 전용면적(㎡). 임대 비율은 용적률 완화분에서 법정으로 정해져 입력받지 않는다
    rental_exclusive_area_m2?: number;
    owner: {
        desired_unit: string;
        official_price?: number;   //직접 입력하지 않으면 서버가 공시지가로 추정한다
    };
}

//getContributionInfo API HTTP Handler
export async function getContributionInfo(requestData: ContributionRequest): Promise<any> {
    const response = await api.post('/api/v1/contribution', requestData);
    return response.data;
}
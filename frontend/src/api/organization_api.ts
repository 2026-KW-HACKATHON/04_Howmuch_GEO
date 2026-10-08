import { api } from './client';


//조직 개요 인터페이스
export interface OrganizationOverview {
    account_type: 'personal' | 'leader';
    role: 'personal' | 'leader' | 'member';
    organization_id?: number;
    plan_code?: 'Standard' | 'Pro' | 'Premium';
    plan_name?: string;
    price?: number;
    duration_months?: number;
    invitation_code?: string | null;
    organization_status?: 'pending_payment' | 'active';
    membership_status?: 'pending' | 'active';
    organization_name?: string | null;
    paid_until?: string | null;
    max_members?: number;
    unlimited_credits: boolean;
}

//조직 맴버 인터페이스
export interface OrganizationMember {
    user_id: number;
    user_name: string;
    email: string;
    status: 'pending' | 'active';
    applied_at: string;
}

//조직 Map View 인터페이스
export interface OrganizationMapView {
    latitude: number;
    longitude: number;
    level: number;
}

//조직 시나리오 인터페이스
export interface OrganizationScenario {
    pnus: string[];
    parcels: { pnu: string; area_m2: number; land_price_per_m2: number }[];
    map_view: OrganizationMapView;
    zoning: string;
    target_ym: string;
    sliders: Record<string, number | string>;
    unit_mix: { exclusive_area_m2: number; household_ratio: number }[] | null;
    rental_exclusive_area_m2: number | null;
}

//조직 시나리오 요약 인터페이스
export interface OrganizationScenarioSummary {
    id: number;
    name: string;
    updated_at: string;
}

//조직 시나리오 응답 인터페이스 (기준안 목록 응답용)
export interface OrganizationScenarioResponse {
    scenario: OrganizationScenario | null;
    updated_at: string | null;
}

//저장된 조직 시나리오 응답 인터페이스
export interface OrganizationScenarioSavedResponse extends OrganizationScenarioResponse {
    id: number;
    name: string;
    scenario: OrganizationScenario;
    updated_at: string;
}

//조직 시나리오 응답 인터페이스 (기준안 단일 응답용)
export interface OrganizationScenariosResponse {
    scenarios: OrganizationScenarioSummary[];
}

//가입된 조직 확인 API HTTP handler
export async function getOrganizationOverview(): Promise<OrganizationOverview> {
    const response = await api.get('/api/v1/organization/me');
    return response.data;
}

//조직 가입 API HTTP handler
export async function applyOrganizationCode(invitation_code: string): Promise<void> {
    await api.post('/api/v1/organization/join', { invitation_code });
}

//조직 탈퇴 API HTTP handler
export async function leaveOrganization(): Promise<void> {
    await api.delete('/api/v1/organization/leave');
}

//조직 맴버 확인 API HTTP handler
export async function getOrganizationMembers(): Promise<{ max_members: number; members: OrganizationMember[] }> {
    const response = await api.get('/api/v1/organization/members');
    return response.data;
}

//조직 맴버 승인 API HTTP handler
export async function approveOrganizationMember(userId: number): Promise<void> {
    await api.post(`/api/v1/organization/members/${userId}/approve`);
}

//조직 맴버 삭제 API HTTP handler
export async function removeOrganizationMember(userId: number): Promise<void> {
    await api.delete(`/api/v1/organization/members/${userId}`);
}

//조직 시나리오 전체 조회하기 API HTTP handler
export async function getOrganizationScenarios(): Promise<OrganizationScenariosResponse> {
    const response = await api.get('/api/v1/organization/scenarios');
    return response.data;
}

//단일 시나리오 불러오기 API HTTP handler
export async function getOrganizationScenario(scenarioId: number): Promise<OrganizationScenarioResponse> {
    const response = await api.get(`/api/v1/organization/scenarios/${scenarioId}`);
    return response.data;
}

//단일 시나리오 저장 API HTTP handler
export async function saveOrganizationScenario(
    name: string,
    scenario: OrganizationScenario,
): Promise<OrganizationScenarioSavedResponse> {
    const response = await api.post('/api/v1/organization/scenarios', { name, scenario });
    return response.data;
}

//단일 시나리오 삭제 API HTTP handler
export async function deleteOrganizationScenario(scenarioId: number): Promise<void> {
    await api.delete(`/api/v1/organization/scenarios/${scenarioId}`);
}

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

import { api } from './client';

//일일 크레딧 인터페이스 스키마
export interface DailyCredits {
    credits_remaining: number;
    daily_credits_remaining?: number;
    purchased_credits?: number;
    daily_credit_limit: number;
    resets_at: string;
    unlimited?: boolean;
}

//사용자 회원가입 요청 스키마
export interface SignupRequest {
    email: string;
    user_name: string;
    password: string;
    account_type: 'personal' | 'leader';
    plan_code?: 'Standard' | 'Pro' | 'Premium';
}

//사용자 로그인 요청 스키마
export interface LoginRequest {
    email: string;
    user_name: string;
    password: string;
}

//사용자 회원가입 API HTTP Handler
export async function userSignup(signupRequest: SignupRequest): Promise<any> {
    const response = await api.post('/api/v1/user/signup', signupRequest);
    return response.data;
}

//사용자 로그인 API HTTP Handler
export async function userLogin(loginRequest: LoginRequest): Promise<any> {
    const response = await api.post('/api/v1/user/login', loginRequest);
    return response.data;
}

//사용자 로그아웃 API HTTP Handler
export async function userLogout(): Promise<any> {
    const response = await api.post('/api/v1/user/logout');
    return response.data;
}

//사용자 정보 조회 API HTTP Handler
export async function userInfo(): Promise<any> {
    const response = await api.get('/api/v1/user/info');
    return response.data;
}

//사용자 일일 크레딧 조회 API HTTP Handler
export async function userCredits(): Promise<DailyCredits> {
    const response = await api.get('/api/v1/user/credits');
    return response.data;
}

//사용자 일일 크레딧 초기화 API HTTP Handler
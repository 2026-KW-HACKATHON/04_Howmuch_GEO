import { api } from './client';

//사용자 회원가입 요청 스키마
export interface SignupRequest {
    email: string;
    user_name: string;
    password: string;
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
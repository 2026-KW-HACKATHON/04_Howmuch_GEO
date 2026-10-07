import { api } from './client';

//결제 요청 인터페이스
export interface PaymentRequest {
    item_name: string
    quantity: number
    price: number
    tax_free_amount: number
    plan_code?: 'Standard' | 'Pro' | 'Premium'
}

//결제 응답 인터페이스
export interface PaymentReadyResponse {
    next_redirect_pc_url: string
    tid: string
}

export async function postCreditPurchase(): Promise<PaymentReadyResponse> {
    const response = await api.post('/api/v1/kakao-pay/credits/ready');
    return response.data;
}

//결제 요청 API HTTP Handler
export async function postPayment(paymentRequest: PaymentRequest): Promise<PaymentReadyResponse> {
    const response = await api.post('/api/v1/kakao-pay/ready', paymentRequest);
    return response.data;
}
import { useCallback, useState, useEffect } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { postPayment } from '../api/payment_api';
import type { PaymentRequest } from '../api/payment_api';
import { resetUserCredits, userInfo } from '../api/user_api';

const TEST_PAYMENT = {
    item_name: '',
    quantity: 0,
    price: 0,
    tax_free_amount: 0,
};

interface PaymentLocationState {
    paymentParam?: PaymentRequest;
}

export default function PaymentPage() {
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');
    const { state } = useLocation();
    const [searchParams] = useSearchParams();
    const paymentStatus = searchParams.get('status');
    const paymentParam = (state as PaymentLocationState | null)?.paymentParam ?? TEST_PAYMENT;

    useEffect(() => {
        if(paymentStatus==='success'){
            resetCreditsAction();
        }
    }, [paymentStatus]);


    //로그인 상태 확인
    const checkLoginStatus = useCallback(async () => {
        try {
            const response = await userInfo();
            if (response && response.user_name && response.email) {
                console.log("[ 계정 로그인 되어있음 ]")
            } else {
                alert("계정 정보에 오류가 생겼습니다. 다시 로그인해주세요.");
                window.location.href = "/login";
            }
        } catch (err: any) {
            if (err.response && err.response.status === 401) {
                alert("로그인이 필요합니다.");
                window.location.href = "/login";
            } else {
                console.error("[ 오류 발생 ] : ", err);
            }
        }
    }, []);

    //로그인 되어있는지 확인
    useEffect(() => {
        void checkLoginStatus();
    }, [checkLoginStatus]);

    const startPayment = async () => {
        setIsSubmitting(true);
        setErrorMessage('');

        try {
            const result = await postPayment(paymentParam);
            const redirectUrl = new URL(result.next_redirect_pc_url);

            if (redirectUrl.protocol !== 'https:') {
                throw new Error('안전하지 않은 결제 주소입니다.');
            }

            window.location.assign(redirectUrl.toString());
        } catch (error) {
            console.error('[ KakaoPay ready error ]', error);
            setErrorMessage('결제 요청을 시작하지 못했습니다. 잠시 후 다시 시도해주세요.');
            setIsSubmitting(false);
        }
    };

    const resetCreditsAction = async () => {
            try {
                const credits = await resetUserCredits();
            } catch (err) {
                console.error("[ 크레딧 초기화 오류 발생 ] : ", err);
                alert("크레딧 초기화에 실패했습니다. 잠시 후 다시 시도해주세요.");
            }
        };

    return (
        <main className="min-h-screen bg-[#f5f7f4] text-slate-900">
            <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-5 sm:px-10">
                <Link to="/main" className="text-lg font-bold tracking-tight text-slate-900">
                    얼마 <span className="font-medium text-emerald-700">GEO</span>
                </Link>
                <Link to="/main" className="text-sm font-medium text-slate-600 hover:text-slate-950">
                    서비스로 돌아가기
                </Link>
            </header>

            <div className="mx-auto grid w-full max-w-5xl gap-10 px-5 py-10 sm:px-10 lg:grid-cols-[1fr_360px] lg:gap-16 lg:py-16">
                <section>
                    <p className="text-sm font-semibold uppercase tracking-[0.12em] text-emerald-800">KakaoPay checkout</p>
                    <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">결제 확인</h1>
                    <p className="mt-3 max-w-xl leading-7 text-slate-600">
                        아래 결제 항목을 확인해주세요.
                    </p>
                    <p className="mt-0 max-w-xl leading-7 text-slate-600">
                        결제 버튼을 누르면 카카오페이 화면으로 이동합니다.
                    </p>

                    {paymentStatus === 'success' && (
                        <div role="status" className="mt-8 border-l-4 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                            결제가 승인되었습니다.
                        </div>
                    )}
                    {paymentStatus === 'cancel' && (
                        <div role="status" className="mt-8 border-l-4 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-950">
                            결제가 취소되었습니다.
                        </div>
                    )}
                    {paymentStatus === 'fail' && (
                        <div role="alert" className="mt-8 border-l-4 border-rose-600 bg-rose-50 px-4 py-3 text-sm text-rose-900">
                            결제가 완료되지 않았습니다. 다시 시도해주세요.
                        </div>
                    )}

                    <div className="mt-10 border-y border-slate-200 py-6">
                        <h2 className="text-base font-semibold">주문 상품</h2>
                        <div className="mt-5 flex items-start justify-between gap-6">
                            <div>
                                <p className="font-medium">{paymentParam.item_name}</p>
                                    <p className="mt-1 text-sm text-slate-500">수량 {paymentParam.quantity}</p>
                            </div>
                                <p className="shrink-0 font-semibold">₩{paymentParam.price.toLocaleString('ko-KR')}</p>
                        </div>
                    </div>

                    <div className="mt-6 flex items-start gap-3 text-sm leading-6 text-slate-500">
                    </div>
                </section>

                <aside className="self-start border border-slate-200 bg-white p-6 shadow-sm">
                    <h2 className="text-lg font-semibold">결제 금액</h2>
                    <div className="mt-6 flex items-center justify-between border-b border-slate-100 pb-4 text-sm text-slate-600">
                        <span>상품 금액</span>
                        <span>₩{paymentParam.price.toLocaleString('ko-KR')}</span>
                    </div>
                    <div className="flex items-center justify-between py-5">
                        <span className="font-semibold">총 결제 금액</span>
                        <strong className="text-2xl">₩{paymentParam.price.toLocaleString('ko-KR')}</strong>
                    </div>
                    {errorMessage && <p role="alert" className="mb-4 text-sm text-rose-700">{errorMessage}</p>}
                    <button
                        type="button"
                        onClick={startPayment}
                        disabled={isSubmitting}
                        className="flex min-h-12 w-full items-center justify-center gap-2 bg-[#ffeb00] px-4 font-semibold text-slate-950 transition hover:bg-[#f5df00] disabled:cursor-wait disabled:opacity-60"
                    >
                        {isSubmitting ? '결제 연결 중...' : '카카오페이로 결제'}
                    </button>
                    <p className="mt-3 text-center text-xs leading-5 text-slate-500">
                        결제 버튼을 누르면 카카오페이 결제 화면으로 이동합니다.
                    </p>
                </aside>
            </div>
        </main>
    );
}

import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { postCreditPurchase } from '../api/payment_api';

export default function CreditPurchasePage() {
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');
    const [searchParams] = useSearchParams();
    const paymentStatus = searchParams.get('status');

    const startPayment = async () => {
        setIsSubmitting(true);
        setErrorMessage('');
        try {
            const result = await postCreditPurchase();
            const redirectUrl = new URL(result.next_redirect_pc_url);
            if (redirectUrl.protocol !== 'https:') {
                throw new Error('안전하지 않은 결제 주소입니다.');
            }
            window.location.assign(redirectUrl.toString());
        } catch (error) {
            console.error('[ Credit purchase ready error ]', error);
            setErrorMessage('결제 요청을 시작하지 못했습니다. 잠시 후 다시 시도해주세요.');
            setIsSubmitting(false);
        }
    };

    return (
        <main className="min-h-screen bg-[#f4f7f4] text-slate-900">
            <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-5 sm:px-10">
                <Link to="/main" className="text-lg font-bold tracking-tight">얼마 <span className="font-medium text-emerald-700">GEO</span></Link>
                <Link to="/main" className="text-sm font-medium text-slate-600 hover:text-slate-950">메인으로</Link>
            </header>

            <div className="mx-auto grid w-full max-w-4xl gap-10 px-5 py-10 sm:px-10 lg:grid-cols-[1fr_340px] lg:py-16">
                <section>
                    <p className="text-sm font-semibold uppercase tracking-[0.12em] text-emerald-800">Credit top-up</p>
                    <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">크레딧 구매</h1>
                    <p className="mt-3 max-w-xl leading-7 text-slate-600">결제가 KakaoPay에서 승인되면 구매 크레딧 5회가 계정에 누적됩니다. 일일 기본 크레딧을 먼저 사용하고 이후 구매분이 사용됩니다.</p>

                    {paymentStatus === 'success' && (
                        <div role="status" className="mt-8 border-l-4 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                            결제가 승인되어 크레딧 5회가 추가되었습니다. <Link to="/main" className="ml-2 font-semibold underline">서비스로 돌아가기</Link>
                        </div>
                    )}
                    {paymentStatus === 'cancel' && (
                        <div role="status" className="mt-8 border-l-4 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-950">결제가 취소되었습니다. 크레딧은 추가되지 않았습니다.</div>
                    )}
                    {paymentStatus === 'fail' && (
                        <div role="alert" className="mt-8 border-l-4 border-rose-600 bg-rose-50 px-4 py-3 text-sm text-rose-900">결제가 승인되지 않았습니다. 크레딧은 추가되지 않았습니다.</div>
                    )}

                    <div className="mt-10 border-y border-slate-200 py-6">
                        <h2 className="text-base font-semibold">상품 안내</h2>
                        <p className="mt-3 text-lg font-semibold">개인 크레딧 5회권</p>
                        <p className="mt-1 text-sm text-slate-600">구매 크레딧은 일일 기본 크레딧과 별도로 누적됩니다.</p>
                    </div>
                </section>

                <aside className="self-start border border-slate-200 bg-white p-6 shadow-sm">
                    <h2 className="text-lg font-semibold">결제 금액</h2>
                    <div className="mt-6 flex items-center justify-between border-b border-slate-100 pb-4 text-sm text-slate-600">
                        <span>5회권</span>
                        <span>₩500</span>
                    </div>
                    <div className="flex items-center justify-between py-5">
                        <span className="font-semibold">총 결제 금액</span>
                        <strong className="text-2xl">₩500</strong>
                    </div>
                    {errorMessage && <p role="alert" className="mb-4 text-sm text-rose-700">{errorMessage}</p>}
                    <button type="button" onClick={startPayment} disabled={isSubmitting || paymentStatus === 'success'} className="flex min-h-12 w-full items-center justify-center bg-[#ffeb00] px-4 font-semibold text-slate-950 transition hover:bg-[#f5df00] disabled:cursor-wait disabled:opacity-60">
                        {isSubmitting ? '결제 연결 중...' : '카카오페이로 구매'}
                    </button>
                    <p className="mt-3 text-center text-xs leading-5 text-slate-500">카카오페이 승인 완료 후에만 크레딧이 지급됩니다.</p>
                </aside>
            </div>
        </main>
    );
}

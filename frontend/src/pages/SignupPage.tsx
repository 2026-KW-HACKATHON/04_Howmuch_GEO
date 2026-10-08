/// <reference types="vite/client" />

import ReCAPTCHA from 'react-google-recaptcha';
import { useSignupPage } from '../hooks/useSignupPage';
import { Link } from 'react-router-dom';

export default function SignupPage() {

    //SignupPage Hook 사용
    const {
        handleCaptchaChange,
        setEmail,
        setUserName,
        setPassword,
        setPasswordCheck,
        accountType,
        setAccountType,
        planCode,
        setPlanCode,
        signupButtonAction,
        isFormValid,
        isPasswordValid,
        signupAttempted
    } = useSignupPage();

    return (
        <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-slate-50 via-white to-blue-50 px-4 py-10">
            <div aria-hidden="true" className="pointer-events-none absolute -left-32 -top-32 h-80 w-80 rounded-full bg-blue-100/60 blur-3xl" />
            <div aria-hidden="true" className="pointer-events-none absolute -bottom-40 -right-24 h-96 w-96 rounded-full bg-emerald-100/50 blur-3xl" />

            <main className="relative w-full max-w-3xl">
                <section className="rounded-3xl border border-white/80 bg-white/90 p-6 shadow-xl shadow-slate-200/70 backdrop-blur sm:p-9">
                    <Link to="/main" className="flex w-full items-center justify-center">
                        <img
                            src="/banner.png"
                            alt="얼마 GEO 배너"
                            className="h-32 w-auto object-contain sm:h-36"
                        />
                    </Link>
                    <div className="mb-8 text-center">
                        <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-slate-900">회원가입</h1>
                        <p className="mt-2 text-sm leading-6 text-slate-500">얼마 GEO와 함께 개발 분담금 조회를 시작해 보세요.</p>
                    </div>

                    <form className="mx-auto flex w-full max-w-2xl flex-col items-center">
                        <fieldset className="mb-5 w-full max-w-sm">
                            <legend className="mb-2 text-sm font-semibold text-slate-700">계정 유형</legend>
                            <div className="grid grid-cols-2 gap-2 rounded-2xl bg-slate-100 p-1">
                                <button type="button" onClick={() => setAccountType('personal')} aria-pressed={accountType === 'personal'} className={`rounded-xl border px-3 py-2.5 text-sm font-semibold transition-colors duration-200 ${accountType === 'personal' ? 'border-white bg-white text-blue-700 shadow-sm' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
                                    개인
                                </button>
                                <button type="button" onClick={() => setAccountType('leader')} aria-pressed={accountType === 'leader'} className={`rounded-xl border px-3 py-2.5 text-sm font-semibold transition-colors duration-200 ${accountType === 'leader' ? 'border-white bg-white text-blue-700 shadow-sm' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
                                    조합장
                                </button>
                            </div>
                        </fieldset>
                        <div className="w-full max-w-sm">
                            <input
                                type="email"
                                placeholder="이메일"
                                onChange={(e) => setEmail(e.target.value)}
                                className="mb-4 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-100"
                            />
                            <input
                                type="text"
                                placeholder="아이디"
                                onChange={(e) => setUserName(e.target.value)}
                                className="mb-4 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-100"
                            />
                            <input
                                type="password"
                                placeholder="비밀번호"
                                onChange={(e) => setPassword(e.target.value)}
                                className={`mb-4 w-full rounded-xl border bg-slate-50/70 px-4 py-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:bg-white focus:ring-4 ${
                                    !isPasswordValid && signupAttempted ? 'border-red-400 focus:border-red-400 focus:ring-red-100' : 'border-slate-200 focus:border-blue-500 focus:ring-blue-100'}`}
                            />
                            <input
                                type="password"
                                placeholder="비밀번호 확인"
                                onChange={(e) => setPasswordCheck(e.target.value)}
                                className={`w-full rounded-xl border bg-slate-50/70 px-4 py-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:bg-white focus:ring-4 ${
                                    !isPasswordValid && signupAttempted ? 'border-red-400 focus:border-red-400 focus:ring-red-100' : 'border-slate-200 focus:border-blue-500 focus:ring-blue-100'}`}
                            />
                        </div>
                        <div
                            aria-hidden={accountType !== 'leader'}
                            className={`grid w-full transition-[grid-template-rows,opacity,margin] duration-300 ease-in-out motion-reduce:transition-none ${
                                accountType === 'leader'
                                    ? 'mb-6 mt-5 grid-rows-[1fr] opacity-100'
                                    : 'mb-0 mt-0 grid-rows-[0fr] opacity-0'
                            }`}
                        >
                            <div className="min-h-0 overflow-hidden">
                                <fieldset disabled={accountType !== 'leader'} className="w-full">
                                    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                                        {[
                                            { code: 'Standard', detail: '최대 100명 · 1개월 · ₩10,000' },
                                            { code: 'Pro', detail: '최대 1000명 · 6개월 · ₩50,000' },
                                            { code: 'Premium', detail: '최대 2000명 · 12개월 · ₩100,000' },
                                        ].map((plan) => {
                                            const isSelected = planCode === plan.code;
                                            return (
                                                <button
                                                    key={plan.code}
                                                    type="button"
                                                    onClick={() => setPlanCode(plan.code as 'Standard' | 'Pro' | 'Premium')}
                                                    aria-pressed={isSelected}
                                                    className={`flex flex-col justify-between rounded-2xl border-2 p-4 text-left transition-all duration-200 ${
                                                        isSelected
                                                            ? 'border-blue-600 bg-blue-50/60 shadow-md ring-2 ring-blue-600/15'
                                                            : 'border-slate-200 bg-white hover:border-blue-200 hover:shadow-sm'
                                                    }`}
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <span className={`text-sm font-bold ${isSelected ? 'text-blue-700' : 'text-slate-900'}`}>
                                                            {plan.code}
                                                        </span>
                                                        <div
                                                            className={`flex h-5 w-5 items-center justify-center rounded-full border ${
                                                                isSelected ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-300 bg-white'
                                                            }`}
                                                        >
                                                            {isSelected && (
                                                                <svg className="h-3 w-3 stroke-current" fill="none" viewBox="0 0 24 24" strokeWidth="3">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                                                </svg>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <div className="mt-4 border-t border-slate-100 pt-3">
                                                        <span className={`text-xs leading-relaxed ${isSelected ? 'font-medium text-blue-900' : 'text-slate-600'}`}>
                                                            {plan.detail}
                                                        </span>
                                                    </div>
                                                </button>
                                            );
                                        })}
                                    </div>
                                </fieldset>
                            </div>
                        </div>
                        <div className="mb-5 w-full overflow-x-auto">
                            <div className="mt-5 flex justify-center">
                                <ReCAPTCHA
                                    sitekey={import.meta.env.VITE_GOOGLE_RECAPTCHA_API}
                                    onChange={handleCaptchaChange}
                                />
                            </div>
                        </div>
                        <button
                            type="submit"
                            className={`w-full max-w-sm rounded-xl px-4 py-3.5 text-sm font-bold text-white shadow-sm transition focus:outline-none focus:ring-4 focus:ring-blue-200 ${
                                isFormValid ? 'bg-blue-600 hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-lg hover:shadow-blue-600/20' : 'cursor-not-allowed bg-slate-300'
                            }`}
                            disabled={!isFormValid}
                            onClick={signupButtonAction}
                        >
                            회원가입
                        </button>
                    </form>
                </section>

                <div className="mt-6 text-center">
                    <p className="mb-3 text-sm text-slate-500">이미 계정이 있으신가요?</p>
                    <div className="flex flex-wrap items-center justify-center gap-2">
                        <button
                            type="button"
                            onClick={() => window.location.href = '/login'}
                            className="rounded-xl border border-slate-200 bg-white/80 px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-100"
                        >
                            로그인
                        </button>
                        <Link
                            to="/main"
                            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-4 py-2.5 text-sm font-semibold text-slate-500 shadow-sm transition hover:border-blue-200 hover:bg-blue-50 hover:text-slate-800 focus:outline-none focus:ring-4 focus:ring-blue-100"
                        >
                            돌아가기
                        </Link>
                    </div>
                </div>
            </main>
        </div>
    );
}
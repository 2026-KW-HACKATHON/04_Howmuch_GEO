/// <reference types="vite/client" />

import ReCAPTCHA from 'react-google-recaptcha';
import { useSignupPage } from '../hooks/useSignupPage';

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
        <div className="flex flex-col items-center justify-center h-screen bg-gray-100">
            <h1 className="text-2xl font-bold mb-4">회원가입</h1>
            <p className="text-gray-600 mb-8">서비스를 이용하기 위해서는 회원가입이 필요합니다.</p>
            <form className="flex w-[min(92vw,900px)] flex-col items-center">
                <fieldset className="mb-4 w-full max-w-sm">
                    <legend className="mb-2 text-sm font-semibold text-gray-700">계정 유형</legend>
                    <div className="grid grid-cols-2 gap-2">
                        <button type="button" onClick={() => setAccountType('personal')} aria-pressed={accountType === 'personal'} className={`rounded-lg border px-3 py-2 text-sm transition-colors duration-300 ${accountType === 'personal' ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-gray-300 bg-white text-gray-600'}`}>
                            개인
                        </button>
                        <button type="button" onClick={() => setAccountType('leader')} aria-pressed={accountType === 'leader'} className={`rounded-lg border px-3 py-2 text-sm transition-colors duration-300 ${accountType === 'leader' ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-gray-300 bg-white text-gray-600'}`}>
                            조합장
                        </button>
                    </div>
                </fieldset>
                <input
                    type="email"
                    placeholder="이메일"
                    onChange={(e)=>setEmail(e.target.value)}
                    className="mb-4 w-full max-w-sm rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none"
                />
                <input
                    type="text"
                    placeholder="아이디"
                    onChange={(e)=>setUserName(e.target.value)}
                    className="mb-4 w-full max-w-sm rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none"
                />
                <input
                    type="password"
                    placeholder="비밀번호"
                    onChange={(e)=>setPassword(e.target.value)}
                    className={`mb-4 w-full max-w-sm rounded-lg border border-gray-300 px-4 py-2 ${
                        !isPasswordValid && signupAttempted ? 'border-red-500' : 'focus:border-blue-500'} focus:outline-none`}
                />
                <input
                    type="password"
                    placeholder="비밀번호 확인"
                    onChange={(e)=>setPasswordCheck(e.target.value)}
                    className={`mb-4 w-full max-w-sm rounded-lg border border-gray-300 px-4 py-2 ${
                        !isPasswordValid && signupAttempted ? 'border-red-500' : 'focus:border-blue-500'} focus:outline-none`}
                />
                <div
                    aria-hidden={accountType !== 'leader'}
                    className={`grid w-full transition-[grid-template-rows,opacity,margin] duration-300 ease-in-out motion-reduce:transition-none ${
                        accountType === 'leader'
                            ? 'mb-6 grid-rows-[1fr] opacity-100'
                            : 'mb-0 grid-rows-[0fr] opacity-0'
                    }`}
                >
                    <div className="min-h-0 overflow-hidden">
                    <fieldset disabled={accountType !== 'leader'} className="w-full">
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 ">
                            {[
                                { code: 'Standard', detail: '최대 10명 · 1개월 · ₩10,000' },
                                { code: 'Pro', detail: '최대 30명 · 6개월 · ₩50,000' },
                                { code: 'Premium', detail: '최대 50명 · 12개월 · ₩100,000' },
                            ].map((plan) => {
                                const isSelected = planCode === plan.code;
                                return (
                                    <button
                                        key={plan.code}
                                        type="button"
                                        onClick={() => setPlanCode(plan.code as 'Standard' | 'Pro' | 'Premium')}
                                        aria-pressed={isSelected}
                                        className={`flex flex-col justify-between rounded-xl border-2 p-5 text-left transition-all duration-200 ${
                                            isSelected
                                                ? 'border-blue-600 bg-blue-50/50 shadow-md ring-2 ring-blue-600/20'
                                                : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
                                        }`}
                                    >
                                        {/* 상단: 플랜 이름 및 체크 표시 */}
                                        <div className="flex items-center justify-between">
                                            <span className={`text-sm font-bold ${isSelected ? 'text-blue-700' : 'text-gray-900'}`}>
                                                {plan.code}
                                            </span>
                                            <div
                                                className={`flex h-5 w-5 items-center justify-center rounded-full border ${
                                                    isSelected ? 'border-blue-600 bg-blue-600 text-white' : 'border-gray-300 bg-white'
                                                }`}
                                            >
                                                {isSelected && (
                                                    <svg className="h-3 w-3 stroke-current" fill="none" viewBox="0 0 24 24" strokeWidth="3">
                                                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                                    </svg>
                                                )}
                                            </div>
                                        </div>

                                        {/* 하단: detail 텍스트 */}
                                        <div className="mt-4 pt-3 border-t border-gray-100">
                                            <span className={`text-xs leading-relaxed ${isSelected ? 'font-medium text-blue-900' : 'text-gray-600'}`}>
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
                <ReCAPTCHA
                    sitekey= {import.meta.env.VITE_GOOGLE_RECAPTCHA_API}
                    onChange={handleCaptchaChange}
                />
                <button
                    type="submit"
                    className={`mb-4 w-full max-w-sm rounded-lg ${
                        isFormValid ? 'bg-blue-600 hover:bg-blue-700 focus:outline-none' : 'bg-gray-400 hover:bg-gray-400 focus:outline-none'
                    } px-4 py-2 text-white font-semibold transition`}
                    disabled={!isFormValid}
                    onClick={signupButtonAction}
                >
                    회원가입
                </button>
            </form>
            <p className="text-gray-600 mb-4">이미 계정이 있으신가요?</p>
            <button
                type="button"
                onClick={() => window.location.href = '/login'}
                className="rounded-lg bg-blue-600 px-4 py-2 text-white font-semibold transition hover:bg-blue-700"
            >
                로그인
            </button>
        </div>
    )
}
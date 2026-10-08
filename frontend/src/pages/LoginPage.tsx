/// <reference types="vite/client" />

import ReCAPTCHA from 'react-google-recaptcha';
import { useLoginPage } from '../hooks/useLoginPage';
import { Link } from 'react-router-dom';

export default function LoginPage() {

    //LoginPage Hook 사용
    const { 
        loginButtonAction,
        handleCaptchaChange,
        setUserName,
        setPassword,
        isFormValid,
        loginAttempted
    } = useLoginPage();

    return (
        <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-slate-50 via-white to-blue-50 px-4 py-10">
            <div aria-hidden="true" className="pointer-events-none absolute -left-32 -top-32 h-80 w-80 rounded-full bg-blue-100/60 blur-3xl" />
            <div aria-hidden="true" className="pointer-events-none absolute -bottom-40 -right-24 h-96 w-96 rounded-full bg-emerald-100/50 blur-3xl" />

            <main className="relative w-full max-w-md">

                <section className="rounded-3xl border border-white/80 bg-white/90 p-6 shadow-xl shadow-slate-200/70 backdrop-blur sm:p-9">
                    <Link to="/main" className="flex w-full items-center justify-center">
                        <img
                            src="/banner.png"
                            alt="얼마 GEO 배너"
                            className="h-32 w-auto object-contain sm:h-36"
                        />
                    </Link>
                    <div className="mb-8 text-center">
                        <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-slate-900">로그인</h1>
                        <p className="mt-2 text-sm leading-6 text-slate-500">계정에 로그인하고 개발 분담금을 확인해 보세요.</p>
                    </div>

                    <form className="flex w-full flex-col items-center">
                        <input
                            type="text"
                            autoComplete="username"
                            placeholder="아이디 또는 이메일"
                            onChange={(e) => setUserName(e.target.value)}
                            className={`mb-4 w-full rounded-xl border bg-slate-50/70 px-4 py-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:bg-white focus:ring-4 ${
                                loginAttempted ? 'border-red-400 focus:border-red-400 focus:ring-red-100' : 'border-slate-200 focus:border-blue-500 focus:ring-blue-100'}`}
                        />
                        <input
                            type="password"
                            placeholder="비밀번호"
                            onChange={(e) => setPassword(e.target.value)}
                            className={`mb-5 w-full rounded-xl border bg-slate-50/70 px-4 py-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:bg-white focus:ring-4 ${
                                loginAttempted ? 'border-red-400 focus:border-red-400 focus:ring-red-100' : 'border-slate-200 focus:border-blue-500 focus:ring-blue-100'}`}
                        />
                        <div className="mb-5 w-full overflow-x-auto">
                            <div className="flex justify-center">
                                <ReCAPTCHA
                                    sitekey={import.meta.env.VITE_GOOGLE_RECAPTCHA_API}
                                    onChange={handleCaptchaChange}
                                />
                            </div>
                        </div>
                        <button
                            type="submit"
                            disabled={!isFormValid}
                            onClick={loginButtonAction}
                            className={`w-full rounded-xl px-4 py-3.5 text-sm font-bold text-white shadow-sm transition focus:outline-none focus:ring-4 focus:ring-blue-200 ${
                                isFormValid ? 'bg-blue-600 hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-lg hover:shadow-blue-600/20' : 'cursor-not-allowed bg-slate-300'
                            }`}
                        >
                            로그인
                        </button>
                    </form>
                </section>

                <div className="mt-6 text-center">
                    <p className="mb-3 text-sm text-slate-500">아직 계정이 없으신가요?</p>
                    <div className="flex flex-wrap items-center justify-center gap-2">
                        <button
                            type="button"
                            onClick={() => window.location.href = '/signup'}
                            className="rounded-xl border border-slate-200 bg-white/80 px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-100"
                        >
                            회원가입
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
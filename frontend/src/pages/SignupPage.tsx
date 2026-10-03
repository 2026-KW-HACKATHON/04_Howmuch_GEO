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
        signupButtonAction,
        isFormValid,
        isPasswordValid
    } = useSignupPage();

    return (
        <div className="flex flex-col items-center justify-center h-screen bg-gray-100">
            <h1 className="text-2xl font-bold mb-4">회원가입</h1>
            <p className="text-gray-600 mb-8">서비스를 이용하기 위해서는 회원가입이 필요합니다.</p>
            <form className="flex flex-col items-center w-80">
                <input
                    type="email"
                    placeholder="이메일"
                    onChange={(e)=>setEmail(e.target.value)}
                    className="mb-4 w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none"
                />
                <input
                    type="text"
                    placeholder="아이디"
                    onChange={(e)=>setUserName(e.target.value)}
                    className="mb-4 w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none"
                />
                <input
                    type="password"
                    placeholder="비밀번호"
                    onChange={(e)=>setPassword(e.target.value)}
                    className={`mb-4 w-full rounded-lg border border-gray-300 px-4 py-2 ${
                        !isPasswordValid ? 'border-red-500' : 'focus:border-blue-500'} focus:outline-none`}
                />
                <input
                    type="password"
                    placeholder="비밀번호 확인"
                    onChange={(e)=>setPasswordCheck(e.target.value)}
                    className={`mb-4 w-full rounded-lg border border-gray-300 px-4 py-2 ${
                        !isPasswordValid ? 'border-red-500' : 'focus:border-blue-500'} focus:outline-none`}
                />
                <ReCAPTCHA
                    sitekey= {import.meta.env.VITE_GOOGLE_RECAPTCHA_API}
                    onChange={handleCaptchaChange}
                />
                <button
                    type="submit"
                    className={`mb-4 w-full rounded-lg ${
                        isFormValid ? 'bg-blue-600' : 'bg-gray-400'
                    } px-4 py-2 text-white font-semibold transition hover:bg-blue-700 focus:outline-none`}
                    disabled={!isFormValid}
                    onClick={signupButtonAction}
                >
                    회원가입
                </button>
            </form>
            <p className="text-gray-600 mb-4">이미 계정이 있으신가요?</p>
            <button
                type="button"
                onClick={() => window.location.href = '/signup'}
                className="rounded-lg bg-blue-600 px-4 py-2 text-white font-semibold transition hover:bg-blue-700"
            >
                로그인
            </button>
        </div>
    )
}
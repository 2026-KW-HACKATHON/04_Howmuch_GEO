import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { userLogin, LoginRequest } from '../api/user_api';

export const useLoginPage = () => {
    const [isVerified, setIsVerified] = useState<boolean>(false);
    const [userName, setUserName] = useState<string>('');
    const [password, setPassword] = useState<string>('');
    const [loginAttempted, setLoginAttempted] = useState<boolean>(false);

    const isFormValid = isVerified && userName.trim() !== '' && password.trim() !== '';

    const navigate = useNavigate();

    //ReCaptcha Handler
    const handleCaptchaChange = (token: string | null) => {
        if (token) {
            setIsVerified(true);
        }
    };

    const loginButtonAction = async (e: React.FormEvent<HTMLButtonElement>) => {
        try {

            e.preventDefault();

            const userData = {
                user_name: userName,
                password: password
            }

            const response = await userLogin(userData as LoginRequest);

            alert("로그인에 성공했습니다.");
            navigate("/main");

        } catch(err : any) {
            setLoginAttempted(true);
            alert("로그인 과정에서 오류가 발생했습니다. 다시 시도해주세요.");
        }
    }


    return {
        loginButtonAction,
        handleCaptchaChange,
        setUserName,
        setPassword,
        isFormValid,
        loginAttempted
    };
}
import { useState } from 'react';
import { userSignup } from '../api/user_api'
import { useNavigate } from 'react-router-dom';

export const useSignupPage = () => {

    const [isVerified, setIsVerified] = useState<boolean>(false);
    const [email, setEmail] = useState<string>('');
    const [userName, setUserName] = useState<string>('');
    const [password, setPassword] = useState<string>('');
    const [passwordCheck, setPasswordCheck] = useState<string>('');
    const [signupAttempted, setSignupAttempted] = useState<boolean>(false);
    
    const isPasswordValid = password.trim() !== '' && passwordCheck.trim() !== '' && passwordCheck === password;
    const isFormValid = isVerified && email.trim() !== '' && userName.trim() !== '' && isPasswordValid;

    const navigate = useNavigate();
    
    //ReCaptcha Handler
    const handleCaptchaChange = (token: string | null) => {
        if (token) {
            setIsVerified(true);
        }
    };

    const signupButtonAction = async (e: React.FormEvent<HTMLButtonElement>) => {
        try {

            setSignupAttempted(true);

            e.preventDefault();

            const userData = {
                email: email,
                user_name: userName,
                password: password
            }

            const response = await userSignup(userData);

            alert("회원가입에 성공했습니다. 다시 로그인해주세요.");
            navigate("/login");

        } catch(err : any) {
            if(err && err.response.status === 409) {
                alert("이미 존재하는 이메일 혹은 아이디입니다.");
                return;
            } else {
                alert("회원가입 과정에서 오류가 발생했습니다. 다시 시도해주세요.");
            }
        }
    }



    

    return {
        handleCaptchaChange,
        setEmail,
        setUserName,
        setPassword,
        setPasswordCheck,
        signupButtonAction,
        isFormValid,
        isPasswordValid,
        signupAttempted
    };
}
import React, { useState } from 'react';
import KakaoMap from "./components/KakaoMap"
import SideBar from './components/SideBar';

function App() {
    const [isOpen, setIsOpen] = useState(true);

    //사이드바 토글시 isOpen 값 전환
    const toggleSidebar = () => {
        setIsOpen(!isOpen);
    };

    return (
        <div className="relative w-screen h-screen overflow-hidden">
            
            {/* Kakao 지도 영역 */}
            <main className="absolute inset-0 w-full h-full">
                <KakaoMap />
            </main>

            {/* 사이드바 영역 */}
            <SideBar isOpen={isOpen} onToggleSidebar={toggleSidebar} />
        </div>
    );
}

export default App
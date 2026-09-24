import React, { ReactNode } from 'react'

interface SideBarProps {
    isOpen: boolean;
    onToggleSidebar: () => void;
    children: ReactNode;
}

//SideBar 컴포넌트
const SideBar: React.FC<SideBarProps> = ({ isOpen, onToggleSidebar, children }) => {
    return (
        <div className="absolute top-0 left-0 h-screen z-20 flex pointer-events-none">
            
            {/* 사이드바 본체 */}
            <aside
                className={`min-w-0 h-full bg-slate-900 text-white flex flex-col transition-all duration-300 shadow-2xl pointer-events-auto overflow-hidden ${
                    isOpen ? 'w-96 p-4' : 'w-0 p-0'
                }`}
            >

                {/* 사이드바 제목 영역 */}
                <div className="text-xl font-bold mb-8 px-2 whitespace-nowrap">
                    어디지오 Geo
                </div>

                {/* 자식 컴포넌트 */}
                <div className="flex flex-col gap-2 overflow-y-auto flex-1">
                    {children}
                </div>
            </aside>

            {/* 사이드바 토글 버튼 */}
            <div className="flex items-start pt-4 pointer-events-auto">
                <button
                    onClick={onToggleSidebar}
                    className="bg-slate-800 text-white p-4 rounded-r-md shadow-lg hover:bg-slate-700 transition"
                >
                    {isOpen ? '◀' : '▶'}
                </button>
            </div>
        </div>
    );
};

export default SideBar;
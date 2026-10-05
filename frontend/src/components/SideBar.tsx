import React, { ReactNode } from 'react';

//SideBar Props
interface SideBarProps {
    isOpen: boolean;
    onToggleSidebar: () => void;
    activePanel: 'news' | 'prediction';
    onPanelChange: (panel: 'news' | 'prediction') => void;
    children: ReactNode;
}

//SideBar 컴포넌트
const SideBar: React.FC<SideBarProps> = ({ isOpen, onToggleSidebar, activePanel, onPanelChange, children }) => {
    return (
        <div className="absolute top-0 left-0 h-screen z-20 flex pointer-events-none">
            
            {/* 사이드바 본체 */}
            <aside
                className={`min-w-0 h-full bg-white text-slate-800 flex flex-col transition-all duration-300 shadow-2xl border-r border-slate-200 pointer-events-auto overflow-hidden ${
                    isOpen ? 'w-170 p-5' : 'w-0 p-0 border-r-0'
                }`}
            >

                {/* 사이드바 제목 영역 */}
                <div className="text-xl font-extrabold mb-6 px-2 whitespace-nowrap text-slate-900 flex items-center gap-2">
                    <span>얼마 Geo</span>
                </div>

                <div role="tablist" aria-label="사이드바 패널 선택" className="mb-4 grid grid-cols-2 rounded-lg bg-slate-100 p-1">
                    <button
                        type="button"
                        role="tab"
                        aria-selected={activePanel === 'prediction'}
                        onClick={() => onPanelChange('prediction')}
                        className={`rounded-md px-3 py-2 text-sm font-semibold transition ${activePanel === 'prediction' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
                    >
                        예측 패널
                    </button>
                    <button
                        type="button"
                        role="tab"
                        aria-selected={activePanel === 'news'}
                        onClick={() => onPanelChange('news')}
                        className={`rounded-md px-3 py-2 text-sm font-semibold transition ${activePanel === 'news' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
                    >
                        뉴스 패널
                    </button>
                </div>

                {/* 자식 컴포넌트 */}
                <div className="flex flex-col gap-2 overflow-y-auto flex-1 custom-scrollbar">
                    {children}
                </div>

                {/* 사이드바 하단 Copyright 영역 */}
                <div className="mt-4 pt-4 border-t border-slate-100 px-2 text-center whitespace-nowrap">
                    <p className="text-xs text-slate-400 font-medium">
                        Copyright © 2026 얼마 Geo. All rights reserved.
                    </p>
                </div>
            </aside>

            {/* 사이드바 토글 버튼 */}
            <div className="flex items-start pt-4 pointer-events-auto">
                <button
                    type="button"
                    onClick={onToggleSidebar}
                    className="bg-white/90 backdrop-blur-md text-slate-700 p-3 rounded-r-xl shadow-md border-y border-r border-slate-200 hover:bg-slate-50 hover:text-slate-900 transition"
                >
                    {isOpen ? '◀' : '▶'}
                </button>
            </div>
        </div>
    );
};

export default SideBar;
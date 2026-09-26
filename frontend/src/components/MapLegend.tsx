import React, { useState } from 'react';

//지도 범례 컴포넌트
const MapLegend: React.FC = () => {

    //열리고 닫힘 상태 useState
    const [isOpen, setIsOpen] = useState<boolean>(true);

    //범례 항목 데이터 배열
    const legendItems = [
        { label: '제1종전용주거지역', color: 'bg-[#FFF9C4]' },
        { label: '제2종전용주거지역', color: 'bg-[#FFEE58]' },
        { label: '제1종일반주거지역', color: 'bg-[#FFE082]' },
        { label: '제2종일반주거지역', color: 'bg-[#FFB74D]' },
        { label: '제3종일반주거지역', color: 'bg-[#FF9800]' },
        { label: '준주거지역', color: 'bg-[#EF5350]' },
    ];

    return (
        <div className="absolute bottom-6 right-6 z-10 bg-white/95 backdrop-blur-md rounded-xl shadow-xl border border-gray-200 text-xs overflow-hidden transition-all duration-300">
            
            {/* 제목 및 토글 버튼 */}
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="w-full font-bold text-gray-800 px-3 py-2.5 flex items-center justify-between gap-4 focus:outline-none hover:bg-gray-50/50 transition-colors"
            >
                <span>🏠 주거지역 범례</span>
                <span className={`transform transition-transform duration-300 text-gray-500 ${isOpen ? 'rotate-0' : 'rotate-180'}`}>
                    ▼
                </span>
            </button>

            {/* 접히고 펴지는 영역 */}
            <div
                className={`transition-all duration-300 ease-in-out ${
                    isOpen ? 'max-h-48 opacity-100 pb-3 pt-1 border-t border-gray-100' : 'max-h-0 opacity-0 pb-0 pt-0 border-t-0'
                }`}
            >
                <div className="px-3 flex flex-col gap-1.5">
                    {legendItems.map((item, index) => (
                        <div key={index} className="flex items-center gap-2">
                            <span className={`w-3.5 h-3.5 rounded-sm ${item.color} border border-gray-300 flex-shrink-0`}></span>
                            <span className="text-gray-700">{item.label}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default MapLegend;
import React from 'react';

//지도 범례 컴포넌트
const MapLegend: React.FC = () => {
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
        <div className="absolute bottom-6 right-6 z-10 bg-white/90 backdrop-blur-sm p-3 rounded-lg shadow-lg border border-gray-200 text-xs">
            <div className="font-bold text-gray-800 mb-2 pb-1 border-b border-gray-100 flex items-center justify-between">
                <span>🏠 주거지역 범례</span>
            </div>
            <div className="flex flex-col gap-1.5">
                {legendItems.map((item, index) => (
                    <div key={index} className="flex items-center gap-2">
                        <span className={`w-3.5 h-3.5 rounded-sm ${item.color} border border-gray-300`}></span>
                        <span className="text-gray-700">{item.label}</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default MapLegend;
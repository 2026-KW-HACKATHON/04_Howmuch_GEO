import React, { useEffect, useState } from 'react';
import { useNewsPanel } from '../hooks/useNewsPanel';

//뉴스 페널 Props
interface NewsPanelProps {
    onNewsPanelOpen: boolean
    query: string
}

//뉴스 항목 인터페이스
interface NewsItem {
  title: string;
  contents: string;
  url: string;
  published_at: string;
}

//뉴스 페널 컴포넌트
const NewsPanel: React.FC<NewsPanelProps> = ({onNewsPanelOpen, query}) => {
    const {
        handleGetNews
    } = useNewsPanel();

    const [newsData, setNewsData] = useState<NewsItem[]>([]);


    useEffect(() => {
        if (!onNewsPanelOpen || !query) return;

        const loadNews = async (query: string) => {
            const data = await handleGetNews(query);
            setNewsData(data ?? []);
        };

        void loadNews(query);

    }, [onNewsPanelOpen, query]);

    return (
        <div className="relative min-h-full w-full bg-gradient-to-b from-slate-50 to-white px-4 py-5">
            <div className="mb-5 px-1">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-700">Local updates</p>
                <h2 className="mt-1 text-xl font-extrabold tracking-tight text-slate-900">지역 정보</h2>
                <p className="mt-1 text-sm text-slate-500">관심 지역의 최신 소식을 확인해 보세요.</p>
            </div>

            {/* 뉴스 컨테이너 */}
            <div className="flex w-full flex-col gap-3">
                {newsData.map((news) => (
                    <div className="group rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-lg hover:shadow-slate-200/60">
                        <article key={news.url}>
                            <span className="mb-2 inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-bold tracking-wide text-emerald-700">
                                지역정보
                            </span>
                            <h3 className="text-base font-bold leading-6 text-slate-800 transition-colors group-hover:text-emerald-800">
                                {news.title}
                            </h3>
                            <p className="mt-2.5 text-sm leading-6 text-slate-600">{news.contents}</p>
                            <a
                                className="mt-4 inline-flex items-center gap-2 text-sm font-bold text-emerald-700 transition-colors hover:text-emerald-900"
                                href={news.url}
                            >
                                페이지로 이동하기
                                <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4 transition-transform group-hover:translate-x-0.5">
                                    <path d="M4.167 10h11.666M10 4.167 15.833 10 10 15.833" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                            </a>
                        </article>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default NewsPanel;
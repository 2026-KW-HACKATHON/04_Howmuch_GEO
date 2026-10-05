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
        <div className="w-full h-screen relative">

            {/* 뉴스 컨테이너 */}
            <div className="w-full h-full" >
                {newsData.map((news) => (
                    <div className="bg-slate-200 m-5 p-5 rounded-xl">
                        <article key={news.url}>
                            <span className="font-semibold text-slate-500">{news.title}</span>
                            <p>{news.contents}</p>
                            <a className="font-semibold text-slate-500 hover:text-slate-700" href={news.url}>기사 보기</a>
                        </article>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default NewsPanel;
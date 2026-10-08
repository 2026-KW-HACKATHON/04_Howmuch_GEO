//접속시 팝업 모달 스키마
interface StartupModalSchema {
    onToggleModal: () => void;
}

//접속시 팝업 모달 컴포넌트
export default function StartupModal({onToggleModal} : StartupModalSchema){
    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm">
            <div className="flex h-full w-full items-center justify-center">
                <div className="flex max-h-[min(88vh,48rem)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-white/70 bg-white shadow-2xl shadow-slate-950/25 sm:rounded-3xl">
                    <div className="min-h-0 overflow-y-auto px-5 py-6 sm:px-8 sm:py-8 [&>p:first-child]:mb-5 [&>p:first-child]:text-lg [&>p:first-child]:font-bold [&>p:first-child]:leading-7 [&>p:first-child]:text-slate-900 sm:[&>p:first-child]:text-xl [&>p:nth-child(n+3)]:text-sm [&>p:nth-child(n+3)]:leading-6 [&>p:nth-child(n+3)]:text-slate-600">
                        <p className="text-center">얼마GEO를 이용하기 전에 꼭 읽어 주세요.</p>
                        <p></p>
                        <p>· 화면의 분담금은 공공데이터와 통계로 계산한 예측값이며, 확정 금액이 아닙니다.</p>
                        <p>· 확정 분담금은 감정평가와 관리처분계획 인가를 거쳐 정해집니다.</p>
                        <p> 인가 뒤에도 공사비 증액 등으로 준공 후 청산 때 달라질 수 있습니다.</p>
                        <p>· 사업 기간·공사비·사업비·분양가에는 서울 정비사업 사례의 중앙값과 과거 추세를 썼습니다.</p>
                        <p>  구역마다 다르니 슬라이더로 바꿔 보세요.</p>
                        <p>· 금액은 관리처분·준공 시점의 명목 금액입니다. 오늘 가치로 환산한 값이 아닙니다.</p>
                        <p>· 법령·조례·고시는 2026년 10월 기준입니다. 이후 바뀌면 결과도 달라집니다.</p>
                        <p>실제로는 구역의 정비계획과 조합 총회 결정이 우선합니다.</p>
                        <p>· 계산에 넣지 않은 것 : 재건축초과이익 환수 부담금, 개인 세금(취득세·양도소득세 등),</p>
                        <p>개인 대출 이자(추가 이주비 등), 분양 자격(현금청산 여부) 판단.</p>
                        <p>· 법적·세무적 판단은 변호사·세무사·감정평가사 등 전문가와 상담하세요.</p>
                        <p>· 참고용 정보입니다. 이 결과만으로 매매·투자를 결정하지 마세요.</p>
                    </div>
                    <div className="border-t border-slate-100 bg-slate-50 px-5 py-4 sm:px-8">
                        <button className="w-full rounded-xl bg-emerald-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-emerald-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2" onClick={onToggleModal}>
                            이해했습니다
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
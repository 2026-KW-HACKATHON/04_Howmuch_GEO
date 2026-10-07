import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { PaymentRequest } from '../api/payment_api';
import {
    approveOrganizationMember,
    applyOrganizationCode,
    getOrganizationMembers,
    getOrganizationOverview,
    leaveOrganization,
    removeOrganizationMember,
    type OrganizationMember,
    type OrganizationOverview,
} from '../api/organization_api';
import { resetUserCredits } from '../api/user_api';

export default function OrganizationPage() {
    const [overview, setOverview] = useState<OrganizationOverview | null>(null);
    const [members, setMembers] = useState<OrganizationMember[]>([]);
    const [invitationCode, setInvitationCode] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');
    const [notice, setNotice] = useState('');
    const [isResettingCredits, setIsResettingCredits] = useState(false);

    const loadPage = async () => {
        setIsLoading(true);
        setErrorMessage('');
        try {
            const account = await getOrganizationOverview();
            setOverview(account);
            if (account.role === 'leader') {
                const result = await getOrganizationMembers();
                setMembers(result.members);
            }
        } catch (error) {
            console.error('[ Organization page error ]', error);
            setErrorMessage('계정 정보를 불러오지 못했습니다. 로그인이 필요하거나 잠시 후 다시 시도해주세요.');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadPage();
    }, []);

    const submitInvitationCode = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setIsSaving(true);
        setErrorMessage('');
        setNotice('');
        try {
            await applyOrganizationCode(invitationCode);
            setInvitationCode('');
            setNotice('가입 신청을 보냈습니다. 조합장 승인 후 플랜 혜택이 적용됩니다.');
            await loadPage();
        } catch (error) {
            console.error('[ Organization join error ]', error);
            setErrorMessage('가입 신청을 처리하지 못했습니다. 코드를 확인하고 다시 시도해주세요.');
        } finally {
            setIsSaving(false);
        }
    };

    const resetCredits = async () => {
        if (!window.confirm('오늘 사용할 개인 크레딧을 5개로 초기화할까요?')) return;
        setIsResettingCredits(true);
        setErrorMessage('');
        setNotice('');
        try {
            await resetUserCredits();
            setNotice('오늘 사용할 크레딧 5개를 준비했습니다.');
        } catch (error) {
            console.error('[ Credit reset error ]', error);
            setErrorMessage('크레딧을 초기화하지 못했습니다. 이미 조합 플랜을 이용 중이거나 잠시 후 다시 시도해주세요.');
        } finally {
            setIsResettingCredits(false);
        }
    };

    const updateMember = async (member: OrganizationMember, action: 'approve' | 'remove') => {
        setIsSaving(true);
        setErrorMessage('');
        try {
            if (action === 'approve') await approveOrganizationMember(member.user_id);
            else await removeOrganizationMember(member.user_id);
            await loadPage();
        } catch (error) {
            console.error('[ Organization member update error ]', error);
            setErrorMessage(action === 'approve' ? '가입 승인에 실패했습니다.' : '구성원 제거에 실패했습니다.');
        } finally {
            setIsSaving(false);
        }
    };

    const leaveCurrentOrganization = async () => {
        if (!window.confirm('조합에서 탈퇴할까요? 승인 대기 중인 신청도 취소됩니다.')) return;
        setIsSaving(true);
        setErrorMessage('');
        setNotice('');
        try {
            await leaveOrganization();
            setNotice('조합에서 탈퇴했습니다. 개인 크레딧으로 이용할 수 있습니다.');
            await loadPage();
        } catch (error) {
            console.error('[ Organization leave error ]', error);
            setErrorMessage('조합 탈퇴에 실패했습니다. 잠시 후 다시 시도해주세요.');
        } finally {
            setIsSaving(false);
        }
    };

    const paymentParam: PaymentRequest | undefined = overview?.role === 'leader' && overview.plan_code
        ? {
            item_name: overview.plan_name ?? `플랜 ${overview.plan_code}`,
            quantity: 1,
            price: overview.price ?? 0,
            tax_free_amount: 0,
            plan_code: overview.plan_code,
        }
        : undefined;

    return (
        <main className="min-h-screen bg-[#f4f7f4] text-slate-900">
            <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-5 sm:px-10">
                <Link to="/main" className="text-lg font-bold tracking-tight">얼마 <span className="font-medium text-emerald-700">GEO</span></Link>
                <Link to="/main" className="text-sm font-medium text-slate-600 hover:text-slate-950">메인으로</Link>
            </header>
            <div className="mx-auto max-w-4xl px-5 py-10 sm:px-10">
                <p className="text-sm font-semibold uppercase tracking-[0.12em] text-emerald-800">Account</p>
                <h1 className="mt-2 text-3xl font-bold">조합·가입 관리</h1>

                {isLoading && <p className="mt-8 text-sm text-slate-500">계정 정보를 불러오는 중...</p>}
                {!isLoading && errorMessage && (
                    <section className="mt-8 border border-slate-200 bg-white p-6">
                        <p role="alert" className="text-sm text-rose-700">{errorMessage}</p>
                        <div className="mt-5 flex gap-3">
                            <Link to="/login" className="bg-slate-900 px-4 py-2 text-sm font-semibold text-white">로그인</Link>
                            <Link to="/signup" className="border border-slate-300 px-4 py-2 text-sm font-semibold">회원가입</Link>
                        </div>
                    </section>
                )}

                {!isLoading && overview?.role === 'personal' && (
                    <section className="mt-8 max-w-2xl border border-slate-200 bg-white p-6 sm:p-8">
                        <h2 className="text-lg font-semibold">조합 코드 등록</h2>
                        <p className="mt-2 text-sm leading-6 text-slate-600">조합장에게 받은 코드를 입력하면 가입 승인을 요청합니다. 승인 전에는 개인 일일 크레딧이 적용됩니다.</p>
                        <form onSubmit={submitInvitationCode} className="mt-6 flex flex-col gap-3 sm:flex-row">
                            <input value={invitationCode} onChange={(event) => setInvitationCode(event.target.value)} placeholder="조합 초대 코드" aria-label="조합 초대 코드" className="min-h-11 flex-1 border border-slate-300 px-3 outline-none focus:border-emerald-700" />
                            <button disabled={isSaving || !invitationCode.trim()} className="min-h-11 bg-emerald-700 px-5 font-semibold text-white disabled:opacity-50">가입 신청</button>
                        </form>
                        <div className="mt-7 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
                            <div>
                                <p className="text-sm font-semibold">개인 크레딧</p>
                                <p className="mt-1 text-sm text-slate-500">일일 기본 크레딧을 다시 준비합니다.</p>
                            </div>
                            <button type="button" disabled={isResettingCredits} onClick={() => void resetCredits()} className="min-h-10 border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                                {isResettingCredits ? '처리 중...' : '크레딧 충전'}
                            </button>
                        </div>
                    </section>
                )}

                {!isLoading && overview?.role === 'member' && (
                    <section className="mt-8 max-w-2xl border border-slate-200 bg-white p-6 sm:p-8">
                        <h2 className="text-lg font-semibold">조합 가입 상태</h2>
                        <p className="mt-3 text-sm text-slate-600">조합: {overview.organization_name ?? '조합'}</p>
                        <p className="mt-2 text-sm font-medium">{overview.membership_status === 'active' ? '승인 완료' : '조합장 승인 대기 중'}</p>
                        {overview.membership_status === 'active' && <p className="mt-2 text-sm text-emerald-800">플랜 기간 동안 무제한 크레딧 이용 중 · 만료 {overview.paid_until ? new Date(overview.paid_until).toLocaleDateString('ko-KR') : '-'}</p>}
                        <div className="mt-6 border-t border-slate-100 pt-5">
                            <button type="button" disabled={isSaving} onClick={() => void leaveCurrentOrganization()} className="min-h-10 border border-rose-200 px-4 text-sm font-semibold text-rose-700 transition hover:bg-rose-50 disabled:opacity-50">
                                {isSaving ? '처리 중...' : '조합 탈퇴'}
                            </button>
                        </div>
                    </section>
                )}

                {!isLoading && overview?.role === 'leader' && (
                    <>
                        <section className="mt-8 border border-slate-200 bg-white p-6 sm:p-8">
                            <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
                                <div>
                                    <h2 className="text-lg font-semibold">{overview.plan_name ?? `플랜 ${overview.plan_code}`}</h2>
                                    <p className="mt-2 text-sm text-slate-600">최대 {overview.max_members}명 · {overview.duration_months}개월 · ₩{(overview.price ?? 0).toLocaleString('ko-KR')}</p>
                                    <p className="mt-1 text-sm font-medium">상태: {overview.organization_status === 'active' ? '이용 중' : '결제 대기'}</p>
                                    {overview.paid_until && <p className="mt-1 text-sm text-slate-500">이용 만료일 {new Date(overview.paid_until).toLocaleDateString('ko-KR')}</p>}
                                </div>
                                {overview.organization_status !== 'active' && paymentParam && (
                                    <Link to="/payment" state={{ paymentParam }} className="flex min-h-11 items-center justify-center bg-[#ffeb00] px-5 text-sm font-semibold text-slate-950 hover:bg-[#f5df00]">플랜 결제</Link>
                                )}
                            </div>
                            {overview.invitation_code && <div className="mt-6 border-t border-slate-100 pt-5">
                                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">조합 초대 코드</p>
                                <p className="mt-2 select-all font-mono text-xl font-semibold tracking-wide">{overview.invitation_code}</p>
                            </div>}
                        </section>

                        <section className="mt-8 border border-slate-200 bg-white">
                            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                                <h2 className="font-semibold">구성원 관리</h2>
                                <span className="text-sm text-slate-500">{members.filter((member) => member.status === 'active').length} / {overview.max_members}명</span>
                            </div>
                            {members.length === 0 ? <p className="px-5 py-8 text-sm text-slate-500">가입 신청 또는 등록된 구성원이 없습니다.</p> : <ul className="divide-y divide-slate-100">
                                {members.map((member) => <li key={member.user_id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                                    <div>
                                        <p className="font-medium">{member.user_name}</p>
                                        <p className="mt-1 text-sm text-slate-500">{member.email} · {member.status === 'pending' ? '승인 대기' : '이용 중'}</p>
                                    </div>
                                    <div className="flex gap-2">
                                        {member.status === 'pending' && <button type="button" disabled={isSaving} onClick={() => void updateMember(member, 'approve')} className="border border-emerald-700 px-3 py-2 text-sm font-semibold text-emerald-800 disabled:opacity-50">승인</button>}
                                        <button type="button" disabled={isSaving} onClick={() => void updateMember(member, 'remove')} className="border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-600 disabled:opacity-50">삭제</button>
                                    </div>
                                </li>)}
                            </ul>}
                        </section>
                    </>
                )}

                {notice && <p role="status" className="mt-5 border-l-4 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{notice}</p>}
                {errorMessage && !isLoading && overview && <p role="alert" className="mt-5 border-l-4 border-rose-600 bg-rose-50 px-4 py-3 text-sm text-rose-900">{errorMessage}</p>}
            </div>
        </main>
    );
}

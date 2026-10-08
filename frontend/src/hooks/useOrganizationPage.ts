/// <reference types="vite/client" />

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

//NewsPanel Hook
export const useOrganizationPage= () => {

    const [overview, setOverview] = useState<OrganizationOverview | null>(null);
    const [members, setMembers] = useState<OrganizationMember[]>([]);
    const [invitationCode, setInvitationCode] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');
    const [notice, setNotice] = useState('');

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

    return {
        members,
        notice,
        isSaving,
        invitationCode,
        setInvitationCode,
        overview,
        isLoading,
        errorMessage,
        submitInvitationCode,
        updateMember,
        leaveCurrentOrganization,
        paymentParam
    };
};
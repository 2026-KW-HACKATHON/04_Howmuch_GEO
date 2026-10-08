import React, { useEffect, useState } from 'react';
import ContributionPanel from './ContributionPanel';
import { buildMetrics } from '../hooks/useContribution';
import { useModelPredictForm } from '../hooks/useModelPredictForm';
import {
    deleteOrganizationScenario,
    getOrganizationScenario,
    getOrganizationScenarios,
    saveOrganizationScenario,
    type OrganizationMapView,
    type OrganizationOverview,
    type OrganizationScenarioSummary,
} from '../api/organization_api';
import { ParcelInfo } from '../utils/parcel';

//예측 폼 Props
interface ModelPredictFormProps {
    onHandleZoneData: (pnus: string[], zoning?: string, parcels?: ParcelInfo[], targetYm?: string, householdCount?: number) => Promise<any>;
    onCalculateContribution: (requestData: any) => Promise<any>;
    selectedPnus: string[];
    isOpen: boolean;
    dailyCredits: number | null;
    creditsUnavailable: boolean;
    selectedParcels: ParcelInfo[];
    onRestoreSelection: (pnus: string[], parcels: ParcelInfo[], mapView: OrganizationMapView) => void;
    mapView: OrganizationMapView | null;
    organizationRole?: OrganizationOverview['role'];
    canUseSharedScenario: boolean;
}

//예측 폼 컴포넌트
const ModelPredictForm: React.FC<ModelPredictFormProps> = ({ 
    onHandleZoneData, 
    onCalculateContribution,
    selectedPnus,
    isOpen,
    dailyCredits,
    creditsUnavailable,
    selectedParcels,
    onRestoreSelection,
    mapView,
    organizationRole,
    canUseSharedScenario,
}) => {
    const [scenarioLoading, setScenarioLoading] = useState(false);
    const [scenarioMessage, setScenarioMessage] = useState('');
    const [scenarioError, setScenarioError] = useState('');
    const [scenarioName, setScenarioName] = useState('');
    const [sharedScenarios, setSharedScenarios] = useState<OrganizationScenarioSummary[]>([]);
    const {
        formData,
        sliderData,
        zoneInfo,
        targetYm,
        calcResult,
        loading,
        error,
        selectedZoning,
        zoningOptions,
        handleSelectZoning,
        handleSliderChange,
        unitMix,
        handleUnitMixChange,
        rentalExclusive,
        handleRentalExclusiveChange,
        handleApplyUnitMix,
        unitMixDirty,
        priorAsset,
        ownerPnu,
        handleSelectOwnerPnu,
        ownerExclusive,
        handleOwnerExclusiveChange,
        zoningStale,
        handleZoneData,
        createSharedScenario,
        loadSharedScenario,
    } = useModelPredictForm({
        onHandleZoneData,
        onCalculateContribution,
        selectedPnus,
        selectedParcels,
        onRestoreSelection,
        mapView,
    });

    useEffect(() => {
        if (!canUseSharedScenario) {
            setSharedScenarios([]);
            return;
        }
        let active = true;
        getOrganizationScenarios()
            .then((response) => {
                if (active) setSharedScenarios(response.scenarios);
            })
            .catch((listError) => {
                if (!active) return;
                setScenarioError('조합 기준안 목록을 불러오지 못했습니다.');
                console.error('[ 조합 기준안 목록 조회 오류 발생 ] : ', listError);
            });
        return () => {
            active = false;
        };
    }, [canUseSharedScenario]);

    const handleSaveScenario = async () => {
        setScenarioLoading(true);
        setScenarioMessage('');
        setScenarioError('');
        try {
            const scenario = createSharedScenario();
            if (!scenario) {
                setScenarioError('필지를 선택하고 먼저 구역을 분석해야 조합 기준안을 저장할 수 있습니다.');
                return;
            }
            if (!scenarioName.trim()) {
                setScenarioError('기준안 이름을 입력해 주세요.');
                return;
            }
            const saved = await saveOrganizationScenario(scenarioName.trim(), scenario);
            setSharedScenarios((current) => [
                { id: saved.id, name: saved.name, updated_at: saved.updated_at },
                ...current,
            ]);
            setScenarioMessage(`'${scenarioName.trim()}' 기준안을 저장했습니다.`);
            setScenarioName('');
        } catch (saveError) {
            setScenarioError('조합 기준안을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.');
            console.error('[ 조합 기준안 저장 오류 발생 ] : ', saveError);
        } finally {
            setScenarioLoading(false);
        }
    };

    const handleLoadScenario = async (scenarioId: number) => {
        setScenarioLoading(true);
        setScenarioMessage('');
        setScenarioError('');
        try {
            const response = await getOrganizationScenario(scenarioId);
            if (!response.scenario) {
                setScenarioError('선택한 기준안에 저장된 내용이 없습니다.');
                return;
            }
            await loadSharedScenario(response.scenario);
            const name = sharedScenarios.find((item) => item.id === scenarioId)?.name;
            setScenarioMessage(`'${name ?? '조합 기준안'}'을 불러왔습니다. 슬라이더 변경은 현재 화면에서만 적용됩니다.`);
        } catch (loadError) {
            setScenarioError('조합 기준안을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
            console.error('[ 조합 기준안 불러오기 오류 발생 ] : ', loadError);
        } finally {
            setScenarioLoading(false);
        }
    };

    const handleDeleteScenario = async (scenario: OrganizationScenarioSummary) => {
        if (!window.confirm(`'${scenario.name}' 기준안을 삭제할까요?`)) return;
        setScenarioLoading(true);
        setScenarioMessage('');
        setScenarioError('');
        try {
            await deleteOrganizationScenario(scenario.id);
            setSharedScenarios((current) => current.filter((item) => item.id !== scenario.id));
            setScenarioMessage(`'${scenario.name}' 기준안을 삭제했습니다.`);
        } catch (deleteError) {
            setScenarioError('조합 기준안을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.');
            console.error('[ 조합 기준안 삭제 오류 발생 ] : ', deleteError);
        } finally {
            setScenarioLoading(false);
        }
    };

    //계산 버튼을 누를 수 있는 조건 : 필지를 골랐고, 용도지역을 정했을 때
    //  용도지역이 용적률 범위를 정하므로 이것 없이 계산하면 가정값으로 돌아간다
    const canCalculate = selectedPnus.length > 0
        && !!selectedZoning
        && !loading
        && !creditsUnavailable
        && dailyCredits !== null
        && (dailyCredits === -1 || dailyCredits > 0);

    //조합원 수는 슬라이더 값을 쓰고, 아직 없으면 폼 기본값을 쓴다
    const memberCount = Number(sliderData.member_count?.value ?? formData.member_count);
    const metrics = buildMetrics(zoneInfo, calcResult, sliderData, memberCount);

    return (
        <div className={`h-full w-full bg-slate-50/50 flex flex-col items-center p-6 font-sans overflow-y-auto transition-opacity ${isOpen ? 'opacity-100 duration-500' : 'opacity-0 pointer-events-none duration-100'}`}>
            <div className="max-w-md w-full flex flex-col items-center gap-4">
                {canUseSharedScenario && organizationRole === 'leader' && (
                    <section className="w-full rounded-xl border border-emerald-200 bg-emerald-50/80 p-4">
                        <h2 className="text-sm font-bold text-emerald-900">조합 공유 기준안</h2>
                        <p className="mt-1 text-xs leading-5 text-emerald-800">
                            이름을 붙여 여러 기준안을 저장하고 구성원과 공유할 수 있습니다.
                        </p>
                        <input
                            type="text"
                            maxLength={60}
                            value={scenarioName}
                            onChange={(event) => setScenarioName(event.target.value)}
                            placeholder="예: 역세권 개발안"
                            aria-label="조합 기준안 이름"
                            className="mt-3 w-full rounded-lg border border-emerald-200 bg-white px-3 py-2 text-xs text-slate-800 outline-none focus:border-emerald-500"
                        />
                        <button
                            type="button"
                            onClick={() => void handleSaveScenario()}
                            disabled={scenarioLoading || !scenarioName.trim() || !createSharedScenario()}
                            className="mt-2 w-full rounded-lg bg-emerald-700 px-3 py-2.5 text-xs font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {scenarioLoading ? '처리 중...' : '새 기준안 저장'}
                        </button>
                    </section>
                )}
                {canUseSharedScenario && (
                    <section className="w-full rounded-xl border border-blue-200 bg-blue-50/80 p-4">
                        <h2 className="text-sm font-bold text-blue-900">조합 공유 기준안</h2>
                        <p className="mt-1 text-xs leading-5 text-blue-800">
                            조합장이 저장한 기준안을 불러옵니다. 원본은 수정되지 않으며, 변경한 슬라이더는 현재 화면에서만 시험할 수 있습니다.
                        </p>
                        {sharedScenarios.length === 0 ? (
                            <p className="mt-3 rounded-lg bg-white/70 px-3 py-2 text-xs text-slate-500">저장된 기준안이 없습니다.</p>
                        ) : (
                            <ul className="mt-3 space-y-2">
                                {sharedScenarios.map((scenario) => (
                                    <li key={scenario.id} className="flex items-center gap-2 rounded-lg bg-white p-2.5">
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate text-xs font-semibold text-slate-800">{scenario.name}</p>
                                            <p className="mt-0.5 text-[10px] text-slate-500">
                                                {new Date(scenario.updated_at).toLocaleString()}
                                            </p>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => void handleLoadScenario(scenario.id)}
                                            disabled={scenarioLoading}
                                            className="shrink-0 rounded-md bg-blue-700 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-blue-800 disabled:opacity-50"
                                        >
                                            불러오기
                                        </button>
                                        {organizationRole === 'leader' && (
                                            <button
                                                type="button"
                                                onClick={() => void handleDeleteScenario(scenario)}
                                                disabled={scenarioLoading}
                                                className="shrink-0 rounded-md px-2 py-1.5 text-[11px] font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
                                            >
                                                삭제
                                            </button>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>
                )}
                {scenarioMessage && <p role="status" className="w-full rounded-lg bg-white px-3 py-2 text-xs text-slate-600">{scenarioMessage}</p>}
                {scenarioError && <p role="alert" className="w-full rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{scenarioError}</p>}

                {/* 1단계 : 선택한 필지 */}
                <div className="w-full flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5">
                    <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10.5px] font-semibold text-slate-500">1</span>
                    <span className="text-[12.5px] text-slate-500">선택한 필지</span>
                    <span className="ml-auto text-[12.5px] font-semibold text-slate-900">{selectedPnus.length}개</span>
                </div>

                {/* 2단계 : 용도지역 선택
                    용적률 범위를 정하는 값이라 계산 전에 반드시 골라야 한다.
                    정비사업은 정비계획에서 용도지역을 새로 정하므로 현황 조회값을 그대로 쓰지 않는다.
                    재개발은 사실상 주거지역에서만 일어나므로 서버가 주거지역만 내려준다 */}
                <div className="w-full bg-white rounded-xl border border-slate-200 p-4">
                    <div className="mb-2 flex items-center gap-2">
                        <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10.5px] font-semibold text-slate-500">2</span>
                        <label className="text-xs font-bold tracking-wider text-slate-700">용도지역</label>
                        {!selectedZoning && (
                            <span className="text-[11px] text-amber-600">계산하려면 선택하세요</span>
                        )}
                    </div>

                    <div className="grid grid-cols-2 gap-1.5">
                        {zoningOptions.map((z) => (
                            <button
                                key={z}
                                type="button"
                                onClick={() => handleSelectZoning(z)}
                                className={`rounded-lg border px-2 py-1.5 text-[11.5px] transition ${
                                    selectedZoning === z
                                        ? 'border-blue-600 bg-blue-50 font-semibold text-blue-700'
                                        : 'border-slate-200 text-slate-600 hover:border-slate-300'
                                }`}
                            >
                                {z.replace('지역', '')}
                            </button>
                        ))}
                    </div>
                </div>

                {/* 3단계 : 계산 버튼
                    슬라이더를 움직일 때는 자동으로 다시 계산되지만,
                    필지·용도지역을 바꾼 뒤에는 이 버튼을 눌러야 반영된다 */}
                <button
                    type="button"
                    onClick={handleZoneData}
                    disabled={!canCalculate}
                    className="w-full rounded-xl bg-emerald-600 px-3 py-3 text-[13px] font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                    {loading
                        ? '계산 중...'
                        : creditsUnavailable
                            ? '크레딧 정보를 불러올 수 없습니다'
                        : dailyCredits === null
                            ? '현재 사용할 수 없습니다'
                        : dailyCredits === -1
                            ? '분담금 계산 · 무제한 크레딧'
                        : dailyCredits <= 0
                            ? '오늘의 크레딧을 모두 사용했습니다'
                        : selectedPnus.length === 0
                            ? '지도에서 필지를 선택하세요'
                            : !selectedZoning
                                ? '용도지역을 선택하세요'
                                : `분담금 계산 · 크레딧 ${dailyCredits}개`}
                </button>

                {/* 예상 분담금 패널 : 필지 선택 전에는 0, 선택하면 그 필지만큼 계산된다 */}
                <ContributionPanel
                    result={calcResult}
                    metrics={metrics}
                    sliders={sliderData}
                    onSliderChange={handleSliderChange}
                    unitMix={unitMix}
                    onUnitMixChange={handleUnitMixChange}
                    rentalExclusive={rentalExclusive}
                    onRentalExclusiveChange={handleRentalExclusiveChange}
                    onApplyUnitMix={handleApplyUnitMix}
                    unitMixDirty={unitMixDirty}
                    priorAsset={priorAsset}
                    ownerPnu={ownerPnu}
                    onSelectOwnerPnu={handleSelectOwnerPnu}
                    ownerExclusive={ownerExclusive}
                    onOwnerExclusiveChange={handleOwnerExclusiveChange}
                    zoningStale={zoningStale}
                    targetYm={targetYm}
                    loading={loading}
                />

                {error && (
                    <div className="w-full p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs break-all">
                        {error}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ModelPredictForm;

'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Company } from '@/types';
import {
  Asset,
  AssetDepreciationSchedule,
  AssetSummaryMetrics,
  AssetCreatePayload,
  fetchAssets,
  fetchAssetSummary,
  createAsset,
  postAssetDepreciation,
  disposeAsset,
  deleteAsset,
} from '@/lib/api';
import {
  Briefcase,
  Plus,
  Search,
  Filter,
  Layers,
  Calendar,
  CheckCircle2,
  AlertCircle,
  TrendingDown,
  DollarSign,
  FileText,
  Trash2,
  ExternalLink,
  ChevronRight,
  Info,
  Clock,
  ArrowDownRight,
  ShieldCheck,
  X,
  RefreshCw,
} from 'lucide-react';

interface AssetsViewProps {
  company?: Company;
  onNotify: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
}

const CATEGORIES = [
  { value: 'EQUIPOS_INFORMATICOS', label: 'Equipos Informáticos (217)' },
  { value: 'MOBILIARIO', label: 'Mobiliario (216)' },
  { value: 'MAQUINARIA', label: 'Maquinaria (213)' },
  { value: 'ELEMENTOS_TRANSPORTE', label: 'Elementos de Transporte (218)' },
  { value: 'CONSTRUCCIONES', label: 'Construcciones (211)' },
  { value: 'INSTALACIONES_TECNICAS', label: 'Instalaciones Técnicas (212)' },
  { value: 'APLICACIONES_INFORMATICAS', label: 'Software e Intangibles (206)' },
  { value: 'UTILLAJE', label: 'Utillaje (214)' },
  { value: 'OTRO_INMOVILIZADO', label: 'Otro Inmovilizado (219)' },
];

export const AssetsView: React.FC<AssetsViewProps> = ({ company, onNotify }) => {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [summary, setSummary] = useState<AssetSummaryMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');

  // Selección de activo para el Drawer lateral de Ficha Técnica y Calendario
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);

  // Modales
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [showDisposeModal, setShowDisposeModal] = useState<boolean>(false);
  const [disposingAsset, setDisposingAsset] = useState<Asset | null>(null);

  // Formulario nuevo activo
  const [newCode, setNewCode] = useState<string>('');
  const [newName, setNewName] = useState<string>('');
  const [newCategory, setNewCategory] = useState<string>('EQUIPOS_INFORMATICOS');
  const [newAcqDate, setNewAcqDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [newAcqCost, setNewAcqCost] = useState<number>(1200);
  const [newResidual, setNewResidual] = useState<number>(0);
  const [newUsefulLife, setNewUsefulLife] = useState<number>(4);
  const [newMethod, setNewMethod] = useState<string>('LINEAL');
  const [newNotes, setNewNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Formulario baja/venta
  const [dispDate, setDispDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [dispAmount, setDispAmount] = useState<number>(0);
  const [dispReason, setDispReason] = useState<string>('Obsolescencia técnica');

  const loadData = async () => {
    if (!company?.id) return;
    setLoading(true);
    try {
      const [assetList, sumData] = await Promise.all([
        fetchAssets(company.id, statusFilter, categoryFilter, search),
        fetchAssetSummary(company.id),
      ]);
      setAssets(assetList);
      setSummary(sumData);

      // Si teníamos un activo seleccionado, refrescar su estado
      if (selectedAsset) {
        const updated = assetList.find((a) => a.id === selectedAsset.id);
        if (updated) setSelectedAsset(updated);
      }
    } catch (err: any) {
      onNotify('error', err.message || 'Error al cargar los activos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [company?.id, statusFilter, categoryFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadData();
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!company?.id) return;
    if (!newCode.trim() || !newName.trim()) {
      onNotify('error', 'El código y la descripción son obligatorios.');
      return;
    }
    setSubmitting(true);
    try {
      const payload: AssetCreatePayload = {
        code: newCode.trim(),
        name: newName.trim(),
        category: newCategory,
        acquisition_date: newAcqDate,
        acquisition_cost: Number(newAcqCost),
        residual_value: Number(newResidual),
        useful_life_years: Number(newUsefulLife),
        depreciation_method: newMethod,
        notes: newNotes.trim() || undefined,
      };
      const created = await createAsset(company.id, payload);
      onNotify('success', `Activo ${created.code} registrado con éxito.`);
      setShowCreateModal(false);
      // Resetear campos
      setNewCode(`ACT-${Date.now().toString().slice(-4)}`);
      setNewName('');
      loadData();
      setSelectedAsset(created);
    } catch (err: any) {
      onNotify('error', err.message || 'Error al crear activo');
    } finally {
      setSubmitting(false);
    }
  };

  const handlePostDepreciation = async (asset: Asset, fiscalYear: number) => {
    if (!company?.id) return;
    try {
      const res = await postAssetDepreciation(company.id, asset.id, fiscalYear);
      onNotify('success', res.message, 'Asiento Contable Generado');
      await loadData();
    } catch (err: any) {
      onNotify('error', err.message || 'Error al contabilizar dotación');
    }
  };

  const handleDisposeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!company?.id || !disposingAsset) return;
    try {
      const res = await disposeAsset(company.id, disposingAsset.id, {
        disposal_date: dispDate,
        disposal_amount: Number(dispAmount),
        disposal_reason: dispReason,
      });
      onNotify('success', res.message, 'Desinversión Contabilizada');
      setShowDisposeModal(false);
      setDisposingAsset(null);
      await loadData();
    } catch (err: any) {
      onNotify('error', err.message || 'Error al dar de baja el activo');
    }
  };

  const handleDelete = async (asset: Asset) => {
    if (!company?.id) return;
    if (!confirm(`¿Eliminar definitivamente el activo ${asset.code}? Solo se permite si no tiene dotaciones contabilizadas.`)) {
      return;
    }
    try {
      await deleteAsset(company.id, asset.id);
      onNotify('success', `Activo ${asset.code} eliminado correctamente.`);
      if (selectedAsset?.id === asset.id) setSelectedAsset(null);
      await loadData();
    } catch (err: any) {
      onNotify('error', err.message || 'Error al eliminar');
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ACTIVO':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            En Explotación
          </span>
        );
      case 'TOTALMENTE_AMORTIZADO':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <CheckCircle2 className="w-3 h-3 text-blue-400" />
            Amortizado 100%
          </span>
        );
      case 'VENDIDO':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <DollarSign className="w-3 h-3 text-purple-400" />
            Vendido
          </span>
        );
      case 'BAJA':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">
            <TrendingDown className="w-3 h-3 text-slate-400" />
            Dado de Baja
          </span>
        );
      default:
        return <span className="text-xs text-slate-400">{status}</span>;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 text-slate-100 overflow-hidden">
      {/* CABECERA Y METRICAS */}
      <div className="p-6 border-b border-slate-800 bg-slate-900/60 backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <Briefcase className="w-5 h-5" />
              </div>
              <h1 className="text-xl font-bold text-slate-100">Inmovilizado y Amortizaciones</h1>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                PGC Grupo 2
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Fichas de activo fijo, cuadro plurianual de dotaciones (681/281) y trazabilidad contable de bajas.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setNewCode(`ACT-${new Date().getFullYear()}-${String(assets.length + 1).padStart(3, '0')}`);
                setShowCreateModal(true);
              }}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs shadow-lg shadow-indigo-600/20 transition-all cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Nuevo Activo
            </button>
            <button
              onClick={loadData}
              title="Refrescar datos"
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* TARJETAS RESUMEN KPI */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80">
            <div className="text-xs text-slate-400 font-medium flex items-center justify-between">
              <span>Coste Histórico (Grupo 21)</span>
              <DollarSign className="w-4 h-4 text-slate-500" />
            </div>
            <div className="text-xl font-bold text-slate-100 mt-2 font-mono">
              {(summary?.total_acquisition_cost || 0).toLocaleString('es-ES', {
                style: 'currency',
                currency: 'EUR',
              })}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {summary?.total_assets_count || 0} activos en inventario
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80">
            <div className="text-xs text-slate-400 font-medium flex items-center justify-between">
              <span>Amortización Acum. (Grupo 28)</span>
              <TrendingDown className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-xl font-bold text-amber-400 mt-2 font-mono">
              {(summary?.total_accumulated_depreciation || 0).toLocaleString('es-ES', {
                style: 'currency',
                currency: 'EUR',
              })}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">Dotaciones imputadas al gasto</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80">
            <div className="text-xs text-slate-400 font-medium flex items-center justify-between">
              <span>Valor Neto Contable (VNC)</span>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-xl font-bold text-emerald-400 mt-2 font-mono">
              {(summary?.total_net_book_value || 0).toLocaleString('es-ES', {
                style: 'currency',
                currency: 'EUR',
              })}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">Valor en balance actual</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80">
            <div className="text-xs text-slate-400 font-medium flex items-center justify-between">
              <span>Distribución por Estado</span>
              <Layers className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="flex items-center gap-3 mt-2 text-xs font-semibold">
              <span className="text-emerald-400">{summary?.active_count || 0} Activos</span>
              <span className="text-blue-400">{summary?.fully_depreciated_count || 0} Amort.</span>
              <span className="text-slate-400">{summary?.disposed_count || 0} Bajas</span>
            </div>
            <div className="text-[11px] text-slate-500 mt-1">Segregación PGC</div>
          </div>
        </div>
      </div>

      {/* BARRA DE FILTROS Y BUSQUEDA */}
      <div className="px-6 py-3 border-b border-slate-800/80 bg-slate-900/30 flex flex-wrap items-center justify-between gap-3">
        <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 max-w-md">
          <div className="relative w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar por código, descripción o notas..."
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </form>

        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">Todos los Estados</option>
            <option value="ACTIVO">En Explotación</option>
            <option value="TOTALMENTE_AMORTIZADO">Amortizado 100%</option>
            <option value="BAJA">Baja</option>
            <option value="VENDIDO">Vendido</option>
          </select>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">Todas las Categorías</option>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* CONTENIDO PRINCIPAL: TABLA DE ACTIVOS Y DRAWER LATERAL */}
      <div className="flex-1 flex overflow-hidden">
        {/* TABLA PRINCIPAL */}
        <div className="flex-1 overflow-auto p-6">
          {loading && assets.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400">
              <RefreshCw className="w-8 h-8 animate-spin text-indigo-500 mb-2" />
              <p className="text-sm">Cargando inventario de inmovilizado...</p>
            </div>
          ) : assets.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400 border border-dashed border-slate-800 rounded-xl p-8">
              <Briefcase className="w-12 h-12 text-slate-600 mb-3" />
              <p className="text-sm font-medium text-slate-300">No hay activos registrados</p>
              <p className="text-xs text-slate-500 mt-1 max-w-sm text-center">
                Registra tu primer equipo informático, vehículo o maquinaria para calcular su amortización y generar asientos automáticamente.
              </p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="mt-4 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium cursor-pointer"
              >
                + Registrar Activo
              </button>
            </div>
          ) : (
            <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-900/40">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900 text-slate-400 uppercase tracking-wider text-[11px] font-semibold border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Código / Nombre</th>
                    <th className="py-3 px-4">Categoría PGC</th>
                    <th className="py-3 px-4">F. Compra</th>
                    <th className="py-3 px-4 text-right">Coste Adq.</th>
                    <th className="py-3 px-4 text-right">Amort. Acum.</th>
                    <th className="py-3 px-4 text-right">VNC Actual</th>
                    <th className="py-3 px-4">Estado</th>
                    <th className="py-3 px-4 text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {assets.map((asset) => {
                    const isSelected = selectedAsset?.id === asset.id;
                    return (
                      <tr
                        key={asset.id}
                        onClick={() => setSelectedAsset(asset)}
                        className={`hover:bg-slate-800/40 transition cursor-pointer ${
                          isSelected ? 'bg-indigo-950/20 border-l-2 border-indigo-500' : ''
                        }`}
                      >
                        <td className="py-3 px-4 font-sans">
                          <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                            <span className="font-mono text-indigo-400 text-xs">{asset.code}</span>
                            <span>{asset.name}</span>
                          </div>
                          <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                            Subcuentas: {asset.account_asset} / {asset.account_accumulated_depreciation}
                          </div>
                        </td>
                        <td className="py-3 px-4 font-sans text-slate-400">
                          {CATEGORIES.find((c) => c.value === asset.category)?.label.split(' (')[0] || asset.category}
                        </td>
                        <td className="py-3 px-4 text-slate-400">
                          {asset.acquisition_date}
                        </td>
                        <td className="py-3 px-4 text-right font-semibold text-slate-100">
                          {asset.acquisition_cost.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
                        </td>
                        <td className="py-3 px-4 text-right text-amber-400">
                          {asset.accumulated_depreciation.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
                        </td>
                        <td className="py-3 px-4 text-right font-semibold text-emerald-400">
                          {asset.net_book_value.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
                        </td>
                        <td className="py-3 px-4 font-sans">
                          {getStatusBadge(asset.status)}
                        </td>
                        <td className="py-3 px-4 text-center font-sans">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedAsset(asset);
                            }}
                            className="p-1 rounded text-slate-400 hover:text-indigo-400 transition"
                            title="Ver ficha y calendario"
                          >
                            <ChevronRight className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* DRAWER LATERAL: FICHA TECNICA Y CALENDARIO */}
        {selectedAsset && (
          <div className="w-96 border-l border-slate-800 bg-slate-900/90 flex flex-col h-full overflow-hidden shadow-2xl">
            {/* Cabecera del Drawer */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Ficha de Activo
                </span>
              </div>
              <button
                onClick={() => setSelectedAsset(null)}
                className="p-1 rounded text-slate-400 hover:text-slate-200 transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Contenido scrolleable */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-indigo-400 font-bold">{selectedAsset.code}</span>
                  {getStatusBadge(selectedAsset.status)}
                </div>
                <h2 className="text-base font-bold text-slate-100 mt-1">{selectedAsset.name}</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Vida útil: {selectedAsset.useful_life_years} años • Método {selectedAsset.depreciation_method}
                </p>
              </div>

              {/* Métricas clave */}
              <div className="grid grid-cols-2 gap-2 p-3 rounded-lg bg-slate-950/80 border border-slate-800/80 text-xs font-mono">
                <div>
                  <span className="text-[10px] text-slate-500 uppercase font-sans">Coste Histórico</span>
                  <p className="font-bold text-slate-200 mt-0.5">{selectedAsset.acquisition_cost.toFixed(2)} €</p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 uppercase font-sans">Valor Residual</span>
                  <p className="font-bold text-slate-200 mt-0.5">{selectedAsset.residual_value.toFixed(2)} €</p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 uppercase font-sans">Amort. Acumulada</span>
                  <p className="font-bold text-amber-400 mt-0.5">{selectedAsset.accumulated_depreciation.toFixed(2)} €</p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 uppercase font-sans">VNC Pendiente</span>
                  <p className="font-bold text-emerald-400 mt-0.5">{selectedAsset.net_book_value.toFixed(2)} €</p>
                </div>
              </div>

              {/* Cuentas PGC Asignadas */}
              <div className="p-3 rounded-lg bg-slate-950/40 border border-slate-800/60 text-xs space-y-1.5">
                <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider block">
                  Cuentas Oficiales PGC
                </span>
                <div className="flex justify-between text-slate-300 font-mono">
                  <span className="text-slate-500 font-sans">Activo (21X):</span>
                  <span>{selectedAsset.account_asset}</span>
                </div>
                <div className="flex justify-between text-slate-300 font-mono">
                  <span className="text-slate-500 font-sans">Amort. Acumulada (28X):</span>
                  <span>{selectedAsset.account_accumulated_depreciation}</span>
                </div>
                <div className="flex justify-between text-slate-300 font-mono">
                  <span className="text-slate-500 font-sans">Dotación Gasto (68X):</span>
                  <span>{selectedAsset.account_depreciation_expense}</span>
                </div>
              </div>

              {/* CUADRO DE AMORTIZACIONES PLURIANUAL */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                    Calendario de Dotaciones
                  </span>
                  <span className="text-[10px] text-slate-400">
                    {selectedAsset.schedules?.length || 0} periodos
                  </span>
                </div>

                <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-950/60">
                  <table className="w-full text-left text-[11px] text-slate-300">
                    <thead className="bg-slate-900/80 text-slate-400 text-[10px] uppercase font-semibold border-b border-slate-800">
                      <tr>
                        <th className="py-2 px-2.5">Año</th>
                        <th className="py-2 px-2 text-right">Cuota</th>
                        <th className="py-2 px-2 text-right">VNC Cierre</th>
                        <th className="py-2 px-2.5 text-center">Estado</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/40 font-mono">
                      {selectedAsset.schedules?.map((sched) => (
                        <tr key={sched.id} className="hover:bg-slate-800/30">
                          <td className="py-2 px-2.5 font-bold text-slate-200">{sched.fiscal_year}</td>
                          <td className="py-2 px-2 text-right text-amber-400 font-semibold">
                            {sched.depreciation_amount.toFixed(2)} €
                          </td>
                          <td className="py-2 px-2 text-right text-emerald-400">
                            {sched.net_book_value.toFixed(2)} €
                          </td>
                          <td className="py-2 px-2.5 text-center font-sans">
                            {sched.is_posted ? (
                              <span
                                className="inline-flex items-center gap-1 text-[10px] text-emerald-400 font-semibold"
                                title={`Contabilizado en asiento #${sched.accounting_entry_number}`}
                              >
                                <CheckCircle2 className="w-3 h-3" />
                                #{sched.accounting_entry_number}
                              </span>
                            ) : (
                              <button
                                onClick={() => handlePostDepreciation(selectedAsset, sched.fiscal_year)}
                                className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition cursor-pointer shadow"
                                title="Generar asiento contable 681/281"
                              >
                                Contabilizar
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* ACCIONES DE DESINVERSION / BAJA / ELIMINACIÓN */}
              <div className="pt-2 border-t border-slate-800 flex flex-col gap-2">
                {selectedAsset.status === 'ACTIVO' && (
                  <button
                    onClick={() => {
                      setDisposingAsset(selectedAsset);
                      setDispAmount(0);
                      setDispReason('Obsolescencia técnica');
                      setShowDisposeModal(true);
                    }}
                    className="w-full py-2 rounded-lg bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/30 text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer"
                  >
                    <TrendingDown className="w-3.5 h-3.5" />
                    Dar de Baja / Vender Activo
                  </button>
                )}

                {!selectedAsset.schedules?.some((s) => s.is_posted) && (
                  <button
                    onClick={() => handleDelete(selectedAsset)}
                    className="w-full py-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 text-xs transition flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Eliminar Ficha
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* MODAL CREAR ACTIVO */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-slate-100 text-sm">Alta de Activo en Inmovilizado</h3>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-200 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="p-5 overflow-y-auto space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-medium mb-1">Código Interno</label>
                  <input
                    type="text"
                    required
                    value={newCode}
                    onChange={(e) => setNewCode(e.target.value)}
                    placeholder="ej. ACT-2026-001"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 font-mono focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-medium mb-1">Categoría PGC</label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:border-indigo-500 focus:outline-none"
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-medium mb-1">Descripción / Nombre del Bien</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="ej. Portátil Dell Latitude 5540 Contabilidad"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-400 font-medium mb-1">F. Adquisición</label>
                  <input
                    type="date"
                    required
                    value={newAcqDate}
                    onChange={(e) => setNewAcqDate(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 font-mono focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-medium mb-1">Coste (€)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    min="1"
                    value={newAcqCost}
                    onChange={(e) => setNewAcqCost(parseFloat(e.target.value) || 0)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 font-mono focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-medium mb-1">Valor Residual (€)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={newResidual}
                    onChange={(e) => setNewResidual(parseFloat(e.target.value) || 0)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 font-mono focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-medium mb-1">Vida Útil (Años)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max="100"
                    required
                    value={newUsefulLife}
                    onChange={(e) => setNewUsefulLife(parseFloat(e.target.value) || 1)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 font-mono focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-medium mb-1">Método de Amortización</label>
                  <select
                    value={newMethod}
                    onChange={(e) => setNewMethod(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="LINEAL">Lineal Constante (Proporcional por días)</option>
                    <option value="DIGITOS_DECRECIENTE">Suma de Dígitos Decreciente</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-medium mb-1">Observaciones / Ubicación</label>
                <textarea
                  rows={2}
                  value={newNotes}
                  onChange={(e) => setNewNotes(e.target.value)}
                  placeholder="ej. Ubicado en oficina central, asignado a Responsable Financiero."
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div className="p-3 rounded-lg bg-indigo-950/20 border border-indigo-500/20 text-indigo-300 text-[11px] flex items-start gap-2">
                <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                <p>
                  Las subcuentas PGC (Grupo 21X, 28X y 68X) se autogenerarán y adaptarán a los {company?.plan_cuentas_longitud || 9} dígitos de la empresa.
                </p>
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition cursor-pointer"
                >
                  {submitting ? 'Guardando...' : 'Crear y Calcular Cuadro'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL BAJA / VENTA DE ACTIVO */}
      {showDisposeModal && disposingAsset && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden flex flex-col">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingDown className="w-5 h-5 text-amber-400" />
                <h3 className="font-bold text-slate-100 text-sm">Baja o Venta de Activo</h3>
              </div>
              <button
                onClick={() => setShowDisposeModal(false)}
                className="text-slate-400 hover:text-slate-200 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleDisposeSubmit} className="p-5 space-y-4 text-xs">
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                <div className="font-bold text-slate-200">{disposingAsset.code} - {disposingAsset.name}</div>
                <div className="text-slate-400 font-mono mt-1 text-[11px]">
                  Coste Histórico: {disposingAsset.acquisition_cost.toFixed(2)} € • VNC: {disposingAsset.net_book_value.toFixed(2)} €
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-medium mb-1">Fecha de Desinversión</label>
                <input
                  type="date"
                  required
                  value={dispDate}
                  onChange={(e) => setDispDate(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 font-mono focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-medium mb-1">
                  Importe de Venta / Cobro (€) <span className="text-slate-500">(0 si es desguace o baja)</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={dispAmount}
                  onChange={(e) => setDispAmount(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 font-mono focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-medium mb-1">Motivo Auditable</label>
                <input
                  type="text"
                  required
                  value={dispReason}
                  onChange={(e) => setDispReason(e.target.value)}
                  placeholder="ej. Enajenación a tercero, rotura irreparable..."
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div className="p-3 rounded-lg bg-amber-950/20 border border-amber-500/20 text-amber-300 text-[11px]">
                Se generará un asiento contable que saldará la cuenta 28X de amortización acumulada y la 21X del activo, reconociendo el beneficio (771) o pérdida (671) en partida doble.
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowDisposeModal(false)}
                  className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold transition cursor-pointer"
                >
                  Contabilizar Baja
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

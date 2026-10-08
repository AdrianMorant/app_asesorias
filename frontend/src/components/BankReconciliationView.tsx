'use client';

import React, { useState, useEffect } from 'react';
import { Company } from '@/types';
import {
  Landmark,
  CheckCircle2,
  Clock,
  Sparkles,
  ArrowUpRight,
  ArrowDownLeft,
  Search,
  Filter,
  RefreshCw,
  Check,
  Eye,
  X,
  FileCheck2,
  AlertCircle,
  HelpCircle,
  ShieldCheck,
  Building2,
  Receipt,
  Scale,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface BankTransactionItem {
  id?: string;
  transaction_id?: string;
  date: string | null;
  amount: number;
  description: string;
  status: 'PREVALIDADO' | 'SUGERIDO' | 'PENDIENTE' | 'CONCILIADO';
  match_type?: string;
  invoice_id?: string | null;
  invoice_number?: string | null;
  matched_party?: string | null;
  counterpart_account?: string;
  suggested_concept?: string;
  confidence?: number;
  notes?: string;
  entry_number?: number;
}

export interface BankEntryPreviewLine {
  entry_number: number;
  line_number: number;
  subcuenta: string;
  concepto: string;
  debe: number;
  haber: number;
  documento: string;
}

export interface BankEntryPreview {
  entry_number: number;
  date: string;
  concept: string;
  document: string;
  total_debe: number;
  total_haber: number;
  is_balanced: boolean;
  lines: BankEntryPreviewLine[];
}

interface BankReconciliationViewProps {
  company: Company;
  onNotify: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
  onRefreshData?: () => void;
}

export const BankReconciliationView: React.FC<BankReconciliationViewProps> = ({
  company,
  onNotify,
  onRefreshData,
}) => {
  const [transactions, setTransactions] = useState<BankTransactionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [dateMargin, setDateMargin] = useState<number>(5);

  // Estados del modal de previsualización de asiento
  const [activeModalTx, setActiveModalTx] = useState<BankTransactionItem | null>(null);
  const [entryPreview, setEntryPreview] = useState<BankEntryPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState<boolean>(false);
  const [reconciling, setReconciling] = useState<boolean>(false);
  const [editCounterpart, setEditCounterpart] = useState<string>('');
  const [editBankAccount, setEditBankAccount] = useState<string>('57200000');

  // Cargar transacciones desde el backend
  const loadTransactions = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/companies/${company.id}/bank-transactions?date_margin_days=${dateMargin}`
      );
      if (!res.ok) {
        throw new Error('Error al consultar movimientos bancarios');
      }
      const data = await res.json();
      setTransactions(data.transactions || []);
    } catch (err: any) {
      onNotify('error', err.message || 'Error al conectar con el módulo bancario');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTransactions();
  }, [company.id, dateMargin]);

  // Abrir modal de previsualización de asiento contable
  const handleOpenPreview = async (tx: BankTransactionItem) => {
    setActiveModalTx(tx);
    const initialCounterpart = tx.counterpart_account || '55500000';
    setEditCounterpart(initialCounterpart);
    setLoadingPreview(true);
    try {
      const txPayload = {
        ...tx,
        counterpart_account: initialCounterpart,
      };
      const res = await fetch(`${API_BASE}/companies/${company.id}/bank-transactions/preview-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transaction: txPayload,
          counterpart_account: initialCounterpart,
          bank_account: editBankAccount,
        }),
      });
      if (!res.ok) throw new Error('Error al generar previsualización del asiento');
      const data: BankEntryPreview = await res.json();
      setEntryPreview(data);
    } catch (err: any) {
      onNotify('error', err.message || 'Fallo al calcular el asiento de banco');
    } finally {
      setLoadingPreview(false);
    }
  };

  // Recalcular previsualización al cambiar la subcuenta de contrapartida
  const handleRecalculatePreview = async (newCounterpart: string) => {
    if (!activeModalTx) return;
    setLoadingPreview(true);
    try {
      const txPayload = {
        ...activeModalTx,
        counterpart_account: newCounterpart,
      };
      const res = await fetch(`${API_BASE}/companies/${company.id}/bank-transactions/preview-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transaction: txPayload,
          counterpart_account: newCounterpart,
          bank_account: editBankAccount,
        }),
      });
      if (!res.ok) throw new Error('Error al actualizar asiento');
      const data: BankEntryPreview = await res.json();
      setEntryPreview(data);
    } catch (err: any) {
      onNotify('error', err.message || 'No se pudo actualizar el asiento');
    } finally {
      setLoadingPreview(false);
    }
  };

  // Confirmar y Contabilizar en Libro Diario
  const handleConfirmReconciliation = async (tx: BankTransactionItem, customCounterpart?: string) => {
    setReconciling(true);
    const txId = tx.transaction_id || tx.id;
    const counterpartToUse = customCounterpart || tx.counterpart_account || '55500000';
    try {
      const res = await fetch(
        `${API_BASE}/companies/${company.id}/bank-transactions/${txId}/reconcile`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            counterpart_account: counterpartToUse,
            bank_account: editBankAccount,
            concept: tx.suggested_concept || tx.description,
            invoice_id: tx.invoice_id,
          }),
        }
      );
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Fallo al contabilizar la conciliación');
      }
      const data = await res.json();

      onNotify(
        'success',
        `Movimiento conciliado con éxito. Asiento #${data.entry_number} guardado en el Libro Diario.`,
        'Conciliación Registrada'
      );

      // Actualizar estado local
      setTransactions((prev) =>
        prev.map((t) =>
          (t.transaction_id || t.id) === txId
            ? { ...t, status: 'CONCILIADO', entry_number: data.entry_number }
            : t
        )
      );

      setActiveModalTx(null);
      setEntryPreview(null);
      if (onRefreshData) onRefreshData();
    } catch (err: any) {
      onNotify('error', err.message || 'Error durante la conciliación');
    } finally {
      setReconciling(false);
    }
  };

  // Cálculos de KPIs
  const totalCount = transactions.length;
  const prevalidatedCount = transactions.filter((t) => t.status === 'PREVALIDADO').length;
  const suggestedCount = transactions.filter((t) => t.status === 'SUGERIDO').length;
  const reconciledCount = transactions.filter((t) => t.status === 'CONCILIADO').length;
  const pendingCount = transactions.filter((t) => t.status === 'PENDIENTE').length;

  // Filtrado de la tabla
  const filteredTransactions = transactions.filter((t) => {
    if (filterStatus !== 'ALL' && t.status !== filterStatus) return false;
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      const matchDesc = t.description?.toLowerCase().includes(term);
      const matchParty = t.matched_party?.toLowerCase().includes(term);
      const matchAccount = t.counterpart_account?.toLowerCase().includes(term);
      const matchInv = t.invoice_number?.toLowerCase().includes(term);
      return matchDesc || matchParty || matchAccount || matchInv;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* 1. Cabecera Principal y KPIs */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <Landmark className="w-5 h-5" />
            </span>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Conciliación Bancaria y Punteo Contable
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Emparejamiento inteligente de extractos bancarios contra facturas y sugerencias automáticas de contrapartidas.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadTransactions}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs text-slate-700 hover:text-slate-900 px-3 py-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-600' : ''}`} />
            Actualizar
          </button>
        </div>
      </div>

      {/* Grid de KPIs Rápidos */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* KPI: Total */}
        <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Total Movimientos</div>
            <div className="text-2xl font-bold text-slate-900 font-mono mt-0.5">{totalCount}</div>
          </div>
          <div className="p-2.5 bg-slate-50 text-slate-600 rounded-lg">
            <Scale className="w-5 h-5" />
          </div>
        </div>

        {/* KPI: Prevalidados */}
        <div
          onClick={() => setFilterStatus('PREVALIDADO')}
          className={`bg-white p-4 rounded-xl border cursor-pointer transition-all shadow-sm flex items-center justify-between ${
            filterStatus === 'PREVALIDADO'
              ? 'border-emerald-500 ring-2 ring-emerald-100'
              : 'border-slate-200/80 hover:border-emerald-300'
          }`}
        >
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-600">Prevalidados (Factura)</div>
            <div className="text-2xl font-bold text-emerald-700 font-mono mt-0.5">{prevalidatedCount}</div>
          </div>
          <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-lg">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        {/* KPI: Sugeridos */}
        <div
          onClick={() => setFilterStatus('SUGERIDO')}
          className={`bg-white p-4 rounded-xl border cursor-pointer transition-all shadow-sm flex items-center justify-between ${
            filterStatus === 'SUGERIDO'
              ? 'border-amber-500 ring-2 ring-amber-100'
              : 'border-slate-200/80 hover:border-amber-300'
          }`}
        >
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-amber-600">Sugeridos (Patrón)</div>
            <div className="text-2xl font-bold text-amber-700 font-mono mt-0.5">{suggestedCount}</div>
          </div>
          <div className="p-2.5 bg-amber-50 text-amber-600 rounded-lg">
            <Sparkles className="w-5 h-5" />
          </div>
        </div>

        {/* KPI: Conciliados */}
        <div
          onClick={() => setFilterStatus('CONCILIADO')}
          className={`bg-white p-4 rounded-xl border cursor-pointer transition-all shadow-sm flex items-center justify-between ${
            filterStatus === 'CONCILIADO'
              ? 'border-indigo-500 ring-2 ring-indigo-100'
              : 'border-slate-200/80 hover:border-indigo-300'
          }`}
        >
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-indigo-600">Conciliados (Diario)</div>
            <div className="text-2xl font-bold text-indigo-700 font-mono mt-0.5">{reconciledCount}</div>
          </div>
          <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-lg">
            <FileCheck2 className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* 2. Filtros y Búsqueda */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
          {[
            { id: 'ALL', label: 'Todos' },
            { id: 'PREVALIDADO', label: `Prevalidados (${prevalidatedCount})` },
            { id: 'SUGERIDO', label: `Sugeridos (${suggestedCount})` },
            { id: 'PENDIENTE', label: `Pendientes (${pendingCount})` },
            { id: 'CONCILIADO', label: `Conciliados (${reconciledCount})` },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterStatus(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                filterStatus === tab.id
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <div className="relative w-full md:w-64">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Buscar por concepto, NIF o cuenta..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          </div>

          <div className="flex items-center gap-1.5 text-xs text-slate-500 whitespace-nowrap">
            <span>Margen:</span>
            <select
              value={dateMargin}
              onChange={(e) => setDateMargin(Number(e.target.value))}
              className="px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs font-medium focus:outline-none"
            >
              <option value={3}>±3 días</option>
              <option value={5}>±5 días</option>
              <option value={10}>±10 días</option>
              <option value={30}>±30 días</option>
            </select>
          </div>
        </div>
      </div>

      {/* 3. Tabla Interactiva de Movimientos */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-400 text-xs flex flex-col items-center justify-center gap-2">
            <RefreshCw className="w-5 h-5 animate-spin text-indigo-600" />
            <span>Consultando extracto y aplicando algoritmos de conciliación...</span>
          </div>
        ) : filteredTransactions.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-xs">
            No se encontraron movimientos bancarios con el filtro seleccionado.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Fecha</th>
                  <th className="py-3 px-4">Concepto Bancario</th>
                  <th className="py-3 px-4 text-right">Importe (€)</th>
                  <th className="py-3 px-4 text-center">Estado</th>
                  <th className="py-3 px-4">Contrapartida Propuesta</th>
                  <th className="py-3 px-4 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredTransactions.map((tx, idx) => {
                  const txId = tx.transaction_id || tx.id || `tx-${idx}`;
                  const isPositive = tx.amount >= 0;
                  const formattedAmount = Intl.NumberFormat('es-ES', {
                    style: 'currency',
                    currency: 'EUR',
                  }).format(Math.abs(tx.amount));

                  return (
                    <tr key={txId} className="hover:bg-slate-50/70 transition-colors">
                      {/* Fecha */}
                      <td className="py-3.5 px-4 font-mono text-slate-700 whitespace-nowrap">
                        {tx.date
                          ? new Date(tx.date).toLocaleDateString('es-ES', {
                              day: '2-digit',
                              month: '2-digit',
                              year: 'numeric',
                            })
                          : 'S/F'}
                      </td>

                      {/* Concepto Bancario */}
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-slate-900 max-w-md truncate">
                          {tx.description}
                        </div>
                        {tx.notes && (
                          <div className="text-[11px] text-slate-400 mt-0.5 truncate">
                            {tx.notes}
                          </div>
                        )}
                      </td>

                      {/* Importe */}
                      <td className="py-3.5 px-4 text-right font-mono font-bold whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 ${
                            isPositive ? 'text-emerald-700' : 'text-rose-700'
                          }`}
                        >
                          {isPositive ? (
                            <ArrowUpRight className="w-3.5 h-3.5 text-emerald-600" />
                          ) : (
                            <ArrowDownLeft className="w-3.5 h-3.5 text-rose-600" />
                          )}
                          {isPositive ? `+${formattedAmount}` : `-${formattedAmount}`}
                        </span>
                      </td>

                      {/* Estado */}
                      <td className="py-3.5 px-4 text-center whitespace-nowrap">
                        {tx.status === 'PREVALIDADO' && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            PREVALIDADO
                          </span>
                        )}
                        {tx.status === 'SUGERIDO' && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                            <Sparkles className="w-3 h-3 text-amber-600" />
                            SUGERIDO
                          </span>
                        )}
                        {tx.status === 'PENDIENTE' && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
                            <Clock className="w-3 h-3 text-slate-500" />
                            PENDIENTE
                          </span>
                        )}
                        {tx.status === 'CONCILIADO' && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                            <FileCheck2 className="w-3 h-3 text-indigo-600" />
                            CONCILIADO {tx.entry_number ? `(#${tx.entry_number})` : ''}
                          </span>
                        )}
                      </td>

                      {/* Contrapartida Propuesta */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-slate-800 px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-[11px]">
                            {tx.counterpart_account || '55500000'}
                          </span>
                          <span className="text-slate-600 truncate max-w-[200px]">
                            {tx.matched_party || tx.suggested_concept || 'Partida pendiente'}
                          </span>
                        </div>
                      </td>

                      {/* Acciones */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          {tx.status === 'PREVALIDADO' && (
                            <button
                              onClick={() => handleConfirmReconciliation(tx)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-semibold shadow-sm transition-colors active:scale-95"
                              title="Emparejar y registrar directamente"
                            >
                              <Check className="w-3 h-3" />
                              Emparejar
                            </button>
                          )}

                          <button
                            onClick={() => handleOpenPreview(tx)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-semibold transition-colors"
                          >
                            <Eye className="w-3 h-3" />
                            Ver Asiento
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 4. Modal Interactivo: Previsualización de Asiento Contable */}
      {activeModalTx && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-2xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-2.5">
                <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                  <Landmark className="w-5 h-5" />
                </span>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Previsualización de Asiento Contable de Banco
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Verificación de partida doble (PGC) antes de asentar en el Libro Diario.
                  </p>
                </div>
              </div>

              <button
                onClick={() => {
                  setActiveModalTx(null);
                  setEntryPreview(null);
                }}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-5">
              {/* Resumen del Movimiento */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 p-3.5 bg-slate-50 rounded-xl border border-slate-200/70 text-xs">
                <div>
                  <div className="text-slate-400 font-medium">Concepto Bancario</div>
                  <div className="font-bold text-slate-800 mt-0.5 truncate">{activeModalTx.description}</div>
                </div>
                <div>
                  <div className="text-slate-400 font-medium">Fecha Operación</div>
                  <div className="font-mono text-slate-700 mt-0.5">{activeModalTx.date || 'S/F'}</div>
                </div>
                <div>
                  <div className="text-slate-400 font-medium">Importe Neto</div>
                  <div className="font-mono font-bold text-slate-900 mt-0.5">
                    {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
                      Math.abs(activeModalTx.amount)
                    )}
                  </div>
                </div>
              </div>

              {/* Ajuste de Contrapartida */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Cuenta Bancaria (572)
                  </label>
                  <input
                    type="text"
                    value={editBankAccount}
                    onChange={(e) => setEditBankAccount(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs font-mono font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Subcuenta Contrapartida (400 / 410 / 430 / 6XX)
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={editCounterpart}
                      onChange={(e) => setEditCounterpart(e.target.value)}
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs font-mono font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                    />
                    <button
                      onClick={() => handleRecalculatePreview(editCounterpart)}
                      disabled={loadingPreview}
                      className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors"
                    >
                      Recalcular
                    </button>
                  </div>
                </div>
              </div>

              {/* Detalle de Partida Doble */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                    <Scale className="w-3.5 h-3.5 text-indigo-600" />
                    Apuntes Contables del Asiento
                  </span>

                  {entryPreview?.is_balanced && (
                    <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3 text-emerald-600" />
                      Partida Doble Cuadrada (0,00 €)
                    </span>
                  )}
                </div>

                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200">
                      <tr>
                        <th className="py-2.5 px-3">Subcuenta</th>
                        <th className="py-2.5 px-3">Concepto</th>
                        <th className="py-2.5 px-3 text-right">Debe (€)</th>
                        <th className="py-2.5 px-3 text-right">Haber (€)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {loadingPreview ? (
                        <tr>
                          <td colSpan={4} className="py-6 text-center text-slate-400">
                            <RefreshCw className="w-4 h-4 animate-spin mx-auto text-indigo-600" />
                          </td>
                        </tr>
                      ) : entryPreview?.lines ? (
                        entryPreview.lines.map((line, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/50">
                            <td className="py-2.5 px-3 font-mono font-bold text-slate-800">
                              {line.subcuenta}
                            </td>
                            <td className="py-2.5 px-3 text-slate-600">{line.concepto}</td>
                            <td className="py-2.5 px-3 text-right font-mono font-medium">
                              {line.debe > 0
                                ? Intl.NumberFormat('es-ES', {
                                    style: 'currency',
                                    currency: 'EUR',
                                  }).format(line.debe)
                                : '-'}
                            </td>
                            <td className="py-2.5 px-3 text-right font-mono font-medium">
                              {line.haber > 0
                                ? Intl.NumberFormat('es-ES', {
                                    style: 'currency',
                                    currency: 'EUR',
                                  }).format(line.haber)
                                : '-'}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={4} className="py-4 text-center text-slate-400">
                            Sin previsualización generada.
                          </td>
                        </tr>
                      )}
                    </tbody>
                    {entryPreview && (
                      <tfoot className="bg-slate-50 font-bold border-t border-slate-200">
                        <tr>
                          <td colSpan={2} className="py-2.5 px-3 text-right text-slate-600">
                            Totales:
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-slate-900">
                            {Intl.NumberFormat('es-ES', {
                              style: 'currency',
                              currency: 'EUR',
                            }).format(entryPreview.total_debe)}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-slate-900">
                            {Intl.NumberFormat('es-ES', {
                              style: 'currency',
                              currency: 'EUR',
                            }).format(entryPreview.total_haber)}
                          </td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
              <button
                onClick={() => {
                  setActiveModalTx(null);
                  setEntryPreview(null);
                }}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-200 transition-colors"
              >
                Cancelar
              </button>

              <button
                onClick={() => handleConfirmReconciliation(activeModalTx, editCounterpart)}
                disabled={reconciling || loadingPreview || !entryPreview?.is_balanced}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold text-white shadow-sm transition-all ${
                  reconciling || loadingPreview || !entryPreview?.is_balanced
                    ? 'bg-slate-300 cursor-not-allowed text-slate-500'
                    : 'bg-indigo-600 hover:bg-indigo-700 active:scale-95 shadow-indigo-600/20'
                }`}
              >
                {reconciling ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Contabilizando en Diario...
                  </>
                ) : (
                  <>
                    <FileCheck2 className="w-4 h-4" />
                    Confirmar y Contabilizar Asiento
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

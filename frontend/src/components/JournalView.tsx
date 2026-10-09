'use client';

import React, { useState, useEffect } from 'react';
import { Company, JournalEntryGroup, LedgerResponse, TrialBalanceResponse } from '@/types';
import {
  fetchJournalEntries,
  fetchAccountLedger,
  fetchTrialBalance,
  reverseJournalEntry,
  closeFiscalYear,
  reopenFiscalYear,
  getTrialBalanceCsvUrl,
} from '@/lib/api';
import {
  BookOpen,
  Search,
  CheckCircle2,
  AlertTriangle,
  Scale,
  Calendar,
  Layers,
  ArrowRight,
  FileSpreadsheet,
  Download,
  Filter,
  RotateCcw,
  Lock,
  Unlock,
  ChevronLeft,
  ChevronRight,
  FileText,
  ExternalLink,
  ShieldCheck,
  Building2,
  PieChart,
} from 'lucide-react';

interface JournalViewProps {
  company: Company;
  onNotify: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
}

export const JournalView: React.FC<JournalViewProps> = ({ company, onNotify }) => {
  const [subTab, setSubTab] = useState<'journal' | 'ledger' | 'trial-balance'>('journal');
  const [loading, setLoading] = useState<boolean>(true);

  // Estados Libro Diario
  const [journalEntries, setJournalEntries] = useState<JournalEntryGroup[]>([]);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [selectedExported, setSelectedExported] = useState<string>('ALL');
  const [selectedFiscalYear, setSelectedFiscalYear] = useState<number | undefined>(undefined);
  const [entryNumberFilter, setEntryNumberFilter] = useState<number | undefined>(undefined);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalAsientos, setTotalAsientos] = useState<number>(0);
  const [totalGeneralDebe, setTotalGeneralDebe] = useState<number>(0);
  const [totalGeneralHaber, setTotalGeneralHaber] = useState<number>(0);
  const [cuadreGeneral, setCuadreGeneral] = useState<boolean>(true);
  const [fechaCierreContable, setFechaCierreContable] = useState<string | null>(null);

  // Modal de Reversión de Asiento
  const [reversingEntry, setReversingEntry] = useState<JournalEntryGroup | null>(null);
  const [reversalReason, setReversalReason] = useState<string>('');
  const [reversalDate, setReversalDate] = useState<string>('');
  const [submittingReversal, setSubmittingReversal] = useState<boolean>(false);

  // Modal de Cierre de Ejercicio
  const [showCloseYearModal, setShowCloseYearModal] = useState<boolean>(false);
  const [yearToClose, setYearToClose] = useState<number>(new Date().getFullYear());
  const [closingDate, setClosingDate] = useState<string>(`${new Date().getFullYear()}-12-31`);
  const [submittingCloseYear, setSubmittingCloseYear] = useState<boolean>(false);

  // Estados Libro Mayor
  const [ledgerSubcuenta, setLedgerSubcuenta] = useState<string>('430000001');
  const [ledgerData, setLedgerData] = useState<LedgerResponse | null>(null);

  // Estados Balance de Sumas y Saldos
  const [trialBalanceData, setTrialBalanceData] = useState<TrialBalanceResponse | null>(null);

  // Cargar Libro Diario
  const loadJournal = async () => {
    setLoading(true);
    try {
      const res = await fetchJournalEntries(company.id, {
        search: searchTerm.trim() || undefined,
        entryNumber: entryNumberFilter,
        status: selectedStatus !== 'ALL' ? selectedStatus : undefined,
        exported: selectedExported === 'ALL' ? undefined : selectedExported === 'true',
        fiscalYear: selectedFiscalYear,
        page,
        pageSize: 50,
      });
      setJournalEntries(res.asientos || []);
      setTotalAsientos(res.total_asientos || 0);
      setTotalPages(res.total_pages || 1);
      setTotalGeneralDebe(res.total_general_debe || 0);
      setTotalGeneralHaber(res.total_general_haber || 0);
      setCuadreGeneral(res.cuadre_general ?? true);
      setFechaCierreContable(res.fecha_cierre_contable || null);
    } catch {
      onNotify('error', 'Error al cargar el Libro Diario');
    } finally {
      setLoading(false);
    }
  };

  // Cargar Extracto de Mayor
  const loadLedger = async (subcta: string) => {
    if (!subcta) return;
    setLoading(true);
    try {
      const res = await fetchAccountLedger(company.id, subcta.trim(), {
        fiscalYear: selectedFiscalYear,
      });
      setLedgerData(res);
    } catch {
      onNotify('error', `Error al cargar extracto de mayor para la cuenta ${subcta}`);
    } finally {
      setLoading(false);
    }
  };

  // Cargar Balance de Sumas y Saldos
  const loadTrialBalance = async () => {
    setLoading(true);
    try {
      const res = await fetchTrialBalance(company.id, {
        fiscalYear: selectedFiscalYear,
      });
      setTrialBalanceData(res);
    } catch {
      onNotify('error', 'Error al calcular el balance de sumas y saldos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (subTab === 'journal') {
      loadJournal();
    } else if (subTab === 'ledger') {
      loadLedger(ledgerSubcuenta);
    } else if (subTab === 'trial-balance') {
      loadTrialBalance();
    }
  }, [company.id, subTab, page, selectedStatus, selectedExported, selectedFiscalYear, entryNumberFilter]);

  // Manejar Reversión Auditable
  const handleExecuteReversal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reversingEntry || reversalReason.trim().length < 5) return;
    setSubmittingReversal(true);
    try {
      const res = await reverseJournalEntry(company.id, reversingEntry.entry_number, {
        reason: reversalReason.trim(),
        reversal_date: reversalDate || undefined,
      });
      onNotify(
        'success',
        `Asiento #${reversingEntry.entry_number} revertido mediante el Asiento de anulación #${res.reversal_entry_number}.`,
        'Reversión Contable'
      );
      setReversingEntry(null);
      setReversalReason('');
      setReversalDate('');
      await loadJournal();
    } catch (err: any) {
      onNotify('error', err.message || 'Error al revertir el asiento');
    } finally {
      setSubmittingReversal(false);
    }
  };

  // Manejar Cierre de Ejercicio
  const handleExecuteCloseYear = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingCloseYear(true);
    try {
      const res = await closeFiscalYear(company.id, {
        year: yearToClose,
        closing_date: closingDate || undefined,
      });
      onNotify(
        'success',
        `Ejercicio ${yearToClose} cerrado con éxito. Asiento de regularización generado contra cuenta ${res.cuenta_resultado} (${res.tipo_resultado}: ${res.resultado_neto.toFixed(2)} €).`,
        'Cierre de Ejercicio'
      );
      setShowCloseYearModal(false);
      await loadJournal();
    } catch (err: any) {
      onNotify('error', err.message || 'Error al cerrar el ejercicio');
    } finally {
      setSubmittingCloseYear(false);
    }
  };

  // Salto desde el Mayor al Asiento en el Diario
  const jumpToJournalEntry = (num: number) => {
    setEntryNumberFilter(num);
    setSubTab('journal');
  };

  return (
    <div className="space-y-6">
      {/* Cabecera y Selector de Pestaña Contable */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <BookOpen className="w-5 h-5" />
            </span>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
                Libros Contables y Registros Oficiales PGC
                {fechaCierreContable && (
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 inline-flex items-center gap-1">
                    <Lock className="w-3 h-3 text-amber-600" />
                    Cierre: {new Date(fechaCierreContable).toLocaleDateString('es-ES')}
                  </span>
                )}
              </h1>
              <p className="text-xs text-slate-500 mt-1">
                Libro Diario cronológico en partida doble, extracto de Libro Mayor por subcuenta individual
                y Balance de Sumas y Saldos estructurado conforme al PGC de PYMES (RD 1515/2007).
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Botón Cierre Contable */}
          <button
            onClick={() => setShowCloseYearModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition"
          >
            <Lock className="w-3.5 h-3.5" />
            Cierre Ejercicio
          </button>

          {/* Selector de Subpestañas */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs font-medium">
            <button
              onClick={() => {
                setSubTab('journal');
                setEntryNumberFilter(undefined);
              }}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                subTab === 'journal'
                  ? 'bg-white text-slate-900 font-bold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Libro Diario
            </button>
            <button
              onClick={() => setSubTab('ledger')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                subTab === 'ledger'
                  ? 'bg-white text-slate-900 font-bold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Libro Mayor
            </button>
            <button
              onClick={() => setSubTab('trial-balance')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                subTab === 'trial-balance'
                  ? 'bg-white text-slate-900 font-bold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Balance Sumas y Saldos
            </button>
          </div>
        </div>
      </div>

      {/* 1. LIBRO DIARIO */}
      {subTab === 'journal' && (
        <div className="space-y-4">
          {/* Barra de Filtros y Parámetros */}
          <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex flex-wrap items-center gap-2 flex-1">
              {/* Buscador de texto */}
              <div className="relative w-64">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && loadJournal()}
                  placeholder="Subcuenta, concepto, doc..."
                  className="w-full text-xs pl-8 pr-3 py-1.5 border border-slate-200 rounded-lg outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
                />
              </div>

              {/* Filtro Ejercicio Fiscal */}
              <select
                value={selectedFiscalYear || ''}
                onChange={(e) => {
                  setSelectedFiscalYear(e.target.value ? Number(e.target.value) : undefined);
                  setPage(1);
                }}
                className="px-2.5 py-1.5 border border-slate-200 rounded-lg bg-white text-slate-700 outline-none"
              >
                <option value="">Todos los Ejercicios</option>
                <option value="2026">Ejercicio 2026</option>
                <option value="2025">Ejercicio 2025</option>
                <option value="2024">Ejercicio 2024</option>
              </select>

              {/* Filtro Estado Contable */}
              <select
                value={selectedStatus}
                onChange={(e) => {
                  setSelectedStatus(e.target.value);
                  setPage(1);
                }}
                className="px-2.5 py-1.5 border border-slate-200 rounded-lg bg-white text-slate-700 outline-none"
              >
                <option value="ALL">Todos los Estados</option>
                <option value="contabilizado">Contabilizados</option>
                <option value="revertido">Revertidos / Anulados</option>
                <option value="borrador">Borradores</option>
              </select>

              {/* Filtro Estado de Exportación */}
              <select
                value={selectedExported}
                onChange={(e) => {
                  setSelectedExported(e.target.value);
                  setPage(1);
                }}
                className="px-2.5 py-1.5 border border-slate-200 rounded-lg bg-white text-slate-700 outline-none"
              >
                <option value="ALL">Exportación ERP: Todos</option>
                <option value="true">Exportados a ERP</option>
                <option value="false">Pendientes de Exportar</option>
              </select>

              {entryNumberFilter && (
                <button
                  onClick={() => setEntryNumberFilter(undefined)}
                  className="px-2 py-1 bg-indigo-50 text-indigo-700 rounded-lg font-mono text-[11px] font-bold border border-indigo-200 flex items-center gap-1"
                >
                  Asiento #{entryNumberFilter} <span className="text-slate-400">×</span>
                </button>
              )}
            </div>

            {/* Totales y Cuadre de Partida Doble */}
            <div className="flex items-center gap-3 font-mono text-xs">
              <div className="text-slate-500">
                Total Asientos: <strong className="text-slate-900">{totalAsientos}</strong>
              </div>
              <div className="text-slate-500">
                Debe: <strong className="text-indigo-700">{totalGeneralDebe.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €</strong>
              </div>
              <div className="text-slate-500">
                Haber: <strong className="text-indigo-700">{totalGeneralHaber.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €</strong>
              </div>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  cuadreGeneral
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-rose-50 text-rose-700 border-rose-200'
                }`}
              >
                {cuadreGeneral ? 'Partida Doble Cuadrada (0,00 €)' : 'Descuadre Detectado'}
              </span>
            </div>
          </div>

          {/* Listado de Asientos Contables */}
          {journalEntries.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-400 text-xs">
              No se han encontrado asientos contables para los filtros seleccionados.
            </div>
          ) : (
            <div className="space-y-4">
              {journalEntries.map((asiento) => (
                <div
                  key={`${asiento.fecha}_${asiento.entry_number}`}
                  className={`bg-white rounded-xl border shadow-xs overflow-hidden transition ${
                    asiento.status === 'revertido'
                      ? 'border-amber-200 bg-amber-50/20'
                      : 'border-slate-200'
                  }`}
                >
                  {/* Cabecera del Asiento */}
                  <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-200 flex flex-wrap items-center justify-between text-xs gap-2">
                    <div className="flex items-center gap-3">
                      <span className="font-bold font-mono text-indigo-700 bg-indigo-50 border border-indigo-200 px-2.5 py-0.5 rounded">
                        Asiento #{asiento.entry_number}
                      </span>
                      <span className="text-slate-600 font-mono flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-slate-400" />
                        {new Date(asiento.fecha).toLocaleDateString('es-ES')}
                      </span>
                      {asiento.documento && (
                        <span className="text-slate-500 font-mono bg-white px-2 py-0.5 rounded border border-slate-200">
                          Doc: {asiento.documento}
                        </span>
                      )}
                      {asiento.is_reversal && (
                        <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 text-[10px] font-bold">
                          Reversión de #{asiento.reversal_of_entry_number}
                        </span>
                      )}
                      {asiento.is_closed_period && (
                        <span className="px-2 py-0.5 rounded bg-slate-200 text-slate-700 text-[10px] font-semibold flex items-center gap-1">
                          <Lock className="w-3 h-3" /> Ejercicio Cerrado
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {/* Estado Contable */}
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          asiento.status === 'revertido'
                            ? 'bg-amber-100 text-amber-800 border border-amber-300'
                            : asiento.status === 'borrador'
                            ? 'bg-slate-100 text-slate-600'
                            : 'bg-emerald-100 text-emerald-800'
                        }`}
                      >
                        {asiento.status || 'contabilizado'}
                      </span>

                      {/* Exportado a ERP */}
                      {asiento.exported_to_erp ? (
                        <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-bold">
                          Exportado a ERP
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px] font-medium">
                          Pendiente exportar
                        </span>
                      )}

                      {/* Cuadre */}
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          asiento.is_balanced
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {asiento.is_balanced ? 'Cuadrado' : 'Descuadrado'}
                      </span>

                      {/* Botón Revertir Asiento */}
                      {asiento.status !== 'revertido' && !asiento.is_closed_period && (
                        <button
                          onClick={() => setReversingEntry(asiento)}
                          title="Revertir este asiento contable de forma auditable"
                          className="px-2 py-1 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded text-[11px] font-medium transition flex items-center gap-1"
                        >
                          <RotateCcw className="w-3 h-3" />
                          Revertir
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Tabla de Apuntes (Partida Doble) */}
                  <table className="w-full text-xs">
                    <thead className="text-[11px] text-slate-400 border-b border-slate-100 bg-slate-50/50">
                      <tr>
                        <th className="py-2 px-4 text-left w-36">Subcuenta</th>
                        <th className="py-2 px-4 text-left">Concepto</th>
                        <th className="py-2 px-4 text-right w-36">Debe (€)</th>
                        <th className="py-2 px-4 text-right w-36">Haber (€)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50 font-mono">
                      {asiento.lines.map((l) => (
                        <tr key={l.id} className="hover:bg-slate-50/50">
                          <td className="py-2 px-4 font-bold text-slate-800 flex items-center gap-1.5">
                            <span
                              onClick={() => {
                                setLedgerSubcuenta(l.subcuenta);
                                setSubTab('ledger');
                              }}
                              className="cursor-pointer hover:underline hover:text-indigo-600"
                              title="Ver extracto de Mayor"
                            >
                              {l.subcuenta}
                            </span>
                          </td>
                          <td className="py-2 px-4 font-sans text-slate-600">{l.concepto}</td>
                          <td className="py-2 px-4 text-right text-slate-900">
                            {l.debe > 0
                              ? l.debe.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })
                              : '-'}
                          </td>
                          <td className="py-2 px-4 text-right text-slate-900">
                            {l.haber > 0
                              ? l.haber.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })
                              : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-slate-50/70 font-mono font-bold text-xs border-t border-slate-200">
                      <tr>
                        <td colSpan={2} className="py-2 px-4 text-right font-sans text-slate-500">
                          Totales Asiento #{asiento.entry_number}:
                        </td>
                        <td className="py-2 px-4 text-right text-indigo-700">
                          {asiento.total_debe.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                        </td>
                        <td className="py-2 px-4 text-right text-indigo-700">
                          {asiento.total_haber.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ))}

              {/* Controles de Paginación */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between bg-white px-4 py-3 rounded-xl border border-slate-200 text-xs">
                  <span className="text-slate-500">
                    Página <strong>{page}</strong> de <strong>{totalPages}</strong> ({totalAsientos} asientos)
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="px-3 py-1.5 border rounded-lg hover:bg-slate-50 disabled:opacity-40 transition flex items-center gap-1"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" /> Anterior
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages}
                      className="px-3 py-1.5 border rounded-lg hover:bg-slate-50 disabled:opacity-40 transition flex items-center gap-1"
                    >
                      Siguiente <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 2. LIBRO MAYOR */}
      {subTab === 'ledger' && (
        <div className="space-y-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3 w-full md:w-auto">
              <label className="text-xs font-bold text-slate-700 whitespace-nowrap">
                Subcuenta a Consultar:
              </label>
              <input
                type="text"
                value={ledgerSubcuenta}
                onChange={(e) => setLedgerSubcuenta(e.target.value.trim())}
                onKeyDown={(e) => e.key === 'Enter' && loadLedger(ledgerSubcuenta)}
                placeholder="430000001, 700000000..."
                className="font-mono text-xs px-3 py-1.5 border rounded-lg outline-none focus:ring-1 focus:ring-indigo-500 w-44"
              />
              <button
                onClick={() => loadLedger(ledgerSubcuenta)}
                className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700 transition"
              >
                Consultar Mayor
              </button>
            </div>

            {ledgerData && (
              <div className="flex items-center gap-4 text-xs font-mono">
                <div>
                  <span className="text-slate-400">Total Debe:</span>{' '}
                  <strong className="text-slate-800">
                    {ledgerData.total_debe.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-400">Total Haber:</span>{' '}
                  <strong className="text-slate-800">
                    {ledgerData.total_haber.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-400">Saldo Final:</span>{' '}
                  <strong
                    className={
                      ledgerData.tipo_saldo === 'DEUDOR'
                        ? 'text-emerald-700 font-bold'
                        : ledgerData.tipo_saldo === 'ACREEDOR'
                        ? 'text-indigo-700 font-bold'
                        : 'text-slate-600'
                    }
                  >
                    {ledgerData.saldo_final.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}{' '}
                    ({ledgerData.tipo_saldo})
                  </strong>
                </div>
              </div>
            )}
          </div>

          {ledgerData && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-800 font-mono">
                    Extracto de Mayor: {ledgerData.subcuenta}
                  </h3>
                  <p className="text-xs text-slate-500">{ledgerData.descripcion} • Naturaleza: {ledgerData.naturaleza_esperada}</p>
                </div>
                <div className="text-xs text-slate-500 font-mono">
                  Saldo Inicial:{' '}
                  <strong>
                    {(ledgerData.debe_inicial - ledgerData.haber_inicial).toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                  </strong>
                </div>
              </div>

              {ledgerData.movimientos.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-xs">
                  No hay movimientos registrados para esta subcuenta en el periodo.
                </div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-4 text-left">Fecha</th>
                      <th className="py-2.5 px-4 text-left">Asiento</th>
                      <th className="py-2.5 px-4 text-left">Concepto</th>
                      <th className="py-2.5 px-4 text-left">Documento</th>
                      <th className="py-2.5 px-4 text-right">Debe (€)</th>
                      <th className="py-2.5 px-4 text-right">Haber (€)</th>
                      <th className="py-2.5 px-4 text-right">Saldo Progresivo</th>
                      <th className="py-2.5 px-4 text-center">Acción</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {ledgerData.movimientos.map((m) => (
                      <tr key={m.id} className="hover:bg-slate-50">
                        <td className="py-2.5 px-4 text-slate-600">
                          {new Date(m.fecha).toLocaleDateString('es-ES')}
                        </td>
                        <td className="py-2.5 px-4 font-bold text-slate-700">#{m.entry_number}</td>
                        <td className="py-2.5 px-4 font-sans text-slate-800">{m.concepto}</td>
                        <td className="py-2.5 px-4 text-slate-400">{m.documento || '-'}</td>
                        <td className="py-2.5 px-4 text-right text-slate-900">
                          {m.debe > 0 ? m.debe.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' }) : '-'}
                        </td>
                        <td className="py-2.5 px-4 text-right text-slate-900">
                          {m.haber > 0 ? m.haber.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' }) : '-'}
                        </td>
                        <td className="py-2.5 px-4 text-right font-bold text-slate-900">
                          {m.saldo_progresivo.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}{' '}
                          <span className="text-[10px] text-slate-400 font-normal">{m.signo}</span>
                        </td>
                        <td className="py-2.5 px-4 text-center">
                          <button
                            onClick={() => jumpToJournalEntry(m.entry_number)}
                            title="Navegar al asiento completo en el Diario"
                            className="px-2 py-0.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded text-[11px] font-sans font-medium transition inline-flex items-center gap-1"
                          >
                            <ArrowRight className="w-3 h-3" /> Ver Asiento
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

      {/* 3. BALANCE DE SUMAS Y SALDOS */}
      {subTab === 'trial-balance' && (
        <div className="space-y-4">
          {trialBalanceData && (
            <div className="space-y-4">
              {/* Resumen Oficial por Grupos del PGC */}
              {trialBalanceData.grupos_resumen && trialBalanceData.grupos_resumen.length > 0 && (
                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                      <PieChart className="w-4 h-4 text-indigo-600" />
                      Estructura por Grupos del Plan General Contable (PGC PYMES)
                    </h3>
                    <a
                      href={getTrialBalanceCsvUrl(company.id, selectedFiscalYear)}
                      download
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition shadow-xs"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Descargar Excel / CSV
                    </a>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {trialBalanceData.grupos_resumen.map((g) => (
                      <div
                        key={g.grupo}
                        className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between font-bold text-slate-800">
                          <span>{g.nombre}</span>
                          <span className="text-[10px] bg-white px-1.5 py-0.5 rounded border text-slate-500 font-mono">
                            {g.cuentas_activas} ctas.
                          </span>
                        </div>
                        <div className="flex items-center justify-between font-mono text-[11px] text-slate-600 pt-1">
                          <span>Debe: {g.suma_debe.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}</span>
                          <span>Haber: {g.suma_haber.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}</span>
                        </div>
                        <div className="flex items-center justify-between font-mono text-[11px] font-bold pt-0.5 border-t border-slate-200">
                          <span className="text-slate-400">Saldo:</span>
                          <span className={g.saldo_deudor > 0 ? 'text-emerald-700' : 'text-indigo-700'}>
                            {g.saldo_deudor > 0
                              ? `${g.saldo_deudor.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })} (D)`
                              : `${g.saldo_acreedor.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })} (H)`}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tabla Detallada de Comprobación */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-800">
                      Balance de Comprobación de Sumas y Saldos Detallado
                    </h3>
                    <p className="text-xs text-slate-500">
                      Verificación de partida doble: Suma Debe = Suma Haber • Saldo Deudor = Saldo Acreedor
                    </p>
                  </div>
                  <div
                    className={`px-3 py-1 rounded-lg text-xs font-bold border ${
                      trialBalanceData.totales.cuadrado
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-rose-50 text-rose-700 border-rose-200'
                    }`}
                  >
                    {trialBalanceData.totales.cuadrado
                      ? 'Balance Totalmente Cuadrado'
                      : 'Descuadre Detectado'}
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 uppercase tracking-wider">
                      <tr>
                        <th className="py-2.5 px-4 text-left">Cuenta</th>
                        <th className="py-2.5 px-4 text-left">Descripción</th>
                        <th className="py-2.5 px-4 text-right">Suma Debe</th>
                        <th className="py-2.5 px-4 text-right">Suma Haber</th>
                        <th className="py-2.5 px-4 text-right">Saldo Deudor</th>
                        <th className="py-2.5 px-4 text-right">Saldo Acreedor</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono">
                      {trialBalanceData.items.map((it) => (
                        <tr key={it.codigo} className="hover:bg-slate-50">
                          <td className="py-2 px-4 font-bold text-slate-900">{it.codigo}</td>
                          <td className="py-2 px-4 font-sans text-slate-700">{it.descripcion}</td>
                          <td className="py-2 px-4 text-right text-slate-900">
                            {it.suma_debe.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                          </td>
                          <td className="py-2 px-4 text-right text-slate-900">
                            {it.suma_haber.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                          </td>
                          <td className="py-2 px-4 text-right text-emerald-700 font-semibold">
                            {it.saldo_deudor > 0
                              ? it.saldo_deudor.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })
                              : '-'}
                          </td>
                          <td className="py-2 px-4 text-right text-indigo-700 font-semibold">
                            {it.saldo_acreedor > 0
                              ? it.saldo_acreedor.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })
                              : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-slate-100 font-mono font-bold text-xs border-t-2 border-slate-300">
                      <tr>
                        <td colSpan={2} className="py-3 px-4 font-sans text-slate-800">
                          TOTALES GENERALES
                        </td>
                        <td className="py-3 px-4 text-right text-slate-900">
                          {trialBalanceData.totales.suma_debe.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                        </td>
                        <td className="py-3 px-4 text-right text-slate-900">
                          {trialBalanceData.totales.suma_haber.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                        </td>
                        <td className="py-3 px-4 text-right text-emerald-800">
                          {trialBalanceData.totales.saldo_deudor.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                        </td>
                        <td className="py-3 px-4 text-right text-indigo-800">
                          {trialBalanceData.totales.saldo_acreedor.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modal de Reversión Auditable */}
      {reversingEntry && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl overflow-hidden border border-slate-200">
            <div className="px-6 py-4 bg-amber-50 border-b border-amber-200 flex items-center justify-between">
              <div className="flex items-center gap-2 text-amber-900 font-bold text-sm">
                <RotateCcw className="w-4 h-4 text-amber-600" />
                Revertir Asiento #{reversingEntry.entry_number}
              </div>
              <button
                type="button"
                onClick={() => setReversingEntry(null)}
                className="text-slate-400 hover:text-slate-700"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleExecuteReversal} className="p-6 space-y-4 text-xs">
              <p className="text-slate-600 leading-relaxed">
                Esta acción creará un <strong>contra-asiento auditable</strong> con las mismas subcuentas invirtiendo
                estrictamente Debe y Haber. El asiento original quedará marcado como <em>revertido</em>.
              </p>

              <div>
                <label className="block font-bold text-slate-700 mb-1">
                  Motivo de la Reversión Contable * (Mínimo 5 caracteres)
                </label>
                <textarea
                  required
                  rows={3}
                  value={reversalReason}
                  onChange={(e) => setReversalReason(e.target.value)}
                  placeholder="Ej. Anulación por rectificativa recibida, corrección de cuenta de gasto errónea..."
                  className="w-full p-2.5 border border-slate-300 rounded-xl outline-none focus:ring-1 focus:ring-amber-500 text-xs"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">
                  Fecha Contable de la Reversión (Opcional, por defecto hoy)
                </label>
                <input
                  type="date"
                  value={reversalDate}
                  onChange={(e) => setReversalDate(e.target.value)}
                  className="w-full p-2 border border-slate-300 rounded-xl outline-none text-xs"
                />
              </div>

              <div className="pt-2 border-t flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setReversingEntry(null)}
                  className="px-4 py-2 border rounded-xl text-slate-600 hover:bg-slate-50 font-medium"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submittingReversal || reversalReason.trim().length < 5}
                  className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-bold disabled:opacity-50 transition shadow-xs"
                >
                  {submittingReversal ? 'Revirtiendo...' : 'Confirmar Reversión'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal de Cierre de Ejercicio */}
      {showCloseYearModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl overflow-hidden border border-slate-200">
            <div className="px-6 py-4 bg-indigo-50 border-b border-indigo-200 flex items-center justify-between">
              <div className="flex items-center gap-2 text-indigo-900 font-bold text-sm">
                <Lock className="w-4 h-4 text-indigo-600" />
                Cierre y Regularización de Ejercicio
              </div>
              <button
                type="button"
                onClick={() => setShowCloseYearModal(false)}
                className="text-slate-400 hover:text-slate-700"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleExecuteCloseYear} className="p-6 space-y-4 text-xs">
              <p className="text-slate-600 leading-relaxed">
                Este proceso regularizará automáticamente todas las cuentas de gestión (Grupos 6 de gastos y 7 de ingresos),
                saldando sus importes contra la cuenta oficial <strong>129000000 (Resultado del Ejercicio)</strong> y
                bloqueará nuevas contabilizaciones para fechas anteriores o iguales al cierre.
              </p>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Ejercicio a Cerrar</label>
                  <input
                    type="number"
                    required
                    value={yearToClose}
                    onChange={(e) => {
                      const yr = Number(e.target.value);
                      setYearToClose(yr);
                      setClosingDate(`${yr}-12-31`);
                    }}
                    className="w-full p-2 border border-slate-300 rounded-xl font-mono text-xs outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Fecha de Cierre</label>
                  <input
                    type="date"
                    required
                    value={closingDate}
                    onChange={(e) => setClosingDate(e.target.value)}
                    className="w-full p-2 border border-slate-300 rounded-xl font-mono text-xs outline-none"
                  />
                </div>
              </div>

              <div className="pt-2 border-t flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCloseYearModal(false)}
                  className="px-4 py-2 border rounded-xl text-slate-600 hover:bg-slate-50 font-medium"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submittingCloseYear}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold disabled:opacity-50 transition shadow-xs"
                >
                  {submittingCloseYear ? 'Cerrando Ejercicio...' : 'Ejecutar Cierre Contable'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

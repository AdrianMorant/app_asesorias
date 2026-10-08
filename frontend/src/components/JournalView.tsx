'use client';

import React, { useState, useEffect } from 'react';
import { Company, JournalEntryGroup, LedgerResponse, TrialBalanceResponse } from '@/types';
import { fetchJournalEntries, fetchAccountLedger, fetchTrialBalance } from '@/lib/api';
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

  // Estados Libro Mayor
  const [ledgerSubcuenta, setLedgerSubcuenta] = useState<string>('430000001');
  const [ledgerData, setLedgerData] = useState<LedgerResponse | null>(null);

  // Estados Balance de Sumas y Saldos
  const [trialBalanceData, setTrialBalanceData] = useState<TrialBalanceResponse | null>(null);

  // Cargar Libro Diario
  const loadJournal = async () => {
    setLoading(true);
    try {
      const res = await fetchJournalEntries(company.id, { search: searchTerm });
      setJournalEntries(res.asientos || []);
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
      const res = await fetchAccountLedger(company.id, subcta);
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
      const res = await fetchTrialBalance(company.id);
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
  }, [company.id, subTab]);

  return (
    <div className="space-y-6">
      {/* Cabecera y Selector de Pestaña Contable */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <BookOpen className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Libros Contables y Registros Oficiales PGC
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Libro Diario cronológico en partida doble, extracto de Libro Mayor por subcuenta individual
            y Balance de Sumas y Saldos comprobado conforme a los principios contables españoles.
          </p>
        </div>

        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs font-medium">
          <button
            onClick={() => setSubTab('journal')}
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

      {/* 1. LIBRO DIARIO */}
      {subTab === 'journal' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="relative w-full md:w-80">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && loadJournal()}
                placeholder="Buscar por subcuenta, concepto o doc..."
                className="w-full text-xs pl-8 pr-3 py-2 border border-slate-200 rounded-lg outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
              />
            </div>
            <div className="text-xs text-slate-500 font-mono">
              Total Asientos:{' '}
              <strong className="text-slate-800">{journalEntries.length}</strong>
            </div>
          </div>

          {journalEntries.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-400 text-xs">
              No se han encontrado asientos contables registrados para esta empresa.
            </div>
          ) : (
            <div className="space-y-4">
              {journalEntries.map((asiento, idx) => (
                <div
                  key={idx}
                  className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden"
                >
                  {/* Cabecera del Asiento */}
                  <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-200 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-3">
                      <span className="font-bold font-mono text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded">
                        Asiento #{asiento.entry_number}
                      </span>
                      <span className="text-slate-500 font-mono">
                        {new Date(asiento.fecha).toLocaleDateString('es-ES')}
                      </span>
                      {asiento.documento && (
                        <span className="text-slate-400 font-mono">
                          Doc: {asiento.documento}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      {asiento.exported_to_erp ? (
                        <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold">
                          Exportado a ERP
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px] font-medium">
                          Pendiente exportar
                        </span>
                      )}

                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          asiento.is_balanced
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {asiento.is_balanced ? 'Cuadrado' : 'Descuadrado'}
                      </span>
                    </div>
                  </div>

                  {/* Líneas de apunte en partida doble */}
                  <table className="w-full text-xs">
                    <thead className="text-[11px] text-slate-400 border-b border-slate-100">
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
                          <td className="py-2 px-4 font-bold text-slate-800">{l.subcuenta}</td>
                          <td className="py-2 px-4 font-sans text-slate-600">{l.concepto}</td>
                          <td className="py-2 px-4 text-right text-slate-900">
                            {l.debe > 0
                              ? Intl.NumberFormat('es-ES', {
                                  style: 'currency',
                                  currency: 'EUR',
                                }).format(l.debe)
                              : '-'}
                          </td>
                          <td className="py-2 px-4 text-right text-slate-900">
                            {l.haber > 0
                              ? Intl.NumberFormat('es-ES', {
                                  style: 'currency',
                                  currency: 'EUR',
                                }).format(l.haber)
                              : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-slate-50/60 font-mono font-bold text-xs border-t border-slate-200">
                      <tr>
                        <td colSpan={2} className="py-2 px-4 text-right font-sans text-slate-500">
                          Totales Asiento:
                        </td>
                        <td className="py-2 px-4 text-right text-indigo-700">
                          {Intl.NumberFormat('es-ES', {
                            style: 'currency',
                            currency: 'EUR',
                          }).format(asiento.total_debe)}
                        </td>
                        <td className="py-2 px-4 text-right text-indigo-700">
                          {Intl.NumberFormat('es-ES', {
                            style: 'currency',
                            currency: 'EUR',
                          }).format(asiento.total_haber)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ))}
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
                className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700"
              >
                Consultar Mayor
              </button>
            </div>

            {ledgerData && (
              <div className="flex items-center gap-4 text-xs font-mono">
                <div>
                  <span className="text-slate-400">Total Debe:</span>{' '}
                  <strong className="text-slate-800">
                    {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
                      ledgerData.total_debe
                    )}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-400">Total Haber:</span>{' '}
                  <strong className="text-slate-800">
                    {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
                      ledgerData.total_haber
                    )}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-400">Saldo Final:</span>{' '}
                  <strong
                    className={
                      ledgerData.tipo_saldo === 'DEUDOR'
                        ? 'text-emerald-700'
                        : ledgerData.tipo_saldo === 'ACREEDOR'
                        ? 'text-indigo-700'
                        : 'text-slate-600'
                    }
                  >
                    {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
                      ledgerData.saldo_final
                    )}{' '}
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
                  <p className="text-xs text-slate-500">{ledgerData.descripcion}</p>
                </div>
                <div className="text-xs text-slate-500 font-mono">
                  Saldo Inicial:{' '}
                  <strong>
                    {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
                      ledgerData.debe_inicial - ledgerData.haber_inicial
                    )}
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
                      <th className="py-2.5 px-4">Fecha</th>
                      <th className="py-2.5 px-4">Asiento</th>
                      <th className="py-2.5 px-4">Concepto</th>
                      <th className="py-2.5 px-4">Documento</th>
                      <th className="py-2.5 px-4 text-right">Debe (€)</th>
                      <th className="py-2.5 px-4 text-right">Haber (€)</th>
                      <th className="py-2.5 px-4 text-right">Saldo Progresivo</th>
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
                          {m.debe > 0
                            ? Intl.NumberFormat('es-ES', {
                                style: 'currency',
                                currency: 'EUR',
                              }).format(m.debe)
                            : '-'}
                        </td>
                        <td className="py-2.5 px-4 text-right text-slate-900">
                          {m.haber > 0
                            ? Intl.NumberFormat('es-ES', {
                                style: 'currency',
                                currency: 'EUR',
                              }).format(m.haber)
                            : '-'}
                        </td>
                        <td className="py-2.5 px-4 text-right font-bold text-slate-900">
                          {Intl.NumberFormat('es-ES', {
                            style: 'currency',
                            currency: 'EUR',
                          }).format(m.saldo_progresivo)}{' '}
                          <span className="text-[10px] text-slate-400 font-normal">{m.signo}</span>
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
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-800">
                    Balance de Comprobación de Sumas y Saldos
                  </h3>
                  <p className="text-xs text-slate-500">
                    Verificación de partida doble: Suma Debe = Suma Haber • Saldo Deudor = Saldo
                    Acreedor
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
                          {Intl.NumberFormat('es-ES', {
                            style: 'currency',
                            currency: 'EUR',
                          }).format(it.suma_debe)}
                        </td>
                        <td className="py-2 px-4 text-right text-slate-900">
                          {Intl.NumberFormat('es-ES', {
                            style: 'currency',
                            currency: 'EUR',
                          }).format(it.suma_haber)}
                        </td>
                        <td className="py-2 px-4 text-right text-emerald-700 font-semibold">
                          {it.saldo_deudor > 0
                            ? Intl.NumberFormat('es-ES', {
                                style: 'currency',
                                currency: 'EUR',
                              }).format(it.saldo_deudor)
                            : '-'}
                        </td>
                        <td className="py-2 px-4 text-right text-indigo-700 font-semibold">
                          {it.saldo_acreedor > 0
                            ? Intl.NumberFormat('es-ES', {
                                style: 'currency',
                                currency: 'EUR',
                              }).format(it.saldo_acreedor)
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
                        {Intl.NumberFormat('es-ES', {
                          style: 'currency',
                          currency: 'EUR',
                        }).format(trialBalanceData.totales.suma_debe)}
                      </td>
                      <td className="py-3 px-4 text-right text-slate-900">
                        {Intl.NumberFormat('es-ES', {
                          style: 'currency',
                          currency: 'EUR',
                        }).format(trialBalanceData.totales.suma_haber)}
                      </td>
                      <td className="py-3 px-4 text-right text-emerald-800">
                        {Intl.NumberFormat('es-ES', {
                          style: 'currency',
                          currency: 'EUR',
                        }).format(trialBalanceData.totales.saldo_deudor)}
                      </td>
                      <td className="py-3 px-4 text-right text-indigo-800">
                        {Intl.NumberFormat('es-ES', {
                          style: 'currency',
                          currency: 'EUR',
                        }).format(trialBalanceData.totales.saldo_acreedor)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

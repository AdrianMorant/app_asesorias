'use client';

import React, { useState, useEffect } from 'react';
import { Company, TaxSummaryResponse } from '@/types';
import { fetchTaxSummary } from '@/lib/api';
import {
  Landmark,
  Scale,
  Calendar,
  AlertTriangle,
  FileText,
  CheckCircle2,
  Users,
  Download,
  Building,
  ArrowRight,
  ShieldAlert,
  ShieldCheck,
  FileDown,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

interface TaxModelsViewProps {
  company: Company;
  onNotify: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
}

export const TaxModelsView: React.FC<TaxModelsViewProps> = ({ company, onNotify }) => {
  const [year, setYear] = useState<number>(2026);
  const [period, setPeriod] = useState<string>('1T');
  const [activeModel, setActiveModel] = useState<'303' | '111' | '115' | '347'>('303');
  const [taxData, setTaxData] = useState<TaxSummaryResponse | null>(null);
  const [riskReport, setRiskReport] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [summaryRes, riskRes] = await Promise.all([
        fetchTaxSummary(company.id, year, period),
        fetch(`${API_BASE}/companies/${company.id}/audit-risk-score?year=${year}&period=${period}`).then((r) =>
          r.ok ? r.json() : null
        ),
      ]);
      setTaxData(summaryRes);
      setRiskReport(riskRes);
    } catch {
      onNotify('error', 'Error al calcular la autoliquidación tributaria');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [company.id, year, period]);

  const mod303 = taxData?.modelo_303;
  const mod111 = taxData?.modelo_111;
  const mod115 = taxData?.modelo_115;
  const mod347 = taxData?.modelo_347;

  return (
    <div className="space-y-6">
      {/* Cabecera y Selectores de Ejercicio / Periodo */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <Landmark className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Impuestos y Modelos Tributarios (AEAT)
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Pre-cálculo y borradores en tiempo real de los modelos oficiales para el PGC español:
            Modelo 303 (IVA), Modelo 111 (Retenciones IRPF), Modelo 115 (Alquileres) y Control preventivo del Modelo 347.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div>
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
              Ejercicio
            </label>
            <select
              value={year}
              onChange={(e) => setYear(parseInt(e.target.value))}
              className="text-xs font-mono font-bold px-3 py-1.5 border border-slate-200 rounded-lg bg-white focus:ring-1 focus:ring-indigo-500 outline-none"
            >
              <option value="2026">2026</option>
              <option value="2025">2025</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
              Periodo
            </label>
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="text-xs font-bold px-3 py-1.5 border border-slate-200 rounded-lg bg-white focus:ring-1 focus:ring-indigo-500 outline-none"
            >
              <option value="1T">1T (Ene - Mar)</option>
              <option value="2T">2T (Abr - Jun)</option>
              <option value="3T">3T (Jul - Sep)</option>
              <option value="4T">4T (Oct - Dic)</option>
              <option value="ANUAL">Ejercicio Completo</option>
            </select>
          </div>
        </div>
      </div>

      {/* Widget Semáforo Preventivo de Riesgo Tributario AEAT */}
      {riskReport && (
        <div
          className={`p-5 rounded-xl border shadow-sm transition-all ${
            riskReport.risk_level === 'HIGH'
              ? 'bg-rose-50/60 border-rose-200'
              : riskReport.risk_level === 'MEDIUM'
              ? 'bg-amber-50/60 border-amber-200'
              : 'bg-emerald-50/60 border-emerald-200'
          }`}
        >
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <span
                className={`p-2.5 rounded-lg shrink-0 ${
                  riskReport.risk_level === 'HIGH'
                    ? 'bg-rose-100 text-rose-700'
                    : riskReport.risk_level === 'MEDIUM'
                    ? 'bg-amber-100 text-amber-700'
                    : 'bg-emerald-100 text-emerald-700'
                }`}
              >
                {riskReport.risk_level === 'LOW' ? (
                  <ShieldCheck className="w-5 h-5" />
                ) : (
                  <ShieldAlert className="w-5 h-5" />
                )}
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-slate-900">
                    Auditoría Preventiva AEAT • Semáforo de Riesgo Fiscal
                  </h3>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase ${
                      riskReport.risk_level === 'HIGH'
                        ? 'bg-rose-600 text-white'
                        : riskReport.risk_level === 'MEDIUM'
                        ? 'bg-amber-600 text-white'
                        : 'bg-emerald-600 text-white'
                    }`}
                  >
                    Riesgo {riskReport.risk_level} ({riskReport.risk_score}/100)
                  </span>
                </div>
                <p className="text-xs text-slate-600 mt-1">
                  {riskReport.risk_level === 'LOW'
                    ? 'Todos los parámetros contables cuadran con los baremos habituales de la Agencia Tributaria. Apto para presentación oficial.'
                    : `Se han detectado ${riskReport.total_risk_factors} factor(es) de riesgo que podrían detonar una inspección o requerimiento fiscal.`}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-slate-500 font-mono">
                Gastos: {riskReport.financial_snapshot?.purchases_base?.toFixed(2)} € / Ventas:{' '}
                {riskReport.financial_snapshot?.sales_base?.toFixed(2)} €
              </span>
            </div>
          </div>

          {riskReport.risk_factors && riskReport.risk_factors.length > 0 && (
            <div className="mt-4 pt-3 border-t border-slate-200/60 space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Observaciones y Puntos de Atención:
              </span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {riskReport.risk_factors.map((rf: any, i: number) => (
                  <div key={i} className="p-2.5 bg-white/80 rounded-lg border border-slate-200 text-xs space-y-1">
                    <div className="font-bold text-slate-800 flex items-center justify-between">
                      <span>{rf.title}</span>
                      <span className="text-[10px] font-mono text-rose-600">+{rf.penalty} pts</span>
                    </div>
                    <div className="text-slate-600 text-[11px]">{rf.description}</div>
                    <div className="text-[10px] text-indigo-700 font-medium">💡 {rf.recommendation}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Selector de Modelo Oficial */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button
          onClick={() => setActiveModel('303')}
          className={`p-3.5 rounded-xl border text-left transition-all ${
            activeModel === '303'
              ? 'bg-indigo-50/50 border-indigo-500 ring-2 ring-indigo-500/20'
              : 'bg-white border-slate-200 hover:border-slate-300'
          }`}
        >
          <div className="text-xs font-bold text-indigo-700">Modelo 303</div>
          <div className="text-sm font-bold text-slate-900 mt-0.5">Autoliquidación IVA</div>
          <div className="text-[11px] text-slate-500 mt-1">
            Resultado:{' '}
            <strong className="font-mono text-slate-800">
              {mod303 ? `${mod303.resultado.toFixed(2)} €` : '...'}
            </strong>
          </div>
        </button>

        <button
          onClick={() => setActiveModel('111')}
          className={`p-3.5 rounded-xl border text-left transition-all ${
            activeModel === '111'
              ? 'bg-indigo-50/50 border-indigo-500 ring-2 ring-indigo-500/20'
              : 'bg-white border-slate-200 hover:border-slate-300'
          }`}
        >
          <div className="text-xs font-bold text-amber-700">Modelo 111</div>
          <div className="text-sm font-bold text-slate-900 mt-0.5">Retenciones IRPF</div>
          <div className="text-[11px] text-slate-500 mt-1">
            Retenido:{' '}
            <strong className="font-mono text-slate-800">
              {mod111 ? `${mod111.importe_retenciones.toFixed(2)} €` : '...'}
            </strong>
          </div>
        </button>

        <button
          onClick={() => setActiveModel('115')}
          className={`p-3.5 rounded-xl border text-left transition-all ${
            activeModel === '115'
              ? 'bg-indigo-50/50 border-indigo-500 ring-2 ring-indigo-500/20'
              : 'bg-white border-slate-200 hover:border-slate-300'
          }`}
        >
          <div className="text-xs font-bold text-emerald-700">Modelo 115</div>
          <div className="text-sm font-bold text-slate-900 mt-0.5">Alquileres Urbanos</div>
          <div className="text-[11px] text-slate-500 mt-1">
            Retenido:{' '}
            <strong className="font-mono text-slate-800">
              {mod115 ? `${mod115.importe_retenciones.toFixed(2)} €` : '...'}
            </strong>
          </div>
        </button>

        <button
          onClick={() => setActiveModel('347')}
          className={`p-3.5 rounded-xl border text-left transition-all ${
            activeModel === '347'
              ? 'bg-indigo-50/50 border-indigo-500 ring-2 ring-indigo-500/20'
              : 'bg-white border-slate-200 hover:border-slate-300'
          }`}
        >
          <div className="text-xs font-bold text-purple-700">Modelo 347</div>
          <div className="text-sm font-bold text-slate-900 mt-0.5">Terceros (&gt;3.005 €)</div>
          <div className="text-[11px] text-slate-500 mt-1">
            Declarables:{' '}
            <strong className="font-mono text-slate-800">
              {mod347 ? `${mod347.total_declarables} entidades` : '...'}
            </strong>
          </div>
        </button>
      </div>

      {/* VISTA DETALLADA DEL MODELO SELECCIONADO */}

      {/* 1. MODELO 303 (IVA) */}
      {activeModel === '303' && mod303 && (
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden p-6 space-y-6">
          <div className="flex items-center justify-between border-b pb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Borrador Modelo 303 • Autoliquidación del Impuesto sobre el Valor Añadido
              </h2>
              <p className="text-xs text-slate-500">
                Periodo: {mod303.periodo} / Ejercicio {mod303.ejercicio} • Empresa: {company.razon_social} ({company.cif})
              </p>
            </div>
            <div className="flex items-center gap-3">
              <a
                href={`${API_BASE}/companies/${company.id}/export/modelo-303?year=${year}&period=${period}`}
                download={`303_${company.cif}_${year}_${period}.txt`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-bold text-xs shadow-sm transition-colors"
              >
                <FileDown className="w-4 h-4" /> Generar Fichero Oficial BOE (.txt)
              </a>

              <div
                className={`px-4 py-2 rounded-xl border text-right ${
                  mod303.resultado > 0
                    ? 'bg-amber-50 border-amber-200 text-amber-900'
                    : 'bg-emerald-50 border-emerald-200 text-emerald-900'
                }`}
              >
                <div className="text-[10px] font-bold uppercase tracking-wider">
                  Resultado [Casilla 46]
                </div>
                <div className="text-lg font-bold font-mono">
                  {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
                    mod303.resultado
                  )}
                </div>
                <div className="text-[10px] font-semibold">{mod303.tipo_resultado}</div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Columna Izquierda: IVA DEVENGADO */}
            <div className="space-y-3">
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 font-bold text-xs text-slate-800 uppercase tracking-wide">
                I. IVA Devengado (Ventas y Facturación Emitida)
              </div>
              <table className="w-full text-xs">
                <thead className="text-[11px] text-slate-400 border-b">
                  <tr>
                    <th className="py-2 text-left">Régimen General</th>
                    <th className="py-2 text-right">Base Imponible</th>
                    <th className="py-2 text-center">Tipo</th>
                    <th className="py-2 text-right">Cuota</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  <tr>
                    <td className="py-2 text-slate-700 font-sans">[01]-[03] Régimen 21%</td>
                    <td className="py-2 text-right">{mod303.devengado.r21.base.toFixed(2)} €</td>
                    <td className="py-2 text-center">21%</td>
                    <td className="py-2 text-right font-semibold text-slate-900">
                      {mod303.devengado.r21.cuota.toFixed(2)} €
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 text-slate-700 font-sans">[04]-[06] Régimen 10%</td>
                    <td className="py-2 text-right">{mod303.devengado.r10.base.toFixed(2)} €</td>
                    <td className="py-2 text-center">10%</td>
                    <td className="py-2 text-right font-semibold text-slate-900">
                      {mod303.devengado.r10.cuota.toFixed(2)} €
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 text-slate-700 font-sans">[07]-[09] Régimen 4%</td>
                    <td className="py-2 text-right">{mod303.devengado.r4.base.toFixed(2)} €</td>
                    <td className="py-2 text-center">4%</td>
                    <td className="py-2 text-right font-semibold text-slate-900">
                      {mod303.devengado.r4.cuota.toFixed(2)} €
                    </td>
                  </tr>
                </tbody>
                <tfoot className="border-t font-mono font-bold text-xs bg-slate-50/50">
                  <tr>
                    <td colSpan={3} className="py-2 text-right font-sans text-slate-600">
                      [27] Total Cuota Devengada:
                    </td>
                    <td className="py-2 text-right text-indigo-700">
                      {mod303.devengado.total_cuota.toFixed(2)} €
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>

            {/* Columna Derecha: IVA DEDUCIBLE */}
            <div className="space-y-3">
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 font-bold text-xs text-slate-800 uppercase tracking-wide">
                II. IVA Deducible (Compras y Facturas Recibidas)
              </div>
              <table className="w-full text-xs">
                <thead className="text-[11px] text-slate-400 border-b">
                  <tr>
                    <th className="py-2 text-left">Concepto Deducible</th>
                    <th className="py-2 text-right">Base Imponible</th>
                    <th className="py-2 text-right">Cuota Deducible</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  <tr>
                    <td className="py-2 text-slate-700 font-sans">
                      [28]-[29] Operaciones Interiores Corrientes
                    </td>
                    <td className="py-2 text-right">{mod303.deducible.base_interior.toFixed(2)} €</td>
                    <td className="py-2 text-right font-semibold text-slate-900">
                      {mod303.deducible.cuota_interior.toFixed(2)} €
                    </td>
                  </tr>
                </tbody>
                <tfoot className="border-t font-mono font-bold text-xs bg-slate-50/50">
                  <tr>
                    <td colSpan={2} className="py-2 text-right font-sans text-slate-600">
                      [45] Total Cuota Deducible:
                    </td>
                    <td className="py-2 text-right text-emerald-700">
                      {mod303.deducible.total_cuota.toFixed(2)} €
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 2. MODELO 111 (Retenciones IRPF) */}
      {activeModel === '111' && mod111 && (
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between border-b pb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Borrador Modelo 111 • Retenciones del IRPF (Profesionales y Nóminas)
              </h2>
              <p className="text-xs text-slate-500">
                Rendimientos de actividades profesionales (Cuentas 4751) y perceptores identificados
              </p>
            </div>
            <a
              href={`${API_BASE}/companies/${company.id}/export/modelo-111?year=${year}&period=${period}`}
              download={`111_${company.cif}_${year}_${period}.txt`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-bold text-xs shadow-sm transition-colors"
            >
              <FileDown className="w-4 h-4" /> Generar Fichero Oficial BOE (.txt)
            </a>
          </div>

          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-400 mb-1">[Casilla 07] Número de Perceptores</div>
              <div className="text-2xl font-bold font-mono text-slate-800">
                {mod111.numero_perceptores}
              </div>
            </div>
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-400 mb-1">[Casilla 08] Base de las Retenciones</div>
              <div className="text-2xl font-bold font-mono text-slate-800">
                {mod111.base_retenciones.toFixed(2)} €
              </div>
            </div>
            <div className="p-4 bg-amber-50 rounded-xl border border-amber-200">
              <div className="text-xs text-amber-700 font-semibold mb-1">
                [Casilla 09] Importe Total a Ingresar
              </div>
              <div className="text-2xl font-bold font-mono text-amber-900">
                {mod111.importe_retenciones.toFixed(2)} €
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3. MODELO 115 (Alquileres) */}
      {activeModel === '115' && mod115 && (
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between border-b pb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Borrador Modelo 115 • Retenciones sobre Arrendamientos Urbanos
              </h2>
              <p className="text-xs text-slate-500">
                Imputaciones a subcuentas de alquileres (621) y retención del 19% aplicable
              </p>
            </div>
            <a
              href={`${API_BASE}/companies/${company.id}/export/modelo-115?year=${year}&period=${period}`}
              download={`115_${company.cif}_${year}_${period}.txt`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold text-xs shadow-sm transition-colors"
            >
              <FileDown className="w-4 h-4" /> Generar Fichero Oficial BOE (.txt)
            </a>
          </div>

          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-400 mb-1">[Casilla 01] Número de Perceptores</div>
              <div className="text-2xl font-bold font-mono text-slate-800">
                {mod115.numero_perceptores}
              </div>
            </div>
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-400 mb-1">[Casilla 02] Base de las Retenciones</div>
              <div className="text-2xl font-bold font-mono text-slate-800">
                {mod115.base_retenciones.toFixed(2)} €
              </div>
            </div>
            <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
              <div className="text-xs text-emerald-700 font-semibold mb-1">
                [Casilla 03] Retenciones Practicadas
              </div>
              <div className="text-2xl font-bold font-mono text-emerald-900">
                {mod115.importe_retenciones.toFixed(2)} €
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. CONTROL MODELO 347 (Operaciones > 3.005,06 €) */}
      {activeModel === '347' && mod347 && (
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between border-b pb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Control Preventivo Modelo 347 • Operaciones Anuales con Terceras Personas
              </h2>
              <p className="text-xs text-slate-500">
                Umbral legal obligatorio: superior a 3.005,06 € computado durante el año natural {mod347.ejercicio}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <a
                href={`${API_BASE}/companies/${company.id}/export/modelo-347?year=${year}`}
                download={`347_${company.cif}_${year}.txt`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-3.5 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-bold text-xs shadow-sm transition-colors"
              >
                <FileDown className="w-4 h-4" /> Generar Fichero Oficial BOE (.txt)
              </a>
              <div className="text-xs font-mono font-bold px-3 py-1.5 bg-purple-50 text-purple-700 rounded-lg border border-purple-200">
                {mod347.total_declarables} Sujetos Declarables
              </div>
            </div>
          </div>

          {mod347.declarables.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs">
              Ningún cliente o proveedor supera el umbral de 3.005,06 € en el ejercicio actual.
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b">
                <tr>
                  <th className="py-2.5 px-4 text-left">NIF / CIF</th>
                  <th className="py-2.5 px-4 text-left">Razón Social</th>
                  <th className="py-2.5 px-4 text-left">Tipo</th>
                  <th className="py-2.5 px-4 text-right">T1 (€)</th>
                  <th className="py-2.5 px-4 text-right">T2 (€)</th>
                  <th className="py-2.5 px-4 text-right">T3 (€)</th>
                  <th className="py-2.5 px-4 text-right">T4 (€)</th>
                  <th className="py-2.5 px-4 text-right font-bold">Total Anual (€)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {mod347.declarables.map((d, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="py-2.5 px-4 font-bold text-slate-800">{d.cif}</td>
                    <td className="py-2.5 px-4 font-sans text-slate-900">{d.nombre}</td>
                    <td className="py-2.5 px-4">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 font-sans">
                        {d.tipo}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-right">{d.t1.toFixed(2)}</td>
                    <td className="py-2.5 px-4 text-right">{d.t2.toFixed(2)}</td>
                    <td className="py-2.5 px-4 text-right">{d.t3.toFixed(2)}</td>
                    <td className="py-2.5 px-4 text-right">{d.t4.toFixed(2)}</td>
                    <td className="py-2.5 px-4 text-right font-bold text-indigo-700">
                      {d.total_anual.toFixed(2)} €
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};

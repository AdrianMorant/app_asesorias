'use client';

import React, { useState, useEffect } from 'react';
import { Company, Invoice, SalesInvoice, TaxSummaryResponse } from '@/types';
import { fetchTaxSummary } from '@/lib/api';
import { ActiveNavTab, WorkspaceMode } from '@/components/Sidebar';
import { TaxModelsView } from '@/components/TaxModelsView';
import {
  Scale,
  Calendar,
  TrendingUp,
  TrendingDown,
  Sparkles,
  Download,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  Clock,
  Receipt,
  Users,
  Building2,
  Landmark,
  ShieldCheck,
  HelpCircle,
  Info,
  FileText,
  Layers,
  ChevronRight,
  Zap,
} from 'lucide-react';

interface TaxDashboardViewProps {
  company: Company;
  invoices?: Invoice[];
  sales?: SalesInvoice[];
  onNotify: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
  onNavigateTab?: (tab: ActiveNavTab) => void;
  onOpenAIAssistantWithQuery?: (query: string) => void;
  mode?: WorkspaceMode;
}

export const TaxDashboardView: React.FC<TaxDashboardViewProps> = ({
  company,
  invoices = [],
  sales = [],
  onNotify,
  onNavigateTab,
  onOpenAIAssistantWithQuery,
  mode = 'client',
}) => {
  const [year, setYear] = useState<number>(2026);
  const [period, setPeriod] = useState<string>('1T');
  const [taxData, setTaxData] = useState<TaxSummaryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [showOfficialTechnicalView, setShowOfficialTechnicalView] = useState<boolean>(false);

  // Cargar datos tributarios del backend
  const loadTaxData = async () => {
    setLoading(true);
    try {
      const res = await fetchTaxSummary(company.id, year, period);
      setTaxData(res);
    } catch {
      onNotify('error', 'Error al calcular la autoliquidación tributaria.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTaxData();
  }, [company.id, year, period]);

  // Cálculos dinámicos combinados
  const mod303 = taxData?.modelo_303;
  const mod111 = taxData?.modelo_111;
  const mod115 = taxData?.modelo_115;
  const mod347 = taxData?.modelo_347;

  // IVA repercutido y soportado
  const vatCollected = mod303?.devengado?.total_cuota ?? sales.reduce((acc, s) => acc + (s.total_tax || 0), 0);
  const vatDeductible = mod303?.deducible?.total_cuota ?? invoices.reduce((acc, i) => acc + (i.total_tax || 0), 0);
  const netVatResult = mod303?.resultado ?? (vatCollected - vatDeductible);

  // Retenciones IRPF acumuladas
  const retentions111Total = mod111?.importe_retenciones ?? invoices.reduce((acc, i) => acc + (i.total_retention || 0), 0);
  const retentions115Total = mod115?.importe_retenciones ?? 0;

  // Días restantes para el fin del plazo (20 de Abril)
  const daysLeftDeadline = 13;

  // Descarga del Borrador Informativo para No Contables
  const handleDownloadDraft = () => {
    const reportText = `=====================================================
INFORME FISCAL SIMPLIFICADO: ${company.razon_social}
CIF: ${company.cif} | Ejercicio: ${year} - Periodo: ${period}
Generado automáticamente por Konta AI Suite
=====================================================

1. AUTOLIQUIDACIÓN ESTIMADA DE IVA (MODELO 303):
-----------------------------------------------------
• (+) IVA Cobrado a tus clientes (Ventas): ${vatCollected.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
• (-) IVA Soportado deducible (Compras):   ${vatDeductible.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
-----------------------------------------------------
RESULTADO NETO DE IVA: ${Math.abs(netVatResult).toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
POSICIÓN FISCAL: ${netVatResult > 0 ? 'A INGRESAR A HACIENDA' : 'A COMPENSAR / A TU FAVOR'}
PLAZO LÍMITE DE PAGO/PRESENTACIÓN: 20 de Abril de ${year} (Quedan ${daysLeftDeadline} días)

2. RETENCIONES IRPF (MODELO 111):
-----------------------------------------------------
• Retenciones a profesionales / colaboradores: ${retentions111Total.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
• Estado: Listo para liquidar telemáticamente

3. RETENCIONES DE ALQUILERES (MODELO 115):
-----------------------------------------------------
• Retenciones sobre arrendamientos urbanos: ${retentions115Total.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €

=====================================================
* Documento informativo de uso interno para la gerencia.
=====================================================`;

    const blob = new Blob([reportText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `Borrador_Fiscal_${company.cif}_${year}_${period}.txt`;
    link.click();
    URL.revokeObjectURL(url);

    onNotify('success', 'Borrador fiscal descargado correctamente.');
  };

  const isAdvisor = mode === 'advisor';

  return (
    <div className="space-y-6">
      {/* Selector de periodo y Alternador de Modo */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100">
            <Scale className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-slate-900 tracking-tight">
                Panel Fiscal y Modelos Tributarios
              </h1>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                AEAT Compliance 2026
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Traducción en lenguaje claro de tus obligaciones trimestrales ante la Agencia Tributaria.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Selector Trimestre */}
          <div className="flex items-center bg-slate-100 p-1 rounded-xl text-xs font-semibold">
            {['1T', '2T', '3T', '4T'].map((t) => (
              <button
                key={t}
                onClick={() => setPeriod(t)}
                className={`px-3 py-1 rounded-lg transition-all ${
                  period === t
                    ? 'bg-white text-slate-900 shadow-xs font-bold'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Selector Año */}
          <select
            value={year}
            onChange={(e) => setYear(parseInt(e.target.value))}
            className="text-xs font-bold px-3 py-1.5 border border-slate-200 rounded-xl bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value={2026}>2026</option>
            <option value={2025}>2025</option>
          </select>

          {/* Toggle entre Vista Simplificada y Vista Técnica */}
          <button
            onClick={() => setShowOfficialTechnicalView(!showOfficialTechnicalView)}
            className={`text-xs font-semibold px-3 py-1.5 rounded-xl border transition-all flex items-center gap-1.5 ${
              showOfficialTechnicalView
                ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>{showOfficialTechnicalView ? 'Vista Simplificada' : 'Vista Técnica AEAT'}</span>
          </button>
        </div>
      </div>

      {/* Si el usuario prefiere la vista técnica de modelos oficiales, la mostramos */}
      {showOfficialTechnicalView ? (
        <div className="space-y-4">
          <div className="p-3 rounded-xl bg-indigo-50 border border-indigo-100 text-xs text-indigo-900 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Info className="w-4 h-4 text-indigo-600" />
              Estás visualizando el <strong>Modo Técnico Oficial</strong> con casillas de autoliquidación AEAT (01-27).
            </span>
            <button
              onClick={() => setShowOfficialTechnicalView(false)}
              className="text-xs font-bold text-indigo-700 underline hover:text-indigo-900"
            >
              Volver a la vista simplificada
            </button>
          </div>
          <TaxModelsView company={company} onNotify={onNotify} />
        </div>
      ) : (
        /* VISTA SIMPLIFICADA PARA NO CONTABLES */
        <div className="space-y-6">
          
          {/* 1. TARJETA PRINCIPAL: RESULTADO DE IVA DEL TRIMESTRE EN CURSO */}
          <div className="bg-gradient-to-br from-slate-900 via-slate-850 to-slate-900 border border-slate-800 rounded-2xl p-6 text-white shadow-xl">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-800">
              <div className="space-y-1">
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Modelo 303 (IVA Trimestral)
                </span>
                <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                  Resultado de IVA del {period} {year}
                </h2>
                <p className="text-xs text-slate-400">
                  Cálculo automático: IVA cobrado en tus ventas menos IVA deducible en tus compras.
                </p>
              </div>

              {/* Semáforo de posición tributaria */}
              <div className="flex items-center gap-3">
                <div
                  className={`px-4 py-2 rounded-xl border flex items-center gap-2.5 ${
                    netVatResult > 0
                      ? 'bg-amber-950/60 border-amber-500/40 text-amber-300'
                      : 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
                  }`}
                >
                  <span
                    className={`w-2.5 h-2.5 rounded-full ${
                      netVatResult > 0 ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'
                    }`}
                  />
                  <div className="text-left">
                    <span className="text-[10px] font-bold uppercase tracking-wider block">
                      Posición Fiscal
                    </span>
                    <span className="text-xs font-bold">
                      {netVatResult > 0 ? 'A Ingresar a Hacienda' : 'A Devolver / Compensar'}
                    </span>
                  </div>
                </div>

                <div className="text-right">
                  <span className="text-[10px] text-slate-400 block font-medium">
                    Importe Estimado
                  </span>
                  <span
                    className={`text-2xl font-bold font-mono tracking-tight ${
                      netVatResult > 0 ? 'text-amber-400' : 'text-emerald-400'
                    }`}
                  >
                    {Math.abs(netVatResult).toLocaleString('es-ES', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{' '}
                    €
                  </span>
                </div>
              </div>
            </div>

            {/* Desglose visual en 3 columnas: IVA Cobrado vs IVA Deducible */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-5">
              {/* Columna 1: IVA Cobrado a Clientes */}
              <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="flex items-center gap-1.5 font-medium text-slate-300">
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    IVA Cobrado (Ventas)
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-300 font-mono">
                    Repercutido
                  </span>
                </div>
                <div className="text-xl font-bold font-mono text-emerald-400">
                  +{vatCollected.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
                </div>
                <p className="text-[11px] text-slate-400">
                  Impuesto cobrado en tus facturas emitidas a clientes. No es ingreso propio, se recauda para la AEAT.
                </p>
              </div>

              {/* Columna 2: IVA Deducible en Compras */}
              <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="flex items-center gap-1.5 font-medium text-slate-300">
                    <TrendingDown className="w-4 h-4 text-rose-400" />
                    IVA Deducible (Gastos)
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-300 font-mono">
                    Soportado
                  </span>
                </div>
                <div className="text-xl font-bold font-mono text-rose-400">
                  -{vatDeductible.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
                </div>
                <p className="text-[11px] text-slate-400">
                  IVA pagado en tus facturas de proveedores verificadas. La IA lo resta directamente de lo que debes pagar.
                </p>
              </div>

              {/* Columna 3: Recomendación Práctica */}
              <div className="p-4 rounded-xl bg-indigo-950/40 border border-indigo-500/30 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-300 mb-1">
                    <Sparkles className="w-4 h-4 text-indigo-400" />
                    Consejo Financiero de Konta IA
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed">
                    {netVatResult > 0 ? (
                      <>
                        Aparta <strong className="text-white">{Math.abs(netVatResult).toLocaleString('es-ES', { minimumFractionDigits: 2 })} €</strong> en tu cuenta corriente antes del <strong>20 de Abril</strong> para evitar recargos o intereses de demora.
                      </>
                    ) : (
                      <>
                        Tienes un saldo a tu favor de <strong className="text-white">{Math.abs(netVatResult).toLocaleString('es-ES', { minimumFractionDigits: 2 })} €</strong>. Se compensará automáticamente reduciendo el pago del próximo trimestre.
                      </>
                    )}
                  </p>
                </div>

                <div className="pt-2 flex items-center justify-between text-[10px] text-indigo-300/80 border-t border-indigo-500/20">
                  <span>Plazo límite: 20 de Abril</span>
                  <span className="font-bold text-amber-300">{daysLeftDeadline} días restantes</span>
                </div>
              </div>
            </div>
          </div>

          {/* 2. PREVISIÓN DE MODELOS TRIBUTARIOS (AEAT) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Modelo 303: IVA */}
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-900 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-600" />
                    Modelo 303 (IVA Trimestral)
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                    Autoliquidación
                  </span>
                </div>
                <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
                  {Math.abs(netVatResult).toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  {netVatResult > 0 ? 'Importe a ingresar en la AEAT.' : 'Importe a compensar a tu favor.'}
                </p>
                
                <div className="mt-3 p-2.5 rounded-xl bg-slate-50 border border-slate-100 text-[11px] space-y-1 text-slate-600">
                  <div className="flex justify-between">
                    <span>Estado del borrador:</span>
                    <strong className="text-emerald-700">Listo para presentación</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Límite presentación:</span>
                    <span className="font-mono text-slate-800">20/04/2026</span>
                  </div>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center gap-2">
                <button
                  onClick={() => onNavigateTab?.('expenses')}
                  className="flex-1 text-xs font-semibold py-2 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 transition-all flex items-center justify-center gap-1.5"
                >
                  <Receipt className="w-3.5 h-3.5 text-slate-600" />
                  Ver Desglose Facturas
                </button>
              </div>
            </div>

            {/* Modelo 111: Retenciones IRPF */}
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-900 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-500" />
                    Modelo 111 (Retenciones IRPF)
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                    Profesionales / Nóminas
                  </span>
                </div>
                <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
                  {retentions111Total.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Retenciones practicadas a profesionales independientes y nóminas de empleados.
                </p>

                <div className="mt-3 p-2.5 rounded-xl bg-slate-50 border border-slate-100 text-[11px] space-y-1 text-slate-600">
                  <div className="flex justify-between">
                    <span>Profesionales detectados:</span>
                    <strong className="text-slate-800 font-mono">
                      {invoices.filter((i) => i.total_retention && i.total_retention > 0).length} facturas
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Límite presentación:</span>
                    <span className="font-mono text-slate-800">20/04/2026</span>
                  </div>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center gap-2">
                <button
                  onClick={() => onNavigateTab?.('expenses')}
                  className="flex-1 text-xs font-semibold py-2 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 transition-all flex items-center justify-center gap-1.5"
                >
                  <Users className="w-3.5 h-3.5 text-slate-600" />
                  Ver Facturas con IRPF
                </button>
              </div>
            </div>

            {/* Modelo 115: Alquileres */}
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-900 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-purple-500" />
                    Modelo 115 (Alquileres)
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
                    Arrendamientos
                  </span>
                </div>
                <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
                  {retentions115Total.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Retenciones del 19% aplicadas sobre alquileres de oficinas o locales comerciales.
                </p>

                <div className="mt-3 p-2.5 rounded-xl bg-slate-50 border border-slate-100 text-[11px] space-y-1 text-slate-600">
                  <div className="flex justify-between">
                    <span>Estado:</span>
                    <span className="text-slate-600">
                      {retentions115Total > 0 ? 'Retenciones registradas' : 'Sin arrendamientos en 1T'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Límite presentación:</span>
                    <span className="font-mono text-slate-800">20/04/2026</span>
                  </div>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center gap-2">
                <button
                  onClick={() => setShowOfficialTechnicalView(true)}
                  className="flex-1 text-xs font-semibold py-2 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 transition-all flex items-center justify-center gap-1.5"
                >
                  <Building2 className="w-3.5 h-3.5 text-slate-600" />
                  Inspeccionar Modelo 115
                </button>
              </div>
            </div>
          </div>

          {/* 3. ACCIONES RÁPIDAS Y CONSULTA AL COPILOTO */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 text-white shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-gradient-to-br from-indigo-500 to-emerald-500 text-white shadow-lg">
                <Sparkles className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">
                  ¿Tienes dudas sobre cómo optimizar tus impuestos este trimestre?
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  El Copiloto Financiero IA analiza tus facturas pendientes para deducir el máximo IVA legalmente posible.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5 shrink-0">
              <button
                onClick={handleDownloadDraft}
                className="text-xs font-semibold px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all flex items-center gap-1.5"
              >
                <Download className="w-3.5 h-3.5" />
                Descargar Borrador Informativo
              </button>

              <button
                onClick={() => {
                  if (onOpenAIAssistantWithQuery) {
                    onOpenAIAssistantWithQuery('¿Cuál es mi estimación de IVA para el Modelo 303 y qué puedo deducir?');
                  }
                }}
                className={`text-xs font-semibold px-4 py-2 rounded-xl text-white shadow-md transition-all flex items-center gap-1.5 active:scale-95 ${
                  isAdvisor
                    ? 'bg-blue-600 hover:bg-blue-500 shadow-blue-600/30'
                    : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-600/30'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Preguntar al Copiloto sobre mi IVA</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

        </div>
      )}
    </div>
  );
};

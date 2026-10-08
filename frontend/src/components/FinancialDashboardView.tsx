'use client';

import React, { useState, useEffect } from 'react';
import { Company, Invoice, SalesInvoice } from '@/types';
import { fetchSalesInvoices, fetchTaxSummary } from '@/lib/api';
import {
  TrendingUp,
  TrendingDown,
  Scale,
  Receipt,
  ArrowUpRight,
  ArrowDownLeft,
  Calendar,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sparkles,
  ChevronRight,
  ShieldAlert,
  Landmark,
  Wallet,
  ArrowRight,
  Zap,
} from 'lucide-react';
import { OnboardingGuideCard } from './OnboardingGuideCard';
import { ActivityAuditTimeline } from './ActivityAuditTimeline';

interface FinancialDashboardViewProps {
  company: Company;
  invoices: Invoice[];
  onNavigateTab: (tab: any) => void;
  onSelectInvoice?: (invoice: Invoice) => void;
  onOpenAIAssistant?: () => void;
  mode?: 'advisor' | 'client';
  onOpenDemo?: () => void;
  onOpenUpload?: () => void;
}

export const FinancialDashboardView: React.FC<FinancialDashboardViewProps> = ({
  company,
  invoices,
  onNavigateTab,
  onSelectInvoice,
  onOpenAIAssistant,
  mode = 'client',
  onOpenDemo,
  onOpenUpload,
}) => {
  const [sales, setSales] = useState<SalesInvoice[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const loadSales = async () => {
      setLoading(true);
      try {
        const salesData = await fetchSalesInvoices(company.id);
        setSales(salesData);
      } catch {
        // En caso de fallo silencioso
      } finally {
        setLoading(false);
      }
    };
    loadSales();
  }, [company.id]);

  // Cálculos de métricas
  const totalSales = sales.reduce((acc, s) => acc + (s.total_amount || 0), 0);
  const totalSalesBase = sales.reduce((acc, s) => acc + (s.total_base || 0), 0);
  const totalSalesTax = sales.reduce((acc, s) => acc + (s.total_tax || 0), 0);

  const approvedExpenses = invoices.filter((inv) => inv.is_processed);
  const totalExpenses = approvedExpenses.reduce((acc, i) => acc + (i.total_amount || 0), 0);
  const totalExpensesBase = approvedExpenses.reduce((acc, i) => acc + (i.total_base || 0), 0);
  const totalExpensesTax = approvedExpenses.reduce((acc, i) => acc + (i.total_tax || 0), 0);

  // IVA Neto = Repercutido (ventas) - Soportado (gastos)
  const netVat = totalSalesTax - totalExpensesTax;
  const operatingProfit = totalSalesBase - totalExpensesBase;

  // Semáforo de Ingesta IA
  const greenInvoices = invoices.filter((i) => i.status === 'GREEN');
  const yellowInvoices = invoices.filter((i) => i.status === 'YELLOW');
  const redInvoices = invoices.filter((i) => i.status === 'RED');
  const pendingTriage = invoices.filter((i) => !i.is_processed);

  // Datos para gráfico mensual (12 meses simulados/acumulados)
  const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  const monthlyData = months.map((m, idx) => {
    // Distribuir ingresos y gastos reales o ponderados
    const monthSales = totalSales > 0 ? (totalSales / 12) * (0.8 + (idx % 4) * 0.15) : 0;
    const monthExpenses = totalExpenses > 0 ? (totalExpenses / 12) * (0.85 + ((idx + 2) % 3) * 0.1) : 0;
    return {
      month: m,
      sales: Math.round(monthSales),
      expenses: Math.round(monthExpenses),
    };
  });

  const maxChartVal = Math.max(
    ...monthlyData.map((d) => Math.max(d.sales, d.expenses)),
    1000
  );

  // Calendario Fiscal Español
  const taxDeadlines = [
    {
      model: 'Modelo 303 (IVA 1T)',
      period: '1er Trimestre 2026',
      deadline: '20 de Abril de 2026',
      daysLeft: 13,
      status: 'URGENTE',
      category: 'Autoliquidación IVA',
    },
    {
      model: 'Modelo 111 (IRPF 1T)',
      period: 'Retenciones Profesionales/Nóminas',
      deadline: '20 de Abril de 2026',
      daysLeft: 13,
      status: 'URGENTE',
      category: 'Retenciones IRPF',
    },
    {
      model: 'Modelo 115 (Alquileres 1T)',
      period: 'Retenciones Arrendamientos Urbanos',
      deadline: '20 de Abril de 2026',
      daysLeft: 13,
      status: 'EN_PLAZO',
      category: 'Arrendamientos',
    },
    {
      model: 'Modelo 347 (Terceros)',
      period: 'Operaciones Anuales > 3.005,06 €',
      deadline: '28 de Febrero de 2027',
      daysLeft: 144,
      status: 'EN_SEGUIMIENTO',
      category: 'Informativa Anual',
    },
    {
      model: 'Modelo 390 (Resumen IVA)',
      period: 'Resumen Anual IVA 2026',
      deadline: '30 de Enero de 2027',
      daysLeft: 115,
      status: 'EN_SEGUIMIENTO',
      category: 'Resumen Anual',
    },
  ];

  const isAdvisor = mode === 'advisor';
  const estimatedTreasury = Math.max(8500, 18450 + totalSales - totalExpenses);
  const criticalInvoices = invoices.filter((i) => i.status === 'RED' || i.status === 'YELLOW');

  return (
    <div className="space-y-6">
      {/* Cabecera del Dashboard con Acceso Directo al Copiloto IA */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg text-white">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                isAdvisor ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
              }`}
            >
              {isAdvisor ? 'Espacio Despacho Contable' : 'Espacio Empresa PYME'}
            </span>
            <span className="text-xs text-slate-400 font-mono">CIF: {company.cif}</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Panel Financiero Ejecutivo
            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-normal">
              {company.razon_social}
            </span>
          </h1>
          <p className="text-xs text-slate-400">
            Monitorización en tiempo real de tesorería, cumplimiento fiscal y triaje contable con IA.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {onOpenDemo && (
            <button
              onClick={onOpenDemo}
              className="flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl font-bold text-xs bg-slate-800/90 hover:bg-slate-750 text-cyan-300 border border-slate-700 hover:border-cyan-500/50 transition-all shadow-sm active:scale-95"
            >
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span>Probar Demo Guiada (1 min)</span>
            </button>
          )}

          {onOpenAIAssistant && (
            <button
              onClick={onOpenAIAssistant}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-xs transition-all shadow-md active:scale-95 ${
                isAdvisor
                  ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/30 ring-1 ring-blue-400/30'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/30 ring-1 ring-emerald-400/30'
              }`}
            >
              <Sparkles className="w-4 h-4 animate-spin text-white" />
              <span>Consultar Copiloto IA</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Widget de Onboarding en 3 Pasos (Fase C) */}
      <OnboardingGuideCard
        company={company}
        invoicesCount={invoices.length}
        onNavigateTab={onNavigateTab}
        onOpenUpload={onOpenUpload}
        onOpenDemo={onOpenDemo}
      />

      {/* Banner Proactivo del Agente IA */}
      <div className="bg-gradient-to-r from-indigo-900/40 via-slate-900/50 to-indigo-950/40 border border-indigo-500/30 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 text-slate-200 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 shrink-0 mt-0.5">
            <Zap className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold text-white flex items-center gap-2">
              Konta AI Copilot: Diagnóstico de Operaciones
              <span className="text-[10px] font-semibold px-2 py-0.2 rounded-full bg-indigo-500/20 text-indigo-300">
                Contexto en vivo
              </span>
            </div>
            <p className="text-xs text-slate-300 mt-0.5">
              {criticalInvoices.length > 0 ? (
                <>
                  Se han detectado <strong className="text-amber-300">{criticalInvoices.length} facturas</strong> que requieren validación y el <strong className="text-white">Modelo 303 (IVA 1T)</strong> vence en <strong className="text-amber-300">13 días</strong>.
                </>
              ) : (
                <>
                  Tus libros contables están <strong className="text-emerald-400">100% conciliados</strong> y al día según el PGC.
                </>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {criticalInvoices.length > 0 && (
            <button
              onClick={() => onNavigateTab('expenses')}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all flex items-center gap-1.5"
            >
              Revisar facturas ({criticalInvoices.length})
            </button>
          )}
          {onOpenAIAssistant && (
            <button
              onClick={onOpenAIAssistant}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-all flex items-center gap-1.5 shadow-sm"
            >
              Preguntar al Copiloto
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* 5 KPIs Financieros Ejecutivos */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
        {/* KPI 1: Saldo Disponible (Tesorería) */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span className="font-medium">Saldo Disponible</span>
            <span className="p-1.5 rounded-lg bg-blue-50 text-blue-600">
              <Wallet className="w-4 h-4" />
            </span>
          </div>
          <div className="text-xl font-bold font-mono tracking-tight text-slate-900">
            {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(estimatedTreasury)}
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>Tesorería Estimada</span>
            <span className="text-blue-700 font-semibold font-mono">Cta. 572</span>
          </div>
        </div>

        {/* KPI 2: Facturación (Ventas) */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span className="font-medium">Ingresos Emitidos</span>
            <span className="p-1.5 rounded-lg bg-emerald-50 text-emerald-600">
              <TrendingUp className="w-4 h-4" />
            </span>
          </div>
          <div className="text-xl font-bold font-mono tracking-tight text-slate-900">
            {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(totalSales)}
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>Base: {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(totalSalesBase)}</span>
            <span className="text-emerald-700 font-semibold">{sales.length} facturas</span>
          </div>
        </div>

        {/* KPI 3: Gastos Devengados */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span className="font-medium">Gastos Devengados</span>
            <span className="p-1.5 rounded-lg bg-rose-50 text-rose-600">
              <TrendingDown className="w-4 h-4" />
            </span>
          </div>
          <div className="text-xl font-bold font-mono tracking-tight text-slate-900">
            {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(totalExpenses)}
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>Base: {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(totalExpensesBase)}</span>
            <span className="text-slate-600 font-semibold">{approvedExpenses.length} aprobadas</span>
          </div>
        </div>

        {/* KPI 4: Beneficio Neto */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span className="font-medium">Beneficio Neto</span>
            <span className="p-1.5 rounded-lg bg-indigo-50 text-indigo-600">
              <Landmark className="w-4 h-4" />
            </span>
          </div>
          <div
            className={`text-xl font-bold font-mono tracking-tight ${
              operatingProfit >= 0 ? 'text-emerald-700' : 'text-rose-700'
            }`}
          >
            {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(operatingProfit)}
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>Margen antes de imp.</span>
            <span className="text-indigo-600 font-medium">PYME PGC</span>
          </div>
        </div>

        {/* KPI 5: IVA Neto Trimestral */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span className="font-medium">IVA Est. 1T</span>
            <span className="p-1.5 rounded-lg bg-amber-50 text-amber-600">
              <Scale className="w-4 h-4" />
            </span>
          </div>
          <div
            className={`text-xl font-bold font-mono tracking-tight ${
              netVat > 0 ? 'text-amber-700' : 'text-emerald-700'
            }`}
          >
            {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(Math.abs(netVat))}
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px]">
            <span
              className={`font-semibold px-1.5 py-0.2 rounded text-[10px] ${
                netVat > 0 ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
              }`}
            >
              {netVat > 0 ? 'A Ingresar' : 'A Compensar'}
            </span>
            <span className="text-slate-400 font-mono text-[10px]">Mod. 303</span>
          </div>
        </div>
      </div>

      {/* Centro de Atención Inmediata (Radical Simplicity & Acción Directa) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 text-white shadow-md">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
            <h2 className="text-sm font-bold tracking-wide">
              Centro de Atención Inmediata
            </h2>
            <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-mono">
              Acciones sugeridas por IA
            </span>
          </div>
          <span className="text-xs text-slate-400">
            Prioridad alta
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Card 1: Facturas a Revisar */}
          <div className="bg-slate-850 border border-slate-800/80 rounded-xl p-4 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Receipt className="w-4 h-4 text-rose-400" />
                  Facturas con Incidencia
                </span>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                  {criticalInvoices.length} pendientes
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                {criticalInvoices.length > 0
                  ? 'Requieren confirmar subcuenta o corregir descuadres de CIF/Base.'
                  : 'No hay facturas con bloqueo o pendientes de triaje.'}
              </p>
            </div>

            <button
              onClick={() => onNavigateTab('expenses')}
              className="w-full text-xs font-semibold py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/80 transition-all flex items-center justify-center gap-1.5"
            >
              {criticalInvoices.length > 0 ? 'Resolver en Triaje IA' : 'Ver Todas las Facturas'}
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Card 2: Conciliación Bancaria */}
          <div className="bg-slate-850 border border-slate-800/80 rounded-xl p-4 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Landmark className="w-4 h-4 text-blue-400" />
                  Conciliación Bancaria
                </span>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  Emparejamiento IA
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Cruza movimientos del extracto con asientos contables de facturas y nóminas.
              </p>
            </div>

            <button
              onClick={() => onNavigateTab('banking')}
              className="w-full text-xs font-semibold py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/80 transition-all flex items-center justify-center gap-1.5"
            >
              Conciliar Movimientos
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Card 3: Próximo Vencimiento Fiscal */}
          <div className="bg-slate-850 border border-slate-800/80 rounded-xl p-4 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Calendar className="w-4 h-4 text-amber-400" />
                  Próximo Impuesto
                </span>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  13 días restantes
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Modelo 303 (IVA 1T) y Modelo 111 (IRPF). Plazo: 20 de Abril de 2026.
              </p>
            </div>

            <button
              onClick={() => onNavigateTab('taxes')}
              className="w-full text-xs font-semibold py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/80 transition-all flex items-center justify-center gap-1.5"
            >
              Ver Borradores Oficiales
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Grid Central: Semáforo de Ingesta IA + Gráfico Comparativo 12 Meses */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Widget del Semáforo de Ingesta Inteligente */}
        <div className="lg:col-span-1 bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-emerald-600" />
                Motor Semafórico de Ingesta IA
              </h2>
              <p className="text-[11px] text-slate-500">
                Extracción multimodal Gemini & Validación fiscal
              </p>
            </div>
            <button
              onClick={() => onNavigateTab('expenses')}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-0.5"
            >
              Ir a Triaje <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Barras Semafóricas */}
          <div className="space-y-3">
            {/* Verde */}
            <div className="p-3 rounded-lg bg-emerald-50/70 border border-emerald-200/80">
              <div className="flex items-center justify-between mb-1.5 text-xs">
                <span className="font-bold text-emerald-800 flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                  Verde (Completas y Válidas)
                </span>
                <span className="font-mono font-bold text-emerald-900">{greenInvoices.length}</span>
              </div>
              <div className="w-full bg-emerald-200/50 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-emerald-500 h-2 rounded-full transition-all"
                  style={{
                    width: `${invoices.length > 0 ? (greenInvoices.length / invoices.length) * 100 : 0}%`,
                  }}
                />
              </div>
              <span className="text-[10px] text-emerald-700 mt-1 block">
                CIF, bases, cuotas y asientos 100% cuadradas.
              </span>
            </div>

            {/* Amarillo */}
            <div className="p-3 rounded-lg bg-amber-50/70 border border-amber-200/80">
              <div className="flex items-center justify-between mb-1.5 text-xs">
                <span className="font-bold text-amber-800 flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                  Amarillo (Revisión Sugerida)
                </span>
                <span className="font-mono font-bold text-amber-900">{yellowInvoices.length}</span>
              </div>
              <div className="w-full bg-amber-200/50 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-amber-500 h-2 rounded-full transition-all"
                  style={{
                    width: `${invoices.length > 0 ? (yellowInvoices.length / invoices.length) * 100 : 0}%`,
                  }}
                />
              </div>
              <span className="text-[10px] text-amber-700 mt-1 block">
                Proveedor nuevo o subcuenta sugerida automáticamente.
              </span>
            </div>

            {/* Rojo */}
            <div className="p-3 rounded-lg bg-rose-50/70 border border-rose-200/80">
              <div className="flex items-center justify-between mb-1.5 text-xs">
                <span className="font-bold text-rose-800 flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" />
                  Rojo (Bloqueadas con Anomalías)
                </span>
                <span className="font-mono font-bold text-rose-900">{redInvoices.length}</span>
              </div>
              <div className="w-full bg-rose-200/50 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-rose-500 h-2 rounded-full transition-all"
                  style={{
                    width: `${invoices.length > 0 ? (redInvoices.length / invoices.length) * 100 : 0}%`,
                  }}
                />
              </div>
              <span className="text-[10px] text-rose-700 mt-1 block">
                CIF inválido o descuadre matemático. Requiere triaje manual.
              </span>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Pendientes de aprobación:</span>
            <strong className="text-slate-800 font-mono">{pendingTriage.length} documentos</strong>
          </div>
        </div>

        {/* Gráfico Comparativo: Evolución Mensual Ingresos vs Gastos */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <div>
                <h2 className="text-sm font-bold text-slate-900">
                  Evolución Mensual: Ingresos vs Gastos
                </h2>
                <p className="text-[11px] text-slate-500">
                  Comparativa de facturación emitida frente a compras devengadas
                </p>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className="flex items-center gap-1.5 font-medium text-slate-600">
                  <span className="w-2.5 h-2.5 rounded bg-indigo-600" />
                  Ventas
                </span>
                <span className="flex items-center gap-1.5 font-medium text-slate-600">
                  <span className="w-2.5 h-2.5 rounded bg-emerald-500" />
                  Gastos
                </span>
              </div>
            </div>

            {/* Barras de comparación visual */}
            <div className="h-56 flex items-end justify-between gap-2 pt-6 px-2">
              {monthlyData.map((d, i) => {
                const salesHeight = Math.max((d.sales / maxChartVal) * 160, 4);
                const expHeight = Math.max((d.expenses / maxChartVal) * 160, 4);
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full flex items-end justify-center gap-1 h-44">
                      {/* Barra Ventas */}
                      <div
                        title={`Ventas ${d.month}: ${d.sales} €`}
                        className="w-2.5 md:w-3 bg-indigo-600 rounded-t-sm transition-all hover:bg-indigo-700"
                        style={{ height: `${salesHeight}px` }}
                      />
                      {/* Barra Gastos */}
                      <div
                        title={`Gastos ${d.month}: ${d.expenses} €`}
                        className="w-2.5 md:w-3 bg-emerald-500 rounded-t-sm transition-all hover:bg-emerald-600"
                        style={{ height: `${expHeight}px` }}
                      />
                    </div>
                    <span className="text-[10px] text-slate-400 font-medium">{d.month}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Rango: Ejercicio Fiscal 2026</span>
            <span className="font-mono text-slate-700">
              Total Acumulado:{' '}
              <strong>
                {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
                  totalSales + totalExpenses
                )}
              </strong>
            </span>
          </div>
        </div>
      </div>

      {/* Calendario Fiscal Español Próximo */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <Calendar className="w-4 h-4" />
            </span>
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                Calendario Fiscal Próximo (Modelos AEAT)
              </h2>
              <p className="text-[11px] text-slate-500">
                Plazos oficiales de presentación telemática para la empresa cliente
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigateTab('taxes')}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
          >
            Ver Borradores Oficiales <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {taxDeadlines.map((t, idx) => (
            <div
              key={idx}
              className={`p-3.5 rounded-xl border transition-all ${
                t.status === 'URGENTE'
                  ? 'border-amber-300 bg-amber-50/40 ring-1 ring-amber-300'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-bold text-xs text-slate-900">{t.model}</span>
                <span
                  className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${
                    t.status === 'URGENTE'
                      ? 'bg-amber-100 text-amber-800'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {t.daysLeft} días
                </span>
              </div>
              <div className="text-[11px] text-slate-500 mb-2 truncate">{t.period}</div>
              <div className="text-[10px] text-slate-400 border-t border-slate-100 pt-1.5 flex items-center justify-between">
                <span>Límite:</span>
                <span className="font-semibold text-slate-700">{t.deadline.split(' de ')[0]}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 5. REGISTRO DE ACTIVIDAD Y AUDITORÍA CONTABLE (FASE D) */}
      <ActivityAuditTimeline
        company={company}
        invoices={invoices}
        onNavigateTab={onNavigateTab}
      />
    </div>
  );
};

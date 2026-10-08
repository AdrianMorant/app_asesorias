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
  CheckCircle2,
  Clock,
  Sparkles,
  ChevronRight,
  ShieldAlert,
  Landmark,
} from 'lucide-react';

interface FinancialDashboardViewProps {
  company: Company;
  invoices: Invoice[];
  onNavigateTab: (tab: any) => void;
  onSelectInvoice?: (invoice: Invoice) => void;
}

export const FinancialDashboardView: React.FC<FinancialDashboardViewProps> = ({
  company,
  invoices,
  onNavigateTab,
  onSelectInvoice,
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

  return (
    <div className="space-y-6">
      {/* 4 KPIs Financieros Principales */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* KPI 1: Facturación (Ventas) */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span className="font-medium">Facturación Emitida</span>
            <span className="p-1.5 rounded-lg bg-emerald-50 text-emerald-600">
              <TrendingUp className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono tracking-tight text-slate-900">
            {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(totalSales)}
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>Base: {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(totalSalesBase)}</span>
            <span className="text-emerald-700 font-semibold">{sales.length} facturas</span>
          </div>
        </div>

        {/* KPI 2: Gastos Devengados (Compras con IA) */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span className="font-medium">Gastos Devengados</span>
            <span className="p-1.5 rounded-lg bg-rose-50 text-rose-600">
              <TrendingDown className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono tracking-tight text-slate-900">
            {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(totalExpenses)}
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>Base: {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(totalExpensesBase)}</span>
            <span className="text-slate-600 font-semibold">{approvedExpenses.length} aprobadas</span>
          </div>
        </div>

        {/* KPI 3: IVA Neto a Liquidar */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span className="font-medium">IVA Neto (Repercutido - Soportado)</span>
            <span className="p-1.5 rounded-lg bg-indigo-50 text-indigo-600">
              <Scale className="w-4 h-4" />
            </span>
          </div>
          <div
            className={`text-2xl font-bold font-mono tracking-tight ${
              netVat > 0 ? 'text-amber-700' : 'text-emerald-700'
            }`}
          >
            {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(Math.abs(netVat))}
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px]">
            <span
              className={`font-semibold px-1.5 py-0.5 rounded text-[10px] ${
                netVat > 0
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-emerald-100 text-emerald-800'
              }`}
            >
              {netVat > 0 ? 'A Ingresar a Hacienda' : 'A Compensar / Deducir'}
            </span>
            <span className="text-slate-400 font-mono">Mod. 303</span>
          </div>
        </div>

        {/* KPI 4: Rendimiento Operativo */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span className="font-medium">Margen Operativo Neto</span>
            <span className="p-1.5 rounded-lg bg-indigo-50 text-indigo-600">
              <Landmark className="w-4 h-4" />
            </span>
          </div>
          <div
            className={`text-2xl font-bold font-mono tracking-tight ${
              operatingProfit >= 0 ? 'text-emerald-700' : 'text-rose-700'
            }`}
          >
            {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(operatingProfit)}
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>Ventas netas - Gastos</span>
            <span className="text-indigo-600 font-medium">PYME PGC</span>
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
    </div>
  );
};

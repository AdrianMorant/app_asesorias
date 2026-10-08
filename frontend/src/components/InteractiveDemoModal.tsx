'use client';

import React, { useState, useEffect } from 'react';
import {
  X,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  FileText,
  Building,
  CreditCard,
  Scale,
  RotateCcw,
  Play,
  TrendingDown,
  TrendingUp,
  Receipt,
  ShieldCheck,
  Zap,
  ChevronRight,
  Layers,
} from 'lucide-react';

interface InteractiveDemoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onGoToRealApp?: () => void;
}

interface DemoInvoiceOption {
  id: string;
  provider: string;
  cif: string;
  concept: string;
  amount: number;
  base: number;
  vatRate: number;
  vatAmount: number;
  subaccount: string;
  subaccountName: string;
  bankMatch: {
    bank: string;
    description: string;
    date: string;
    amount: number;
  };
}

const DEMO_INVOICES: DemoInvoiceOption[] = [
  {
    id: 'aws',
    provider: 'Amazon Web Services EMEA SARL',
    cif: 'B84920192',
    concept: 'Infraestructura Cloud Hosting AWS EC2 & S3 (Marzo 2026)',
    amount: 121.0,
    base: 100.0,
    vatRate: 21,
    vatAmount: 21.0,
    subaccount: '628000001',
    subaccountName: 'Suministros Cloud y Servidores',
    bankMatch: {
      bank: 'Banco Santander (ES91 0049 ****)',
      description: 'CARGO TARJETA DEB - AWS EMEA LUXEMBOURG',
      date: '02/04/2026',
      amount: -121.0,
    },
  },
  {
    id: 'google',
    provider: 'Google Ireland Limited',
    cif: 'IE6388047V',
    concept: 'Suscripción Google Workspace Business Plus (Marzo 2026)',
    amount: 72.6,
    base: 60.0,
    vatRate: 21,
    vatAmount: 12.6,
    subaccount: '628000002',
    subaccountName: 'Software y Herramientas SaaS',
    bankMatch: {
      bank: 'BBVA Online (ES21 0182 ****)',
      description: 'ADEUDO SEPA DIRECT DEBIT - GOOGLE IRELAND',
      date: '03/04/2026',
      amount: -72.6,
    },
  },
];

export const InteractiveDemoModal: React.FC<InteractiveDemoModalProps> = ({
  isOpen,
  onClose,
  onGoToRealApp,
}) => {
  const [step, setStep] = useState<number>(1);
  const [selectedInvoice, setSelectedInvoice] = useState<DemoInvoiceOption>(DEMO_INVOICES[0]);
  const [aiAnalyzing, setAiAnalyzing] = useState<boolean>(false);
  const [aiAnalysisProgress, setAiAnalysisProgress] = useState<number>(0);
  const [aiLog, setAiLog] = useState<string>('');
  const [isReconciled, setIsReconciled] = useState<boolean>(false);

  // Reiniciar estado al abrir
  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setSelectedInvoice(DEMO_INVOICES[0]);
      setAiAnalyzing(false);
      setAiAnalysisProgress(0);
      setIsReconciled(false);
    }
  }, [isOpen]);

  // Simulación de extracción en vivo en el Paso 2
  useEffect(() => {
    if (step === 2) {
      setAiAnalyzing(true);
      setAiAnalysisProgress(15);
      setAiLog('Iniciando lectura multimodal con visión artificial...');

      const t1 = setTimeout(() => {
        setAiAnalysisProgress(45);
        setAiLog(`Detectado CIF ${selectedInvoice.cif} de ${selectedInvoice.provider}...`);
      }, 700);

      const t2 = setTimeout(() => {
        setAiAnalysisProgress(80);
        setAiLog(
          `Comprobación de bases: Base ${selectedInvoice.base.toFixed(2)} € + IVA 21% (${selectedInvoice.vatAmount.toFixed(
            2
          )} €) = Total ${selectedInvoice.amount.toFixed(2)} €.`
        );
      }, 1500);

      const t3 = setTimeout(() => {
        setAiAnalysisProgress(100);
        setAiLog(`Certeza: 99% - Subcuenta contable asignada: ${selectedInvoice.subaccount} (${selectedInvoice.subaccountName}).`);
        setAiAnalyzing(false);
      }, 2300);

      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
        clearTimeout(t3);
      };
    }
  }, [step, selectedInvoice]);

  if (!isOpen) return null;

  const handleNextStep = () => {
    if (step < 5) {
      setStep(step + 1);
    }
  };

  const handleRestart = () => {
    setStep(1);
    setSelectedInvoice(DEMO_INVOICES[0]);
    setAiAnalyzing(false);
    setAiAnalysisProgress(0);
    setIsReconciled(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-750 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Cabecera del Modal */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 text-white shadow-md">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-tight">
                  Demostración Interactiva Konta AI
                </h2>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  Simulación de 60 segundos
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Observa cómo la IA automatiza la ingesta, validación contable y conciliación bancaria.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleRestart}
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-all"
              title="Reiniciar demostración"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-all"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Barra de progreso de los 5 pasos */}
        <div className="px-6 py-3 bg-slate-950/40 border-b border-slate-800/80 flex items-center justify-between gap-2 overflow-x-auto">
          {[
            { num: 1, label: '1. Factura' },
            { num: 2, label: '2. Extracción IA' },
            { num: 3, label: '3. Match Banco' },
            { num: 4, label: '4. Asiento PGC' },
            { num: 5, label: '5. Impacto' },
          ].map((item) => (
            <div
              key={item.num}
              onClick={() => step > item.num && setStep(item.num)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 ${
                step === item.num
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-xs'
                  : step > item.num
                  ? 'text-slate-300 hover:bg-slate-800/60 cursor-pointer'
                  : 'text-slate-500 opacity-60'
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                  step === item.num
                    ? 'bg-cyan-500 text-slate-950 font-bold'
                    : step > item.num
                    ? 'bg-emerald-500/30 text-emerald-300 border border-emerald-500/40'
                    : 'bg-slate-800 text-slate-500'
                }`}
              >
                {step > item.num ? '✓' : item.num}
              </span>
              <span>{item.label}</span>
            </div>
          ))}
        </div>

        {/* Cuerpo del paso activo */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {/* PASO 1: SELECCIÓN DE FACTURA FICTICIA */}
          {step === 1 && (
            <div className="space-y-5 animate-in fade-in duration-200">
              <div className="text-center max-w-xl mx-auto space-y-1">
                <h3 className="text-lg font-bold text-white">
                  Paso 1: Selecciona una factura de ejemplo
                </h3>
                <p className="text-xs text-slate-400">
                  Elige uno de los siguientes documentos simulados para iniciar el procesamiento en tiempo real con Konta IA.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto">
                {DEMO_INVOICES.map((inv) => {
                  const isSelected = selectedInvoice.id === inv.id;
                  return (
                    <div
                      key={inv.id}
                      onClick={() => setSelectedInvoice(inv)}
                      className={`p-5 rounded-2xl border cursor-pointer transition-all flex flex-col justify-between space-y-4 ${
                        isSelected
                          ? 'bg-slate-800/90 border-cyan-400 shadow-lg shadow-cyan-500/10 ring-1 ring-cyan-400/50 scale-[1.01]'
                          : 'bg-slate-850/60 border-slate-750 hover:border-slate-600 hover:bg-slate-800/50'
                      }`}
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-700 text-slate-300 font-mono">
                            CIF: {inv.cif}
                          </span>
                          <span className="text-xs font-bold text-cyan-400 font-mono">
                            {inv.amount.toFixed(2)} €
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-white leading-tight">
                          {inv.provider}
                        </h4>
                        <p className="text-xs text-slate-400 line-clamp-2">
                          {inv.concept}
                        </p>
                      </div>

                      <div className="pt-3 border-t border-slate-750 flex items-center justify-between text-xs text-slate-400">
                        <span>Base: {inv.base.toFixed(2)} €</span>
                        <span>IVA 21%: {inv.vatAmount.toFixed(2)} €</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="flex justify-center pt-2">
                <button
                  onClick={handleNextStep}
                  className="px-6 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 shadow-lg shadow-cyan-500/20 active:scale-95 transition-all"
                >
                  <span>Procesar {selectedInvoice.provider.split(' ')[0]} con IA</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* PASO 2: EXTRACCIÓN IA EN VIVO */}
          {step === 2 && (
            <div className="space-y-5 animate-in fade-in duration-200">
              <div className="text-center max-w-xl mx-auto space-y-1">
                <h3 className="text-lg font-bold text-white">
                  Paso 2: Extracción y Validación Multimodal
                </h3>
                <p className="text-xs text-slate-400">
                  La IA examina la factura en tiempo real, verifica el CIF oficial en la AEAT y comprueba el cuadre aritmético.
                </p>
              </div>

              {/* Animación del escáner */}
              <div className="p-5 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-4 max-w-xl mx-auto">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 font-mono flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-cyan-400 animate-spin" />
                    {aiAnalyzing ? 'Extrayendo con Gemini Vision...' : 'Extracción completada'}
                  </span>
                  <span className="text-cyan-400 font-mono font-bold">
                    {aiAnalysisProgress}%
                  </span>
                </div>

                <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500 ease-out"
                    style={{ width: `${aiAnalysisProgress}%` }}
                  />
                </div>

                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-300 min-h-[46px] flex items-center">
                  <span>{aiLog}</span>
                </div>
              </div>

              {/* Ficha de resultados extraídos */}
              {!aiAnalyzing && (
                <div className="p-5 rounded-2xl bg-slate-850/80 border border-slate-700/80 max-w-xl mx-auto space-y-3 animate-in fade-in zoom-in-95 duration-200">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      Resultado del Triaje Contable
                    </span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      Certeza IA: 99%
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
                      <span className="text-[10px] text-slate-400 block">Proveedor y NIF</span>
                      <strong className="text-white block mt-0.5">{selectedInvoice.provider}</strong>
                      <span className="text-[10px] font-mono text-cyan-400">CIF: {selectedInvoice.cif}</span>
                    </div>

                    <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
                      <span className="text-[10px] text-slate-400 block">Subcuenta PGC Sugerida</span>
                      <strong className="text-white block mt-0.5">{selectedInvoice.subaccount}</strong>
                      <span className="text-[10px] text-slate-400">{selectedInvoice.subaccountName}</span>
                    </div>

                    <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
                      <span className="text-[10px] text-slate-400 block">Base Imponible</span>
                      <strong className="text-emerald-400 text-sm font-mono mt-0.5 block">
                        {selectedInvoice.base.toFixed(2)} €
                      </strong>
                    </div>

                    <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
                      <span className="text-[10px] text-slate-400 block">IVA Soportado (21%)</span>
                      <strong className="text-cyan-400 text-sm font-mono mt-0.5 block">
                        {selectedInvoice.vatAmount.toFixed(2)} €
                      </strong>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex justify-center pt-2">
                <button
                  disabled={aiAnalyzing}
                  onClick={handleNextStep}
                  className="px-6 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-2 shadow-lg shadow-cyan-500/20 active:scale-95 transition-all"
                >
                  <span>Siguiente: Buscar Cargo Bancario</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* PASO 3: DETECCIÓN BANCARIA */}
          {step === 3 && (
            <div className="space-y-5 animate-in fade-in duration-200">
              <div className="text-center max-w-xl mx-auto space-y-1">
                <h3 className="text-lg font-bold text-white">
                  Paso 3: Conciliación Bancaria Semántica
                </h3>
                <p className="text-xs text-slate-400">
                  La IA rastrea tus extractos bancarios conectados y encuentra el cargo exacto correspondiente a la factura.
                </p>
              </div>

              {/* Comparativa Factura vs Banco */}
              <div className="max-w-2xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
                {/* Factura */}
                <div className="p-4 rounded-2xl bg-slate-850 border border-slate-700 space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span className="font-semibold text-slate-300">Documento Factura</span>
                    <Receipt className="w-4 h-4 text-cyan-400" />
                  </div>
                  <div className="text-base font-bold text-white">
                    {selectedInvoice.provider.split(' ')[0]}
                  </div>
                  <div className="text-xl font-bold font-mono text-cyan-400">
                    {selectedInvoice.amount.toFixed(2)} €
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Concepto: {selectedInvoice.concept}
                  </div>
                </div>

                {/* Movimiento Bancario Encontrado */}
                <div className="p-4 rounded-2xl bg-indigo-950/40 border border-indigo-500/40 space-y-2 shadow-md">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-indigo-300 flex items-center gap-1.5">
                      <CreditCard className="w-4 h-4 text-indigo-400" />
                      Movimiento Bancario Detectado
                    </span>
                    <span className="text-[10px] font-bold px-2 py-0.2 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      Coincidencia 100%
                    </span>
                  </div>
                  <div className="text-base font-bold text-white">
                    {selectedInvoice.bankMatch.bank}
                  </div>
                  <div className="text-xl font-bold font-mono text-rose-400">
                    {selectedInvoice.bankMatch.amount.toFixed(2)} €
                  </div>
                  <div className="text-[11px] font-mono text-slate-300">
                    {selectedInvoice.bankMatch.description}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    Fecha cargo: {selectedInvoice.bankMatch.date}
                  </div>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 text-xs text-emerald-200 max-w-xl mx-auto flex items-center gap-2.5">
                <Sparkles className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>
                  <strong>Diagnóstico de la IA:</strong> El importe (-{selectedInvoice.amount.toFixed(2)} €) y el emisor coinciden en un 100%. Todo listo para vincular el documento y saldar la deuda.
                </span>
              </div>

              <div className="flex justify-center pt-2">
                <button
                  onClick={handleNextStep}
                  className="px-6 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 shadow-lg shadow-cyan-500/20 active:scale-95 transition-all"
                >
                  <span>Siguiente: Generar Asiento Contable</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* PASO 4: CONFIRMACIÓN Y ASIENTO CONTABLE */}
          {step === 4 && (
            <div className="space-y-5 animate-in fade-in duration-200">
              <div className="text-center max-w-xl mx-auto space-y-1">
                <h3 className="text-lg font-bold text-white">
                  Paso 4: Asiento en Partida Doble (PGC)
                </h3>
                <p className="text-xs text-slate-400">
                  La IA genera el asiento contable reglamentario en el Libro Diario y salda la cuenta de proveedores.
                </p>
              </div>

              {/* Tabla del asiento contable */}
              <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 max-w-2xl mx-auto space-y-3">
                <div className="flex items-center justify-between text-xs pb-2 border-b border-slate-800">
                  <span className="font-bold text-white">
                    Asiento Nº 2026/0418 — Fecha: {selectedInvoice.bankMatch.date}
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                    Cuadrado al céntimo
                  </span>
                </div>

                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-400 border-b border-slate-800/60 text-left">
                      <th className="py-2 px-2">Cuenta</th>
                      <th className="py-2 px-2">Descripción</th>
                      <th className="py-2 px-2 text-right">Debe (€)</th>
                      <th className="py-2 px-2 text-right">Haber (€)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/40 text-slate-200 font-mono">
                    <tr>
                      <td className="py-2.5 px-2 text-cyan-400">{selectedInvoice.subaccount}</td>
                      <td className="py-2.5 px-2 font-sans">{selectedInvoice.subaccountName}</td>
                      <td className="py-2.5 px-2 text-right text-emerald-400">{selectedInvoice.base.toFixed(2)}</td>
                      <td className="py-2.5 px-2 text-right text-slate-500">0.00</td>
                    </tr>
                    <tr>
                      <td className="py-2.5 px-2 text-cyan-400">472000021</td>
                      <td className="py-2.5 px-2 font-sans">H.P. IVA Soportado (21%)</td>
                      <td className="py-2.5 px-2 text-right text-emerald-400">{selectedInvoice.vatAmount.toFixed(2)}</td>
                      <td className="py-2.5 px-2 text-right text-slate-500">0.00</td>
                    </tr>
                    <tr>
                      <td className="py-2.5 px-2 text-cyan-400">572000001</td>
                      <td className="py-2.5 px-2 font-sans">{selectedInvoice.bankMatch.bank.split('(')[0]}</td>
                      <td className="py-2.5 px-2 text-right text-slate-500">0.00</td>
                      <td className="py-2.5 px-2 text-right text-rose-400">{selectedInvoice.amount.toFixed(2)}</td>
                    </tr>
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-slate-700 font-bold text-white">
                      <td colSpan={2} className="py-2.5 px-2 text-right">Totales:</td>
                      <td className="py-2.5 px-2 text-right text-emerald-400 font-mono">{selectedInvoice.amount.toFixed(2)} €</td>
                      <td className="py-2.5 px-2 text-right text-emerald-400 font-mono">{selectedInvoice.amount.toFixed(2)} €</td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              <div className="flex justify-center pt-2">
                <button
                  onClick={() => {
                    setIsReconciled(true);
                    handleNextStep();
                  }}
                  className="px-7 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-2 shadow-lg shadow-emerald-500/20 active:scale-95 transition-all"
                >
                  <ShieldCheck className="w-4 h-4" />
                  <span>Conciliar y Contabilizar en 1 Clic</span>
                </button>
              </div>
            </div>
          )}

          {/* PASO 5: IMPACTO EN TIEMPO REAL EN EL NEGOCIO */}
          {step === 5 && (
            <div className="space-y-5 animate-in fade-in duration-200">
              <div className="text-center max-w-xl mx-auto space-y-1">
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-bold mb-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ¡Factura Contabilizada y Conciliada con Éxito!
                </div>
                <h3 className="text-xl font-bold text-white">
                  Impacto Inmediato en tus Finanzas
                </h3>
                <p className="text-xs text-slate-400">
                  Observa cómo se han actualizado automáticamente tus indicadores ejecutivos sin tocar una sola celda de Excel.
                </p>
              </div>

              {/* Cuadrícula de KPIs actualizados */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto">
                {/* KPI 1: Saldo Tesorería */}
                <div className="p-4 rounded-2xl bg-slate-850 border border-slate-750 space-y-1.5">
                  <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">
                    Saldo Bancario Real (572)
                  </span>
                  <div className="text-xl font-bold font-mono text-white">
                    18.329,00 €
                  </div>
                  <div className="flex items-center gap-1 text-[11px] text-rose-400">
                    <TrendingDown className="w-3.5 h-3.5" />
                    <span>-{selectedInvoice.amount.toFixed(2)} € pagados</span>
                  </div>
                  <span className="text-[10px] text-slate-500 block">
                    Conciliado con Santander
                  </span>
                </div>

                {/* KPI 2: Gastos Deducibles */}
                <div className="p-4 rounded-2xl bg-slate-850 border border-slate-750 space-y-1.5">
                  <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">
                    Gasto Computado (PyG)
                  </span>
                  <div className="text-xl font-bold font-mono text-white">
                    +{selectedInvoice.base.toFixed(2)} €
                  </div>
                  <div className="flex items-center gap-1 text-[11px] text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Base 100% deducible</span>
                  </div>
                  <span className="text-[10px] text-slate-500 block">
                    Cuenta {selectedInvoice.subaccount}
                  </span>
                </div>

                {/* KPI 3: Modelo 303 (IVA) */}
                <div className="p-4 rounded-2xl bg-slate-850 border border-slate-750 space-y-1.5">
                  <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">
                    Ahorro Fiscal en Modelo 303
                  </span>
                  <div className="text-xl font-bold font-mono text-cyan-400">
                    -{selectedInvoice.vatAmount.toFixed(2)} €
                  </div>
                  <div className="flex items-center gap-1 text-[11px] text-cyan-300">
                    <Scale className="w-3.5 h-3.5" />
                    <span>IVA deducible sumado</span>
                  </div>
                  <span className="text-[10px] text-slate-500 block">
                    Casilla 28 de la AEAT
                  </span>
                </div>
              </div>

              {/* Botones de acción final */}
              <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-3">
                <button
                  onClick={handleRestart}
                  className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Probar con otra factura</span>
                </button>

                <button
                  onClick={() => {
                    onClose();
                    onGoToRealApp?.();
                  }}
                  className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/25 active:scale-95 transition-all"
                >
                  <span>Ir a mi Entorno de Trabajo Real</span>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

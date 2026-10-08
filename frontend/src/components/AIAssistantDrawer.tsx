'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Company, Invoice, SalesInvoice } from '@/types';
import { ActiveNavTab, WorkspaceMode } from '@/components/Sidebar';
import {
  Sparkles,
  X,
  Send,
  TrendingUp,
  TrendingDown,
  Scale,
  Receipt,
  Landmark,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  RefreshCw,
  Bot,
  User,
  Clock,
  ShieldAlert,
  Zap,
  Lightbulb,
  FileQuestion,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';

export interface AIMessageMetric {
  label: string;
  value: string;
  trend?: string;
  status?: 'good' | 'warning' | 'danger' | 'neutral';
}

export interface AIMessageAction {
  label: string;
  icon?: 'review' | 'taxes' | 'banking' | 'journal' | 'upload' | 'inspect';
  onClick: () => void;
  variant?: 'primary' | 'secondary' | 'warning';
}

export interface AIMessage {
  id: string;
  sender: 'ai' | 'user';
  timestamp: string;
  text: string;
  metrics?: AIMessageMetric[];
  table?: {
    headers: string[];
    rows: {
      id?: string;
      cols: string[];
      badge?: { text: string; color: 'red' | 'amber' | 'emerald' };
    }[];
  };
  actions?: AIMessageAction[];
}

interface AIAssistantDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  company: Company;
  invoices: Invoice[];
  sales?: SalesInvoice[];
  onNavigateTab: (tab: ActiveNavTab) => void;
  onSelectInvoice?: (invoice: Invoice) => void;
  mode?: WorkspaceMode;
  initialQuery?: string;
}

export const AIAssistantDrawer: React.FC<AIAssistantDrawerProps> = ({
  isOpen,
  onClose,
  company,
  invoices,
  sales = [],
  onNavigateTab,
  onSelectInvoice,
  mode = 'client',
  initialQuery,
}) => {
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Cálculos dinámicos en base a los datos reales
  const totalSales = sales.reduce((acc, s) => acc + (s.total_amount || 0), 0);
  const totalSalesTax = sales.reduce((acc, s) => acc + (s.total_tax || 0), 0);
  const totalExpenses = invoices.reduce((acc, i) => acc + (i.total_amount || 0), 0);
  const totalExpensesTax = invoices.reduce((acc, i) => acc + (i.total_tax || 0), 0);
  const redInvoices = invoices.filter((i) => i.status === 'RED');
  const yellowInvoices = invoices.filter((i) => i.status === 'YELLOW');
  const greenInvoices = invoices.filter((i) => i.status === 'GREEN');
  const netVat = totalSalesTax - totalExpensesTax;
  const netProfit = totalSales - totalExpenses;

  // Auto scroll al último mensaje
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 250);
      scrollToBottom();
      if (initialQuery) {
        setTimeout(() => {
          handleSendMessage(initialQuery);
        }, 350);
      }
    }
  }, [isOpen, initialQuery]);

  // Mensaje de bienvenida inicial
  useEffect(() => {
    if (messages.length === 0) {
      const pendingCount = redInvoices.length + yellowInvoices.length;
      const initialText = `Hola, soy tu **Copiloto Financiero IA**. He sincronizado los libros de **${company.razon_social}** (CIF: \`${company.cif}\`).
${
  pendingCount > 0
    ? `He detectado **${pendingCount} documento(s)** que requieren tu atención inmediata.`
    : 'Tu contabilidad está al día y validada según normativa AEAT.'
} ¿Qué consulta deseas realizar?`;

      setMessages([
        {
          id: 'welcome_1',
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: initialText,
          metrics: [
            {
              label: 'Facturas a Revisar',
              value: `${pendingCount}`,
              status: pendingCount > 0 ? (redInvoices.length > 0 ? 'danger' : 'warning') : 'good',
            },
            {
              label: 'IVA Estimado 1T',
              value: `${Math.abs(netVat).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`,
              trend: netVat > 0 ? 'A ingresar' : 'A compensar',
              status: netVat > 0 ? 'warning' : 'good',
            },
            {
              label: 'Margen Operativo',
              value: `${netProfit.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`,
              status: netProfit >= 0 ? 'good' : 'danger',
            },
          ],
          actions: [
            ...(pendingCount > 0
              ? [
                  {
                    label: `Revisar ${pendingCount} facturas prioritarias`,
                    icon: 'review' as const,
                    onClick: () => {
                      onNavigateTab('expenses');
                      onClose();
                    },
                    variant: 'primary' as const,
                  },
                ]
              : []),
            {
              label: 'Ver estimación Modelo 303',
              icon: 'taxes' as const,
              onClick: () => {
                onNavigateTab('taxes');
                onClose();
              },
              variant: 'secondary' as const,
            },
          ],
        },
      ]);
    }
  }, [company.id, invoices.length, sales.length]);

  // Preguntas sugeridas
  const quickQuestions = [
    { text: '¿Cuánto he gastado este mes?', icon: TrendingDown },
    { text: '¿Qué facturas requieren revisión?', icon: AlertTriangle },
    { text: 'Estimación de IVA (Mod. 303)', icon: Scale },
    { text: 'Movimientos bancarios pendientes', icon: Landmark },
    { text: 'Resumen de margen y rentabilidad', icon: TrendingUp },
  ];

  // Motor de respuesta simulada inteligente del Copiloto
  const handleSendMessage = (queryText: string) => {
    if (!queryText.trim()) return;

    const userMsg: AIMessage = {
      id: `usr_${Date.now()}`,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: queryText,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setIsTyping(true);

    // Simular tiempo de razonamiento de la IA
    setTimeout(() => {
      const q = queryText.toLowerCase();
      let response: AIMessage;

      if (q.includes('gastado') || q.includes('gasto') || q.includes('compras')) {
        response = {
          id: `ai_${Date.now()}`,
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: `En el ejercicio actual para **${company.razon_social}**, se han registrado **${invoices.length} facturas de proveedores** con un volumen total de gastos devengados de **${totalExpenses.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €**.
El IVA soportado acumulado deducible asciende a **${totalExpensesTax.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €**.`,
          metrics: [
            {
              label: 'Gasto Total Bruto',
              value: `${totalExpenses.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €`,
              status: 'neutral',
            },
            {
              label: 'IVA Soportado Deducible',
              value: `${totalExpensesTax.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €`,
              status: 'good',
            },
            {
              label: 'Facturas Validadas',
              value: `${greenInvoices.length} de ${invoices.length}`,
              status: greenInvoices.length === invoices.length ? 'good' : 'warning',
            },
          ],
          actions: [
            {
              label: 'Ver detalle en Gastos / Compras',
              icon: 'review',
              onClick: () => {
                onNavigateTab('expenses');
                onClose();
              },
              variant: 'primary',
            },
            {
              label: 'Inspeccionar Libro Diario PGC',
              icon: 'journal',
              onClick: () => {
                onNavigateTab('journal');
                onClose();
              },
              variant: 'secondary',
            },
          ],
        };
      } else if (q.includes('revisi') || q.includes('rojo') || q.includes('amarillo') || q.includes('pendient') || q.includes('error')) {
        const criticalInvoices = invoices.filter((i) => i.status !== 'GREEN').slice(0, 3);
        const redCount = redInvoices.length;
        const yellowCount = yellowInvoices.length;

        response = {
          id: `ai_${Date.now()}`,
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: redCount + yellowCount > 0
            ? `Actualmente hay **${redCount + yellowCount} factura(s)** en semáforo de atención.
• **${redCount} en Rojo:** Anomalías críticas (descuadre aritmético >0.01 € o CIF no conforme AEAT).
• **${yellowCount} en Amarillo:** Sugerencia de subcuenta contable o proveedor nuevo pendiente de confirmación.`
            : `¡Excelente noticia! Todas las facturas registradas están en estado **Verde (100% validadas)** con CIF verificado y asiento cuadrado.`,
          metrics: [
            { label: 'Bloqueo Rojo', value: `${redCount}`, status: redCount > 0 ? 'danger' : 'good' },
            { label: 'Triaje Amarillo', value: `${yellowCount}`, status: yellowCount > 0 ? 'warning' : 'good' },
            { label: 'Aprobadas Verdes', value: `${greenInvoices.length}`, status: 'good' },
          ],
          table: criticalInvoices.length > 0 ? {
            headers: ['Proveedor', 'CIF', 'Total', 'Alerta IA'],
            rows: criticalInvoices.map((inv) => ({
              id: inv.id,
              cols: [
                inv.issuer_name || 'Desconocido',
                inv.issuer_cif || '---',
                `${inv.total_amount?.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €`,
              ],
              badge: {
                text: inv.status === 'RED' ? 'Descuadre / CIF' : 'Subcuenta sugerida',
                color: inv.status === 'RED' ? 'red' : 'amber',
              },
            })),
          } : undefined,
          actions: [
            {
              label: 'Abrir Consola de Triaje',
              icon: 'review',
              onClick: () => {
                onNavigateTab('expenses');
                if (criticalInvoices[0] && onSelectInvoice) {
                  onSelectInvoice(criticalInvoices[0]);
                }
                onClose();
              },
              variant: 'primary',
            },
          ],
        };
      } else if (q.includes('iva') || q.includes('303') || q.includes('impuesto') || q.includes('fiscal') || q.includes('hacienda')) {
        response = {
          id: `ai_${Date.now()}`,
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: `Cálculo en tiempo real para la autoliquidación del **Modelo 303 (IVA)**:
• **IVA Repercutido (Ventas):** ${totalSalesTax.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
• **IVA Soportado Deducible (Gastos):** ${totalExpensesTax.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €
• **Resultado Neto:** **${Math.abs(netVat).toLocaleString('es-ES', { minimumFractionDigits: 2 })} €** (${netVat > 0 ? 'A ingresar en AEAT' : 'A compensar en próximos periodos'}).`,
          metrics: [
            {
              label: 'Resultado Mod. 303',
              value: `${Math.abs(netVat).toLocaleString('es-ES', { minimumFractionDigits: 2 })} €`,
              trend: netVat > 0 ? 'A pagar a Hacienda' : 'A tu favor (Compensar)',
              status: netVat > 0 ? 'warning' : 'good',
            },
            {
              label: 'IVA Repercutido',
              value: `${totalSalesTax.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €`,
              status: 'neutral',
            },
            {
              label: 'IVA Soportado',
              value: `${totalExpensesTax.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €`,
              status: 'good',
            },
          ],
          actions: [
            {
              label: 'Ver Borrador Oficial Modelo 303',
              icon: 'taxes',
              onClick: () => {
                onNavigateTab('taxes');
                onClose();
              },
              variant: 'primary',
            },
          ],
        };
      } else if (q.includes('banco') || q.includes('movimiento') || q.includes('concilia') || q.includes('extracto')) {
        response = {
          id: `ai_${Date.now()}`,
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: `El módulo de **Conciliación Bancaria Semántica** analiza la cuenta de tesorería (subcuenta 572).
El motor de reglas empareja automáticamente los apuntes bancarios con facturas validadas cruzando emisor, importe y ventana temporal (+/- 5 días).`,
          metrics: [
            { label: 'Estado Bancario', value: 'Sincronizado', status: 'good' },
            { label: 'Algoritmo de Matching', value: 'Semántico + Fecha', status: 'neutral' },
          ],
          actions: [
            {
              label: 'Ir a Conciliación Bancaria',
              icon: 'banking',
              onClick: () => {
                onNavigateTab('banking');
                onClose();
              },
              variant: 'primary',
            },
          ],
        };
      } else {
        // Respuesta general con análisis contextual
        response = {
          id: `ai_${Date.now()}`,
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: `He analizado la información contable disponible para **${company.razon_social}**.
Resumen global:
• **Facturación emitida:** ${totalSales.toLocaleString('es-ES', { minimumFractionDigits: 2 })} € (${sales.length} ventas)
• **Gastos devengados:** ${totalExpenses.toLocaleString('es-ES', { minimumFractionDigits: 2 })} € (${invoices.length} facturas)
• **Resultado neto estimado:** **${netProfit.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €**
• **Documentos pendientes de confirmación:** ${redInvoices.length + yellowInvoices.length}`,
          metrics: [
            { label: 'Ingresos', value: `${totalSales.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €`, status: 'good' },
            { label: 'Gastos', value: `${totalExpenses.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €`, status: 'neutral' },
            { label: 'Resultado', value: `${netProfit.toLocaleString('es-ES', { minimumFractionDigits: 2 })} €`, status: netProfit >= 0 ? 'good' : 'danger' },
          ],
          actions: [
            {
              label: 'Ver Panel Financiero Completo',
              icon: 'journal',
              onClick: () => {
                onNavigateTab('dashboard');
                onClose();
              },
              variant: 'primary',
            },
          ],
        };
      }

      setMessages((prev) => [...prev, response]);
      setIsTyping(false);
    }, 700);
  };

  const clearChat = () => {
    setMessages([]);
  };

  if (!isOpen) return null;

  const isAdvisor = mode === 'advisor';

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop desenfocado */}
      <div
        className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm transition-opacity animate-in fade-in duration-200"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-xl bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col text-slate-100 animate-in slide-in-from-right duration-300">
          
          {/* Header del Copiloto */}
          <div
            className={`p-4 border-b flex items-center justify-between transition-colors ${
              isAdvisor
                ? 'bg-slate-900/90 border-blue-900/50'
                : 'bg-slate-900/90 border-slate-800'
            }`}
          >
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center shadow-lg ${
                  isAdvisor
                    ? 'bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow-blue-500/20'
                    : 'bg-gradient-to-br from-emerald-500 to-teal-700 text-white shadow-emerald-500/20'
                }`}
              >
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-white tracking-wide">
                    Copiloto Konta IA
                  </h2>
                  <span className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    En línea
                  </span>
                </div>
                <p className="text-xs text-slate-400 truncate max-w-[260px]">
                  {company.razon_social} <span className="text-slate-500 font-mono">({company.cif})</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={clearChat}
                title="Reiniciar conversación"
                className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 transition-colors text-xs"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
              <button
                onClick={onClose}
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Quick Questions Pills */}
          <div className="px-4 py-2.5 bg-slate-950/60 border-b border-slate-800/70 overflow-x-auto no-scrollbar flex items-center gap-2">
            <span className="text-[11px] font-medium text-slate-400 flex items-center gap-1 whitespace-nowrap">
              <Lightbulb className="w-3 h-3 text-amber-400" />
              Preguntas clave:
            </span>
            {quickQuestions.map((q, idx) => {
              const Icon = q.icon;
              return (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(q.text)}
                  className="text-[11px] whitespace-nowrap px-2.5 py-1 rounded-full bg-slate-800/90 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700/60 transition-all flex items-center gap-1.5 active:scale-95"
                >
                  <Icon className="w-3 h-3 text-indigo-400" />
                  {q.text}
                </button>
              );
            })}
          </div>

          {/* Lista de Mensajes */}
          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.sender === 'ai' && (
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                      isAdvisor
                        ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                        : 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30'
                    }`}
                  >
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`max-w-[85%] rounded-2xl p-4 space-y-3.5 shadow-md ${
                    msg.sender === 'user'
                      ? isAdvisor
                        ? 'bg-blue-600 text-white rounded-br-sm'
                        : 'bg-indigo-600 text-white rounded-br-sm'
                      : 'bg-slate-800/80 border border-slate-700/70 text-slate-200 rounded-bl-sm'
                  }`}
                >
                  {/* Texto principal */}
                  <div className="text-xs leading-relaxed whitespace-pre-line font-normal">
                    {msg.text.split('**').map((part, i) =>
                      i % 2 === 1 ? <strong key={i} className="font-semibold text-white">{part}</strong> : part
                    )}
                  </div>

                  {/* Tarjetas de Métricas Estructuradas */}
                  {msg.metrics && msg.metrics.length > 0 && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1">
                      {msg.metrics.map((m, i) => (
                        <div
                          key={i}
                          className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-700/60 flex flex-col justify-between"
                        >
                          <span className="text-[10px] text-slate-400 font-medium truncate">
                            {m.label}
                          </span>
                          <div className="text-sm font-bold font-mono text-white mt-1">
                            {m.value}
                          </div>
                          {m.trend && (
                            <span
                              className={`text-[9px] mt-1 font-semibold ${
                                m.status === 'good'
                                  ? 'text-emerald-400'
                                  : m.status === 'danger'
                                  ? 'text-rose-400'
                                  : m.status === 'warning'
                                  ? 'text-amber-400'
                                  : 'text-slate-400'
                              }`}
                            >
                              {m.trend}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Mini-tabla si existe */}
                  {msg.table && (
                    <div className="rounded-xl border border-slate-700/60 overflow-hidden bg-slate-900/70 text-[11px]">
                      <table className="w-full text-left">
                        <thead className="bg-slate-950/70 text-slate-400 text-[10px] uppercase font-semibold">
                          <tr>
                            {msg.table.headers.map((h, i) => (
                              <th key={i} className="p-2 border-b border-slate-800">
                                {h}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/80">
                          {msg.table.rows.map((r, ri) => (
                            <tr key={ri} className="hover:bg-slate-800/40">
                              {r.cols.map((c, ci) => (
                                <td key={ci} className="p-2 text-slate-300 font-mono text-[10px]">
                                  {c}
                                </td>
                              ))}
                              {r.badge && (
                                <td className="p-2">
                                  <span
                                    className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                      r.badge.color === 'red'
                                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                                        : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                    }`}
                                  >
                                    {r.badge.text}
                                  </span>
                                </td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Botones de acción rápida interactiva */}
                  {msg.actions && msg.actions.length > 0 && (
                    <div className="pt-2 flex flex-wrap gap-2 border-t border-slate-700/50">
                      {msg.actions.map((act, ai) => (
                        <button
                          key={ai}
                          onClick={act.onClick}
                          className={`text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all shadow-sm ${
                            act.variant === 'primary'
                              ? isAdvisor
                                ? 'bg-blue-600 hover:bg-blue-500 text-white'
                                : 'bg-emerald-600 hover:bg-emerald-500 text-white'
                              : 'bg-slate-700 hover:bg-slate-600 text-slate-200'
                          }`}
                        >
                          {act.label}
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="flex justify-end text-[9px] text-slate-400">
                    {msg.timestamp}
                  </div>
                </div>

                {msg.sender === 'user' && (
                  <div className="w-7 h-7 rounded-lg bg-slate-700 text-slate-200 flex items-center justify-center shrink-0 mt-0.5">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))}

            {isTyping && (
              <div className="flex gap-3 items-center text-xs text-slate-400 animate-pulse">
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                    isAdvisor ? 'bg-blue-600/20 text-blue-400' : 'bg-emerald-600/20 text-emerald-400'
                  }`}
                >
                  <Bot className="w-4 h-4 animate-spin" />
                </div>
                <span>El Copiloto IA está analizando los datos fiscales y libros diarios...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Footer con Input */}
          <div className="p-3.5 bg-slate-950/80 border-t border-slate-800">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage(inputValue);
              }}
              className="flex items-center gap-2"
            >
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Pregunta a la IA sobre facturas, IVA, banco, gastos..."
                className="flex-1 bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
              />
              <button
                type="submit"
                disabled={!inputValue.trim() || isTyping}
                className={`p-2.5 rounded-xl font-medium transition-all ${
                  inputValue.trim() && !isTyping
                    ? isAdvisor
                      ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/30'
                      : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/30'
                    : 'bg-slate-800 text-slate-600 cursor-not-allowed'
                }`}
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
            <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500 px-1">
              <span>IA Contextual conectada a AEAT y PGC</span>
              <span>Konta Copilot v2.4</span>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

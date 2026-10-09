'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Bell,
  X,
  AlertTriangle,
  Landmark,
  Scale,
  FileText,
  CheckCircle2,
  ChevronRight,
  Filter,
  CheckCheck,
  Sparkles,
  Clock,
  ArrowRight,
  Scissors,
} from 'lucide-react';
import { Invoice, Company } from '@/types';
import { ActiveNavTab } from './Sidebar';

export type NotificationType = 'attention' | 'banking' | 'tax' | 'document' | 'system';

export interface AppNotification {
  id: string;
  type: NotificationType;
  title: string;
  description: string;
  timestamp: string;
  timeAgo: string;
  isRead: boolean;
  priority: 'high' | 'medium' | 'low';
  actionLabel?: string;
  actionTab?: ActiveNavTab;
  invoiceId?: string;
}

interface NotificationCenterDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  invoices: Invoice[];
  company: Company;
  onNavigateTab: (tab: ActiveNavTab) => void;
  onSelectInvoice?: (invoice: Invoice) => void;
}

const STORAGE_READ_NOTIFICATIONS_KEY = 'konta_read_notifications';

export const NotificationCenterDrawer: React.FC<NotificationCenterDrawerProps> = ({
  isOpen,
  onClose,
  invoices,
  company,
  onNavigateTab,
  onSelectInvoice,
}) => {
  const [readIds, setReadIds] = useState<string[]>([]);
  const [selectedFilter, setSelectedFilter] = useState<'all' | NotificationType>('all');

  // Cargar notificaciones leídas de localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const stored = localStorage.getItem(STORAGE_READ_NOTIFICATIONS_KEY);
      if (stored) {
        setReadIds(JSON.parse(stored));
      }
    } catch {
      // Ignorar
    }
  }, []);

  const saveReadIds = (newReadIds: string[]) => {
    setReadIds(newReadIds);
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem(STORAGE_READ_NOTIFICATIONS_KEY, JSON.stringify(newReadIds));
      } catch {
        // Ignorar
      }
    }
  };

  // Construir las alertas dinámicas en base al estado del sistema
  const allNotifications: AppNotification[] = useMemo(() => {
    const list: AppNotification[] = [];

    // 1. Alertas de Facturas Rojas (Atención Requerida)
    const redInvoices = invoices.filter((i) => i.status === 'RED');
    redInvoices.forEach((inv) => {
      const reason = inv.status_reasons?.[0] || 'Descuadre aritmético o CIF no verificado';
      list.push({
        id: `notif-red-${inv.id}`,
        type: 'attention',
        title: `Factura ${inv.invoice_number || 'S/N'} bloqueada`,
        description: `${inv.issuer_name || 'Proveedor'}: ${reason}`,
        timestamp: inv.created_at || new Date().toISOString(),
        timeAgo: 'Atención requerida',
        isRead: readIds.includes(`notif-red-${inv.id}`),
        priority: 'high',
        actionLabel: 'Revisar Factura',
        actionTab: 'expenses',
        invoiceId: inv.id,
      });
    });

    // 2. Alertas de Facturas Amarillas (Revisión de subcuenta / nuevo proveedor)
    const yellowInvoices = invoices.filter((i) => i.status === 'YELLOW');
    if (yellowInvoices.length > 0) {
      list.push({
        id: 'notif-yellow-bulk',
        type: 'attention',
        title: `${yellowInvoices.length} facturas con subcuenta sugerida`,
        description: `Konta IA asignó cuentas contables PGC recomendadas que requieren confirmación rápida.`,
        timestamp: new Date().toISOString(),
        timeAgo: 'Hoy',
        isRead: readIds.includes('notif-yellow-bulk'),
        priority: 'medium',
        actionLabel: 'Validar Sugerencias',
        actionTab: 'expenses',
      });
    }

    // 3. Alertas de Bancos (Conciliación pendiente)
    list.push({
      id: 'notif-bank-reconcile',
      type: 'banking',
      title: 'Conciliación bancaria pendiente',
      description: 'Se han detectado movimientos de Santander y BBVA con coincidencia semántica disponibles.',
      timestamp: new Date().toISOString(),
      timeAgo: 'Hace 2 horas',
      isRead: readIds.includes('notif-bank-reconcile'),
      priority: 'high',
      actionLabel: 'Conciliar en 1 Clic',
      actionTab: 'banking',
    });

    // 4. Alertas Fiscales (Cuenta atrás Modelo 303 y 111)
    list.push({
      id: 'notif-tax-303-deadline',
      type: 'tax',
      title: 'Liquidación 1T 2026: 13 días restantes',
      description: 'El plazo reglamentario para el Modelo 303 (IVA) y Modelo 111 (IRPF) finaliza el 20 de abril.',
      timestamp: new Date().toISOString(),
      timeAgo: 'AEAT Calendario',
      isRead: readIds.includes('notif-tax-303-deadline'),
      priority: 'high',
      actionLabel: 'Ver Modelo 303',
      actionTab: 'taxes',
    });

    // 5. Alertas de Documentos Multifactura (MF)
    const mfInvoices = invoices.filter((i) => i.es_multifactura);
    if (mfInvoices.length > 0) {
      list.push({
        id: 'notif-mf-splitter',
        type: 'document',
        title: 'Documento compuesto multifactura (MF)',
        description: `Detectadas páginas con múltiples facturas listas para segregación automática.`,
        timestamp: new Date().toISOString(),
        timeAgo: 'Ayer',
        isRead: readIds.includes('notif-mf-splitter'),
        priority: 'medium',
        actionLabel: 'Abrir Maquetador MF',
        actionTab: 'expenses',
        invoiceId: mfInvoices[0].id,
      });
    }

    // 6. Mensaje de bienvenida de IA
    list.push({
      id: 'notif-welcome-agent',
      type: 'system',
      title: 'Konta Copilot activo y supervisando',
      description: `Los libros contables y reglas tributarias de ${company.razon_social} están sincronizados.`,
      timestamp: new Date().toISOString(),
      timeAgo: 'Sistema',
      isRead: readIds.includes('notif-welcome-agent'),
      priority: 'low',
    });

    return list;
  }, [invoices, company, readIds]);

  const unreadCount = allNotifications.filter((n) => !n.isRead).length;

  const filteredNotifications = allNotifications.filter((n) => {
    if (selectedFilter === 'all') return true;
    return n.type === selectedFilter;
  });

  const markAllAsRead = () => {
    const allIds = allNotifications.map((n) => n.id);
    saveReadIds(allIds);
  };

  const markAsRead = (id: string) => {
    if (!readIds.includes(id)) {
      saveReadIds([...readIds, id]);
    }
  };

  const handleActionClick = (notif: AppNotification) => {
    markAsRead(notif.id);
    if (notif.actionTab) {
      onNavigateTab(notif.actionTab);
    }
    if (notif.invoiceId && onSelectInvoice) {
      const targetInv = invoices.find((i) => i.id === notif.invoiceId);
      if (targetInv) {
        onSelectInvoice(targetInv);
      }
    }
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end animate-in fade-in duration-200">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="relative w-full max-w-md bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col h-full z-10 text-white">
        {/* Cabecera */}
        <div className="p-4 px-5 border-b border-slate-800 bg-slate-950/70 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/25">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white tracking-tight">
                  Centro de Notificaciones
                </h3>
                {unreadCount > 0 && (
                  <span className="text-[10px] font-bold px-2 py-0.2 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30">
                    {unreadCount} no leídas
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                Alertas fiscales, bancarias y diagnósticos de Konta IA.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-all"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filtros y Acción Rápida */}
        <div className="px-5 py-3 border-b border-slate-800/80 bg-slate-950/40 flex items-center justify-between gap-2 overflow-x-auto">
          <div className="flex items-center gap-1.5">
            {[
              { id: 'all', label: 'Todas' },
              { id: 'attention', label: 'Atención ⚠️' },
              { id: 'banking', label: 'Bancos 🏦' },
              { id: 'tax', label: 'Fiscal ⚖️' },
              { id: 'document', label: 'Docs 📄' },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setSelectedFilter(f.id as any)}
                className={`text-[11px] font-semibold px-2.5 py-1 rounded-lg transition-all shrink-0 ${
                  selectedFilter === f.id
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {unreadCount > 0 && (
            <button
              onClick={markAllAsRead}
              className="text-[11px] font-medium text-indigo-400 hover:text-indigo-300 flex items-center gap-1 shrink-0"
              title="Marcar todas como leídas"
            >
              <CheckCheck className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Marcar leídas</span>
            </button>
          )}
        </div>

        {/* Listado de Notificaciones */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
          {filteredNotifications.length === 0 ? (
            <div className="py-16 text-center text-slate-500 space-y-2">
              <CheckCircle2 className="w-10 h-10 mx-auto text-slate-600" />
              <p className="text-sm font-medium text-slate-400">
                No tienes notificaciones en este filtro
              </p>
              <p className="text-xs text-slate-500">
                Todo tu ecosistema contable y fiscal se encuentra al día.
              </p>
            </div>
          ) : (
            filteredNotifications.map((notif) => (
              <div
                key={notif.id}
                className={`p-3.5 rounded-2xl border transition-all flex flex-col gap-2 relative ${
                  notif.isRead
                    ? 'bg-slate-850/40 border-slate-800/70 text-slate-400 opacity-80'
                    : 'bg-slate-850 border-slate-750 text-white shadow-sm'
                } ${
                  notif.priority === 'high' && !notif.isRead
                    ? 'border-l-4 border-l-rose-500'
                    : ''
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5">
                    <div
                      className={`p-2 rounded-xl shrink-0 mt-0.5 ${
                        notif.type === 'attention'
                          ? 'bg-rose-500/15 text-rose-400 border border-rose-500/25'
                          : notif.type === 'banking'
                          ? 'bg-blue-500/15 text-blue-400 border border-blue-500/25'
                          : notif.type === 'tax'
                          ? 'bg-amber-500/15 text-amber-400 border border-amber-500/25'
                          : notif.type === 'document'
                          ? 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/25'
                          : 'bg-slate-700 text-slate-300'
                      }`}
                    >
                      {notif.type === 'attention' && <AlertTriangle className="w-4 h-4" />}
                      {notif.type === 'banking' && <Landmark className="w-4 h-4" />}
                      {notif.type === 'tax' && <Scale className="w-4 h-4" />}
                      {notif.type === 'document' && <FileText className="w-4 h-4" />}
                      {notif.type === 'system' && <Sparkles className="w-4 h-4" />}
                    </div>

                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <h4
                          className={`text-xs font-bold ${
                            notif.isRead ? 'text-slate-300' : 'text-white'
                          }`}
                        >
                          {notif.title}
                        </h4>
                        {!notif.isRead && (
                          <span className="w-2 h-2 rounded-full bg-cyan-400 shrink-0" />
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        {notif.description}
                      </p>
                    </div>
                  </div>

                  <span className="text-[10px] text-slate-500 shrink-0 font-medium whitespace-nowrap">
                    {notif.timeAgo}
                  </span>
                </div>

                {/* Botón de Acción Directa */}
                {notif.actionLabel && (
                  <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                    <button
                      onClick={() => handleActionClick(notif)}
                      className="text-xs font-semibold text-cyan-300 hover:text-white flex items-center gap-1 group transition-colors"
                    >
                      <span>{notif.actionLabel}</span>
                      <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                    </button>

                    {!notif.isRead && (
                      <button
                        onClick={() => markAsRead(notif.id)}
                        className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
                      >
                        Marcar como leída
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Pie del Drawer */}
        <div className="p-3.5 border-t border-slate-800 bg-slate-950/70 text-center text-xs text-slate-500">
          Supervisión continua con auditoría PGC y Compliance AEAT.
        </div>
      </div>
    </div>
  );
};

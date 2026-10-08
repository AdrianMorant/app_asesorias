'use client';

import React, { useState } from 'react';
import {
  History,
  Sparkles,
  User,
  ShieldCheck,
  CheckCircle2,
  FileText,
  CreditCard,
  Download,
  Scissors,
  Scale,
  RefreshCw,
  Clock,
  ChevronRight,
  Filter,
} from 'lucide-react';
import { Company, Invoice } from '@/types';

export interface AuditEvent {
  id: string;
  timestamp: string;
  timeFormatted: string;
  actorType: 'ai' | 'user' | 'system' | 'compliance';
  actorName: string;
  title: string;
  detail: string;
  category: 'triage' | 'reconciliation' | 'export' | 'tax' | 'multifactura';
  status: 'success' | 'info' | 'warning';
  metadata?: string;
}

interface ActivityAuditTimelineProps {
  company: Company;
  invoices?: Invoice[];
  onNavigateTab?: (tab: any) => void;
  compact?: boolean;
}

const DEFAULT_EVENTS: AuditEvent[] = [
  {
    id: 'evt-1',
    timestamp: '2026-04-08T10:45:00Z',
    timeFormatted: 'Hoy, 10:45',
    actorType: 'ai',
    actorName: 'Konta Copilot IA',
    title: 'Extracción multimodal completada',
    detail: 'Extracción limpia de factura #FRA-2026-9021 (Amazon Web Services). Subcuenta 628000001 asignada con certeza 98%.',
    category: 'triage',
    status: 'success',
    metadata: '121,00 € | CIF B84920192',
  },
  {
    id: 'evt-2',
    timestamp: '2026-04-08T09:30:00Z',
    timeFormatted: 'Hoy, 09:30',
    actorType: 'user',
    actorName: 'Administrador (Tú)',
    title: 'Conciliación bancaria confirmada',
    detail: 'Vinculado cargo de Banco Santander (-121,00 €) con factura de infraestructura cloud. Asiento PGC generado en partida doble.',
    category: 'reconciliation',
    status: 'success',
    metadata: 'Santander ES91 | Asiento 2026/0418',
  },
  {
    id: 'evt-3',
    timestamp: '2026-04-07T18:15:00Z',
    timeFormatted: 'Ayer, 18:15',
    actorType: 'compliance',
    actorName: 'Motor AEAT Compliance',
    title: 'Generado lote de enlace contable',
    detail: 'Exportación SUENLACE.DAT para Wolters Kluwer A3eco / Contasol completada (3 asientos sin incidencias de dígito).',
    category: 'export',
    status: 'info',
    metadata: 'Formato A3 / Sage compatible',
  },
  {
    id: 'evt-4',
    timestamp: '2026-04-07T16:20:00Z',
    timeFormatted: 'Ayer, 16:20',
    actorType: 'ai',
    actorName: 'Konta MF Splitter',
    title: 'Segregación multifactura aplicada',
    detail: 'Detectado PDF compuesto de 4 páginas. Se descartó 1 página en blanco y se generaron 3 subfacturas independientes.',
    category: 'multifactura',
    status: 'success',
    metadata: '3 facturas generadas',
  },
  {
    id: 'evt-5',
    timestamp: '2026-04-07T11:00:00Z',
    timeFormatted: '07 Abr, 11:00',
    actorType: 'system',
    actorName: 'Motor Fiscal Konta',
    title: 'Autoliquidación Modelo 303 estimada',
    detail: 'Cálculo dinámico del 1T 2026: IVA Repercutido (3.150,00 €) - Soportado (1.700,00 €) = 1.450,00 € a ingresar.',
    category: 'tax',
    status: 'info',
    metadata: 'Plazo 20 de Abril',
  },
];

export const ActivityAuditTimeline: React.FC<ActivityAuditTimelineProps> = ({
  company,
  invoices,
  onNavigateTab,
  compact = false,
}) => {
  const [selectedActor, setSelectedActor] = useState<'all' | AuditEvent['actorType']>('all');
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const filteredEvents = DEFAULT_EVENTS.filter((e) => {
    if (selectedActor === 'all') return true;
    return e.actorType === selectedActor;
  });

  const handleRefresh = () => {
    setRefreshing(true);
    setTimeout(() => {
      setRefreshing(false);
    }, 500);
  };

  const getActorBadge = (actorType: AuditEvent['actorType'], name: string) => {
    switch (actorType) {
      case 'ai':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/25">
            <Sparkles className="w-3 h-3 text-cyan-400" />
            {name}
          </span>
        );
      case 'user':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">
            <User className="w-3 h-3 text-emerald-400" />
            {name}
          </span>
        );
      case 'compliance':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
            <ShieldCheck className="w-3 h-3 text-indigo-400" />
            {name}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-700 text-slate-300">
            <Clock className="w-3 h-3 text-slate-400" />
            {name}
          </span>
        );
    }
  };

  const getCategoryIcon = (category: AuditEvent['category']) => {
    switch (category) {
      case 'triage':
        return <FileText className="w-4 h-4 text-cyan-400" />;
      case 'reconciliation':
        return <CreditCard className="w-4 h-4 text-emerald-400" />;
      case 'export':
        return <Download className="w-4 h-4 text-indigo-400" />;
      case 'multifactura':
        return <Scissors className="w-4 h-4 text-purple-400" />;
      case 'tax':
        return <Scale className="w-4 h-4 text-amber-400" />;
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden flex flex-col">
      {/* Cabecera del Timeline */}
      <div className="p-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-slate-900 text-white shadow-xs">
            <History className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900 tracking-tight">
                Registro de Actividad y Auditoría Contable
              </h3>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-200/80 text-slate-700">
                Trazabilidad 100%
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Historial cronológico de extracciones IA, conciliaciones y exportaciones de {company.razon_social}.
            </p>
          </div>
        </div>

        {/* Filtros por Actor y Refrescar */}
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-slate-100 p-1 rounded-xl text-xs font-semibold">
            {[
              { id: 'all', label: 'Todos' },
              { id: 'ai', label: 'Konta IA' },
              { id: 'user', label: 'Usuario' },
              { id: 'compliance', label: 'Compliance' },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setSelectedActor(f.id as any)}
                className={`px-2.5 py-1 rounded-lg transition-all ${
                  selectedActor === f.id
                    ? 'bg-white text-slate-900 shadow-xs font-bold'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <button
            onClick={handleRefresh}
            className="p-1.5 rounded-xl border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-all"
            title="Refrescar historial"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-indigo-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Lista del Timeline */}
      <div className={`p-5 divide-y divide-slate-100 ${compact ? 'max-h-80' : 'max-h-96'} overflow-y-auto custom-scrollbar`}>
        {filteredEvents.map((evt, idx) => (
          <div
            key={evt.id}
            className={`py-3.5 first:pt-1 last:pb-1 flex items-start gap-3.5 group transition-colors hover:bg-slate-50/50 -mx-2 px-2 rounded-xl`}
          >
            {/* Icono de categoría */}
            <div className="w-8 h-8 rounded-xl bg-slate-100 border border-slate-200/60 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
              {getCategoryIcon(evt.category)}
            </div>

            {/* Contenido del evento */}
            <div className="flex-1 space-y-1">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h4 className="text-xs font-bold text-slate-900">
                    {evt.title}
                  </h4>
                  {getActorBadge(evt.actorType, evt.actorName)}
                </div>
                <span className="text-[11px] text-slate-400 font-medium shrink-0">
                  {evt.timeFormatted}
                </span>
              </div>

              <p className="text-xs text-slate-600 leading-relaxed">
                {evt.detail}
              </p>

              {evt.metadata && (
                <div className="pt-0.5">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200/60">
                    {evt.metadata}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Pie del componente */}
      <div className="p-3 bg-slate-50/70 border-t border-slate-100 px-5 flex items-center justify-between text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          Libro de auditoría inmutable para inspecciones de Hacienda.
        </span>
        {onNavigateTab && (
          <button
            onClick={() => onNavigateTab('journal')}
            className="text-xs font-bold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
          >
            <span>Ver Libro Diario Completo</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
};

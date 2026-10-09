'use client';

import React from 'react';
import { TrafficLightStatus } from '@/types';
import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';

interface Props {
  status: TrafficLightStatus;
  reasonsCount?: number;
  showIcon?: boolean;
  size?: 'sm' | 'md' | 'lg';
  esMultifactura?: boolean;
  workflowStatus?: string;
}

export const TrafficLightBadge: React.FC<Props> = ({
  status,
  reasonsCount = 0,
  showIcon = true,
  size = 'md',
  esMultifactura = false,
  workflowStatus,
}) => {
  const configs = {
    GREEN: {
      bg: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400',
      dot: 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]',
      label: 'VERDE',
      icon: CheckCircle2,
      desc: 'Cuadrada y lista',
    },
    YELLOW: {
      bg: 'bg-amber-500/15 border-amber-500/30 text-amber-300',
      dot: 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]',
      label: 'AMARILLO',
      icon: AlertTriangle,
      desc: 'Revisión requerida',
    },
    RED: {
      bg: 'bg-rose-500/15 border-rose-500/30 text-rose-400',
      dot: 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]',
      label: 'ROJO',
      icon: XCircle,
      desc: 'Bloqueante',
    },
  };

  const cfg = configs[status] || configs.RED;
  const Icon = cfg.icon;

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1.5',
    md: 'text-xs px-2.5 py-1 gap-1.5 font-medium',
    lg: 'text-sm px-3.5 py-1.5 gap-2 font-semibold',
  };

  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`inline-flex items-center rounded-full border transition-all duration-200 ${cfg.bg} ${sizeClasses[size]}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot} animate-pulse`} />
        {showIcon && <Icon className="w-3.5 h-3.5" />}
        <span>{cfg.label}</span>
        {reasonsCount > 0 && status !== 'GREEN' && (
          <span className="ml-0.5 px-1.5 py-0.2 text-[10px] bg-black/30 rounded-full">
            {reasonsCount}
          </span>
        )}
      </span>

      {/* Badge visual 'MF' (Multi-Factura) */}
      {esMultifactura && (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm"
          title="Documento Multi-Factura (MF): contiene múltiples páginas a disgregar"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping" />
          MF
        </span>
      )}
    </span>
  );
};

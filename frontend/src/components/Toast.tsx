'use client';

import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  title?: string;
  message: string;
}

interface Props {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<Props> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-md w-full pointer-events-none">
      {toasts.map((t) => {
        const bgColors = {
          success: 'bg-slate-900/95 border-emerald-500/40 text-emerald-300 shadow-emerald-950/50',
          error: 'bg-slate-900/95 border-rose-500/40 text-rose-300 shadow-rose-950/50',
          info: 'bg-slate-900/95 border-cyan-500/40 text-cyan-300 shadow-cyan-950/50',
        };

        const Icon =
          t.type === 'success'
            ? CheckCircle2
            : t.type === 'error'
            ? AlertCircle
            : Info;

        return (
          <div
            key={t.id}
            className={`pointer-events-auto border rounded-xl p-3.5 shadow-2xl backdrop-blur-md flex items-start gap-3 transition-all duration-300 animate-in slide-in-from-bottom-5 ${bgColors[t.type]}`}
          >
            <Icon className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="flex-1 text-xs">
              {t.title && <div className="font-semibold text-white mb-0.5">{t.title}</div>}
              <div className="text-slate-300 leading-relaxed">{t.message}</div>
            </div>
            <button
              type="button"
              onClick={() => onDismiss(t.id)}
              className="text-slate-400 hover:text-white p-0.5 rounded transition"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
};

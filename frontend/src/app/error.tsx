'use client';

import React, { useEffect } from 'react';
import { AlertOctagon, RefreshCw, Home, LifeBuoy } from 'lucide-react';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorBoundaryPage({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Registrar error para monitoreo técnico
    console.error('Frontend Application Error Captured:', error);
  }, [error]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 selection:bg-rose-500/30 selection:text-rose-200">
      <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl shadow-rose-950/20 text-center">
        {/* Icono de advertencia */}
        <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
          <AlertOctagon className="w-8 h-8" />
        </div>

        {/* Título y descripción */}
        <h1 className="text-xl font-bold text-white mb-2">
          Se ha producido un error de visualización
        </h1>
        <p className="text-sm text-slate-400 mb-6 leading-relaxed">
          La interfaz ha capturado una excepción de renderizado imprevista. La sesión no se ha cerrado y tus datos están a salvo.
        </p>

        {/* Detalle del error (técnico para diagnóstico rápido) */}
        {error?.message && (
          <div className="mb-6 p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-left">
            <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block mb-1">
              Detalle del error
            </span>
            <code className="text-xs text-rose-300 font-mono break-all line-clamp-3 block">
              {error.message}
            </code>
            {error.digest && (
              <span className="text-[10px] text-slate-400 font-mono mt-1 block">
                Digest: {error.digest}
              </span>
            )}
          </div>
        )}

        {/* Acciones de recuperación */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={() => reset()}
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 transition-all active:scale-95"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Reintentar</span>
          </button>

          <button
            onClick={() => {
              if (typeof window !== 'undefined') {
                window.location.reload();
              }
            }}
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all active:scale-95"
          >
            <Home className="w-4 h-4" />
            <span>Recargar Página</span>
          </button>
        </div>

        <div className="mt-6 pt-5 border-t border-slate-800/80 flex items-center justify-center gap-2 text-xs text-slate-400">
          <LifeBuoy className="w-3.5 h-3.5" />
          <span>KontaAI Suite • Recuperación de Fallos Activa</span>
        </div>
      </div>
    </div>
  );
}

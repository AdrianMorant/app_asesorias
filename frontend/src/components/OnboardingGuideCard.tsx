'use client';

import React, { useState, useEffect } from 'react';
import {
  Building2,
  Landmark,
  UploadCloud,
  CheckCircle2,
  Circle,
  X,
  ArrowRight,
  Sparkles,
  ChevronRight,
  ShieldCheck,
  Check,
} from 'lucide-react';
import { Company, Invoice } from '@/types';

interface OnboardingGuideCardProps {
  company: Company;
  invoicesCount: number;
  onNavigateTab: (tab: any) => void;
  onOpenUpload?: () => void;
  onOpenDemo?: () => void;
}

const STORAGE_KEY = 'konta_onboarding_dismissed';

export const OnboardingGuideCard: React.FC<OnboardingGuideCardProps> = ({
  company,
  invoicesCount,
  onNavigateTab,
  onOpenUpload,
  onOpenDemo,
}) => {
  const [isDismissed, setIsDismissed] = useState<boolean>(true);
  const [bankConnected, setBankConnected] = useState<boolean>(false);

  // Inicializar estado desde localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'true') {
        setIsDismissed(true);
      } else {
        setIsDismissed(false);
      }

      const bankStored = localStorage.getItem('konta_bank_connected');
      if (bankStored === 'true') {
        setBankConnected(true);
      }
    } catch {
      setIsDismissed(false);
    }
  }, []);

  // Paso 1: Empresa configurada (se considera cumplido si hay CIF y razón social)
  const isStep1Done = Boolean(company && company.cif && company.razon_social);

  // Paso 2: Banco conectado (o simulado / marcado por el usuario)
  const isStep2Done = bankConnected;

  // Paso 3: Al menos 1 factura subida
  const isStep3Done = invoicesCount > 0;

  const stepsDoneCount = (isStep1Done ? 1 : 0) + (isStep2Done ? 1 : 0) + (isStep3Done ? 1 : 0);
  const progressPercent = Math.round((stepsDoneCount / 3) * 100);

  const handleDismiss = () => {
    setIsDismissed(true);
    try {
      localStorage.setItem(STORAGE_KEY, 'true');
    } catch {
      // Ignore
    }
  };

  const handleRestore = () => {
    setIsDismissed(false);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignore
    }
  };

  if (isDismissed) {
    return (
      <div className="flex justify-end -mb-3">
        <button
          onClick={handleRestore}
          className="text-[11px] font-medium text-slate-400 hover:text-cyan-400 flex items-center gap-1.5 transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span>Ver guía de primeros pasos ({stepsDoneCount}/3 completados)</span>
        </button>
      </div>
    );
  }

  return (
    <div className="relative bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-750 rounded-2xl p-5 shadow-lg text-white animate-in fade-in duration-200">
      {/* Botón descartar */}
      <button
        onClick={handleDismiss}
        className="absolute top-4 right-4 p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-all"
        title="Ocultar guía de inicio"
      >
        <X className="w-4 h-4" />
      </button>

      {/* Cabecera del Onboarding */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pr-8 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 uppercase tracking-wider">
              Primeros Pasos
            </span>
            <span className="text-xs font-semibold text-slate-300">
              {stepsDoneCount} de 3 pasos completados ({progressPercent}%)
            </span>
          </div>
          <h2 className="text-base font-bold text-white mt-1">
            Pon en marcha tu contabilidad autónoma con Konta IA
          </h2>
        </div>

        {onOpenDemo && (
          <button
            onClick={onOpenDemo}
            className="self-start sm:self-auto text-xs font-bold px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 hover:border-cyan-500/40 transition-all flex items-center gap-1.5"
          >
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span>Ver Demo Guiada (1 min)</span>
          </button>
        )}
      </div>

      {/* Barra de progreso */}
      <div className="w-full bg-slate-800 h-1.5 rounded-full mt-3 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Los 3 Pasos */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 mt-4">
        {/* Paso 1: Configurar empresa */}
        <div
          className={`p-3.5 rounded-xl border transition-all ${
            isStep1Done
              ? 'bg-slate-800/40 border-slate-750/70'
              : 'bg-slate-800/80 border-cyan-500/30 ring-1 ring-cyan-500/20'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <div
                className={`p-2 rounded-lg ${
                  isStep1Done ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-700 text-cyan-400'
                }`}
              >
                <Building2 className="w-4 h-4" />
              </div>
              <span className="text-xs font-bold text-white">1. Empresa Lista</span>
            </div>
            {isStep1Done ? (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 flex items-center gap-1">
                <Check className="w-3 h-3" /> Hecho
              </span>
            ) : (
              <span className="text-[10px] font-medium text-amber-400">Pendiente</span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
            {company?.razon_social ? (
              <>
                Empresa configurada: <strong className="text-slate-200">{company.razon_social}</strong> (CIF: {company.cif}).
              </>
            ) : (
              'Define la razón social y NIF para la generación reglamentaria de libros PGC.'
            )}
          </p>
        </div>

        {/* Paso 2: Conectar banco o extracto */}
        <div
          className={`p-3.5 rounded-xl border transition-all ${
            isStep2Done
              ? 'bg-slate-800/40 border-slate-750/70'
              : 'bg-slate-800/80 border-cyan-500/30'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <div
                className={`p-2 rounded-lg ${
                  isStep2Done ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-700 text-cyan-400'
                }`}
              >
                <Landmark className="w-4 h-4" />
              </div>
              <span className="text-xs font-bold text-white">2. Conecta tu Banco</span>
            </div>
            {isStep2Done ? (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 flex items-center gap-1">
                <Check className="w-3 h-3" /> Conectado
              </span>
            ) : (
              <button
                onClick={() => {
                  setBankConnected(true);
                  try {
                    localStorage.setItem('konta_bank_connected', 'true');
                  } catch {}
                }}
                className="text-[10px] font-bold text-cyan-400 hover:text-cyan-300 underline"
              >
                Marcar listo
              </button>
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
            Sube un extracto Norma 43, Excel bancario o conecta con PSD2 para conciliar en 1 clic.
          </p>
          <button
            onClick={() => onNavigateTab('bank')}
            className="mt-3 text-xs font-semibold text-cyan-300 hover:text-white flex items-center gap-1 group"
          >
            <span>Ir a Conciliación Bancaria</span>
            <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
          </button>
        </div>

        {/* Paso 3: Subir primera factura */}
        <div
          className={`p-3.5 rounded-xl border transition-all ${
            isStep3Done
              ? 'bg-slate-800/40 border-slate-750/70'
              : 'bg-slate-800/80 border-cyan-500/30 ring-1 ring-cyan-500/20'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <div
                className={`p-2 rounded-lg ${
                  isStep3Done ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-700 text-cyan-400'
                }`}
              >
                <UploadCloud className="w-4 h-4" />
              </div>
              <span className="text-xs font-bold text-white">3. Sube Facturas</span>
            </div>
            {isStep3Done ? (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 flex items-center gap-1">
                <Check className="w-3 h-3" /> {invoicesCount} subidas
              </span>
            ) : (
              <span className="text-[10px] font-medium text-cyan-400">Recomendado</span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
            Arrastra cualquier factura en PDF, PNG o JPG. La IA extraerá los datos en segundos.
          </p>
          <button
            onClick={() => {
              if (onOpenUpload) {
                onOpenUpload();
              } else {
                onNavigateTab('expenses');
              }
            }}
            className="mt-3 text-xs font-semibold text-cyan-300 hover:text-white flex items-center gap-1 group"
          >
            <span>Subir Factura Ahora</span>
            <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
          </button>
        </div>
      </div>
    </div>
  );
};

'use client';

import React, { useState } from 'react';
import { Company } from '@/types';
import {
  LayoutDashboard,
  ArrowUpRight,
  Receipt,
  Users,
  BookOpen,
  Table2,
  Landmark,
  Network,
  Building2,
  Building,
  Briefcase,
  ChevronDown,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from 'lucide-react';

export type ActiveNavTab =
  | 'dashboard'
  | 'sales'
  | 'expenses'
  | 'contacts'
  | 'banking'
  | 'journal'
  | 'chart-of-accounts'
  | 'taxes'
  | 'integrations'
  | 'companies';

export type WorkspaceMode = 'advisor' | 'client';

interface SidebarProps {
  currentTab: ActiveNavTab;
  onSelectTab: (tab: ActiveNavTab) => void;
  companies: Company[];
  selectedCompanyId: string;
  onSelectCompany: (companyId: string) => void;
  onOpenCompanyManager: () => void;
  pendingInvoicesCount?: number;
  yellowInvoicesCount?: number;
  redInvoicesCount?: number;
  mode?: WorkspaceMode;
  onModeChange?: (mode: WorkspaceMode) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  companies,
  selectedCompanyId,
  onSelectCompany,
  onOpenCompanyManager,
  pendingInvoicesCount = 0,
  yellowInvoicesCount = 0,
  redInvoicesCount = 0,
  mode: propMode,
  onModeChange,
}) => {
  const [internalMode, setInternalMode] = useState<WorkspaceMode>('advisor');
  const activeMode = propMode !== undefined ? propMode : internalMode;

  const handleModeSwitch = (newMode: WorkspaceMode) => {
    if (onModeChange) {
      onModeChange(newMode);
    } else {
      setInternalMode(newMode);
    }

    // Si pasamos a modo cliente y la pestaña actual es exclusiva de despacho, volver a dashboard
    if (
      newMode === 'client' &&
      (currentTab === 'integrations' ||
        currentTab === 'companies' ||
        currentTab === 'journal' ||
        currentTab === 'chart-of-accounts' ||
        currentTab === 'taxes')
    ) {
      onSelectTab('dashboard');
    }
  };

  const currentCompany = companies.find((c) => c.id === selectedCompanyId);

  // Catálogo completo de grupos de navegación
  const allNavGroups = [
    {
      group: 'PANEL PRINCIPAL',
      advisorOnly: false,
      items: [
        {
          id: 'dashboard' as ActiveNavTab,
          label: 'Dashboard Financiero',
          icon: LayoutDashboard,
          badge: null,
          advisorOnly: false,
        },
      ],
    },
    {
      group: 'GESTIÓN OPERATIVA',
      advisorOnly: false,
      items: [
        {
          id: 'sales' as ActiveNavTab,
          label: 'Ventas y Facturación',
          icon: ArrowUpRight,
          badge: null,
          advisorOnly: false,
        },
        {
          id: 'expenses' as ActiveNavTab,
          label: 'Gastos e Ingesta IA',
          icon: Receipt,
          advisorOnly: false,
          badge:
            redInvoicesCount > 0 ? (
              <span className="flex items-center gap-1 text-[11px] font-bold px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-700">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                {redInvoicesCount}
              </span>
            ) : yellowInvoicesCount > 0 ? (
              <span className="flex items-center gap-1 text-[11px] font-bold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800">
                {yellowInvoicesCount}
              </span>
            ) : null,
        },
        {
          id: 'contacts' as ActiveNavTab,
          label: 'Contactos (CRM)',
          icon: Users,
          badge: null,
          advisorOnly: false,
        },
        {
          id: 'banking' as ActiveNavTab,
          label: 'Conciliación Bancaria',
          icon: Landmark,
          advisorOnly: false,
          badge: (
            <span
              className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                activeMode === 'advisor'
                  ? 'bg-blue-950 text-blue-300 border border-blue-800/60'
                  : 'bg-slate-800 text-slate-300 border border-slate-700'
              }`}
            >
              572
            </span>
          ),
        },
      ],
    },
    {
      group: 'CONTABILIDAD Y FISCAL',
      advisorOnly: true,
      items: [
        {
          id: 'journal' as ActiveNavTab,
          label: 'Libro Diario y Mayor',
          icon: BookOpen,
          badge: null,
          advisorOnly: true,
        },
        {
          id: 'chart-of-accounts' as ActiveNavTab,
          label: 'Plan Contable PYME',
          icon: Table2,
          badge: null,
          advisorOnly: true,
        },
        {
          id: 'taxes' as ActiveNavTab,
          label: 'Impuestos (303/111/115/347)',
          icon: ShieldCheck,
          badge: null,
          advisorOnly: true,
        },
      ],
    },
    {
      group: 'ENLACE Y DESPACHO',
      advisorOnly: true,
      items: [
        {
          id: 'integrations' as ActiveNavTab,
          label: 'Integraciones ERP',
          icon: Network,
          advisorOnly: true,
          badge: (
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
              A3/DELSOL
            </span>
          ),
        },
        {
          id: 'companies' as ActiveNavTab,
          label: 'Configuración Empresas',
          icon: Building2,
          badge: null,
          advisorOnly: true,
        },
      ],
    },
  ];

  // Filtrado de módulos según el modo activo
  const visibleNavGroups =
    activeMode === 'advisor'
      ? allNavGroups
      : allNavGroups
          .filter((g) => !g.advisorOnly)
          .map((g) => ({
            ...g,
            items: g.items.filter((item) => !item.advisorOnly),
          }));

  // Estilos visuales condicionales según el modo Dual
  const isAdvisor = activeMode === 'advisor';
  const sidebarBgClass = isAdvisor
    ? 'bg-slate-900 border-r border-blue-900/40 text-slate-300'
    : 'bg-slate-950 border-r border-slate-800 text-slate-300';

  const brandAccentClass = isAdvisor
    ? 'bg-gradient-to-tr from-blue-700 to-indigo-500 shadow-blue-900/40'
    : 'bg-gradient-to-tr from-slate-700 to-slate-500 shadow-slate-900/40';

  const activeItemClass = isAdvisor
    ? 'bg-blue-600 text-white shadow-sm shadow-blue-900/30 font-semibold'
    : 'bg-slate-800 text-white border border-slate-700 font-semibold';

  return (
    <aside
      className={`w-64 flex flex-col flex-shrink-0 h-screen select-none transition-colors duration-200 ${sidebarBgClass}`}
    >
      {/* 1. Brand Header */}
      <div
        className={`p-4 border-b flex items-center justify-between ${
          isAdvisor ? 'border-blue-900/30' : 'border-slate-800/80'
        }`}
      >
        <div className="flex items-center gap-2.5">
          <div
            className={`w-9 h-9 rounded-xl flex items-center justify-center text-white shadow-md font-bold text-lg tracking-tight ${brandAccentClass}`}
          >
            K
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-white text-base tracking-tight">KontaAI</span>
              <span
                className={`text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded border ${
                  isAdvisor
                    ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                    : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                }`}
              >
                {isAdvisor ? 'Advisor' : 'Client'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              {isAdvisor ? 'Backoffice Asesoría' : 'Portal PYME & Cliente'}
            </p>
          </div>
        </div>
      </div>

      {/* 2. Selector Dual de Espacio de Trabajo */}
      <div className={`p-2.5 border-b ${isAdvisor ? 'border-blue-900/30 bg-slate-950/40' : 'border-slate-800 bg-slate-900/30'}`}>
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1 px-1">
          Espacio de Trabajo
        </div>
        <div className="grid grid-cols-2 p-1 bg-slate-950/80 rounded-xl border border-slate-800/90 gap-1">
          <button
            onClick={() => handleModeSwitch('advisor')}
            className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-[11px] font-bold transition-all ${
              isAdvisor
                ? 'bg-blue-600 text-white shadow-sm shadow-blue-900/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Briefcase className="w-3.5 h-3.5" />
            <span>Despacho</span>
          </button>
          <button
            onClick={() => handleModeSwitch('client')}
            className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-[11px] font-bold transition-all ${
              !isAdvisor
                ? 'bg-slate-800 text-white border border-slate-700 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Building className="w-3.5 h-3.5" />
            <span>Cliente</span>
          </button>
        </div>
      </div>

      {/* 3. Selector de Empresa Activa */}
      <div
        className={`p-3 border-b ${
          isAdvisor ? 'border-blue-900/30 bg-slate-950/20' : 'border-slate-800 bg-slate-950/40'
        }`}
      >
        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
          <span>{isAdvisor ? 'Cliente Asignado' : 'Mi Empresa'}</span>
          {isAdvisor && (
            <button
              onClick={onOpenCompanyManager}
              className="text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
            >
              Gestionar
            </button>
          )}
        </div>

        <div className="relative">
          <select
            value={selectedCompanyId}
            onChange={(e) => onSelectCompany(e.target.value)}
            className={`w-full text-white text-xs rounded-lg px-2.5 py-2 pr-7 border focus:outline-none appearance-none font-medium truncate cursor-pointer transition-colors ${
              isAdvisor
                ? 'bg-slate-800/90 border-blue-900/50 hover:border-blue-700 focus:ring-1 focus:ring-blue-500'
                : 'bg-slate-900 border-slate-700 hover:border-slate-600 focus:ring-1 focus:ring-slate-500'
            }`}
          >
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.razon_social} ({c.cif})
              </option>
            ))}
          </select>
          <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        </div>

        {currentCompany && (
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400 px-0.5">
            <span className="font-mono text-slate-400">{currentCompany.cif}</span>
            <span className="inline-flex items-center gap-1 text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              {currentCompany.plan_cuentas_longitud} dígitos • {currentCompany.iva_periodicity || 'Trimestral'}
            </span>
          </div>
        )}
      </div>

      {/* 4. Menú de Navegación por Módulos */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4 custom-scrollbar">
        {visibleNavGroups.map((group, idx) => (
          <div key={idx} className="space-y-1">
            <div
              className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 ${
                isAdvisor ? 'text-blue-400/80' : 'text-slate-400'
              }`}
            >
              {group.group}
            </div>
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onSelectTab(item.id)}
                  className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? activeItemClass
                      : isAdvisor
                      ? 'text-slate-300 hover:text-white hover:bg-slate-800/80'
                      : 'text-slate-400 hover:text-white hover:bg-slate-900'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Icon
                      className={`w-4 h-4 flex-shrink-0 ${
                        isActive
                          ? 'text-white'
                          : isAdvisor
                          ? 'text-blue-400/70'
                          : 'text-slate-500'
                      }`}
                    />
                    <span className="truncate">{item.label}</span>
                  </div>
                  {item.badge}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* 5. Pie del Sidebar: Entorno y Estado */}
      <div
        className={`p-3 border-t text-xs ${
          isAdvisor
            ? 'border-blue-900/30 bg-slate-950/60'
            : 'border-slate-800 bg-slate-950/80'
        }`}
      >
        <div className="flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span className="font-medium text-slate-300">OpenAI GPT-4o-mini</span>
          </div>
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
              isAdvisor
                ? 'bg-blue-950 text-blue-300 border border-blue-800'
                : 'bg-slate-900 text-slate-300 border border-slate-700'
            }`}
          >
            {isAdvisor ? 'ERP Link ON' : 'Portal Activo'}
          </span>
        </div>
        <p className="text-[10px] text-slate-400 mt-1 truncate">
          {isAdvisor ? 'PGC 2008 PYME • Wolters Kluwer / DELSOL / Sage' : 'Gestión Facturación & Pagos'}
        </p>
      </div>
    </aside>
  );
};

'use client';

import React, { useState, useEffect } from 'react';
import {
  Building2,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  RefreshCw,
  Search,
  ExternalLink,
  ShieldCheck,
  Mail,
  Scale,
  Landmark,
  ArrowRight,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export interface ClientHealthItem {
  company_id: string;
  cif: string;
  razon_social: string;
  tax_period: string;
  tax_traffic_light: 'GREEN' | 'YELLOW' | 'RED';
  tax_alert_message: string;
  pending_inbound_invoices: number;
  unpaid_sales_invoices: number;
  bank_reconciliation_rate: number;
  unreconciled_bank_transactions: number;
  last_psd2_sync: string | null;
  is_psd2_connected: boolean;
}

interface AdvisorPortalViewProps {
  currentCompanyId: string;
  onSelectCompany: (companyId: string) => void;
  onNotify: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
}

export const AdvisorPortalView: React.FC<AdvisorPortalViewProps> = ({
  currentCompanyId,
  onSelectCompany,
  onNotify,
}) => {
  const [clients, setClients] = useState<ClientHealthItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [filterLight, setFilterLight] = useState<'ALL' | 'RED' | 'YELLOW' | 'GREEN'>('ALL');

  const loadHealthStatus = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/advisor/clients-health-status`);
      if (!res.ok) throw new Error('Error consultando estado multi-tenant de asesoría');
      const data = await res.json();
      setClients(data);
    } catch (err: any) {
      onNotify('error', err.message || 'Error al cargar el panel de asesor');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealthStatus();
  }, []);

  const filteredClients = clients.filter((c) => {
    if (filterLight !== 'ALL' && c.tax_traffic_light !== filterLight) return false;
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      return (
        c.razon_social.toLowerCase().includes(term) ||
        c.cif.toLowerCase().includes(term)
      );
    }
    return true;
  });

  const redCount = clients.filter((c) => c.tax_traffic_light === 'RED').length;
  const yellowCount = clients.filter((c) => c.tax_traffic_light === 'YELLOW').length;
  const greenCount = clients.filter((c) => c.tax_traffic_light === 'GREEN').length;

  return (
    <div className="space-y-6">
      {/* Cabecera */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <Building2 className="w-5 h-5" />
            </span>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Portal del Asesor • Supervisión Multi-Tenant
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Panel maestro de control fiscal, conciliación bancaria y buzón documental de todas las empresas clientes gestionadas.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadHealthStatus}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs text-slate-700 hover:text-slate-900 px-3 py-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-600' : ''}`} />
            Actualizar Estados
          </button>
        </div>
      </div>

      {/* Tarjetas KPI de Semáforo de Despacho */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div
          onClick={() => setFilterLight('ALL')}
          className={`p-4 rounded-xl border shadow-sm cursor-pointer transition-all ${
            filterLight === 'ALL' ? 'border-indigo-500 bg-indigo-50/30' : 'bg-white border-slate-200 hover:border-slate-300'
          }`}
        >
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">Total Clientes Asignados</div>
          <div className="text-2xl font-bold text-slate-900 font-mono mt-1">{clients.length}</div>
        </div>

        <div
          onClick={() => setFilterLight('RED')}
          className={`p-4 rounded-xl border shadow-sm cursor-pointer transition-all ${
            filterLight === 'RED' ? 'border-rose-500 bg-rose-50/40' : 'bg-white border-slate-200 hover:border-rose-300'
          }`}
        >
          <div className="text-[11px] font-bold text-rose-600 uppercase tracking-wide flex items-center justify-between">
            <span>Alerta Crítica (Día 20)</span>
            <AlertOctagon className="w-4 h-4 text-rose-600" />
          </div>
          <div className="text-2xl font-bold text-rose-700 font-mono mt-1">{redCount}</div>
        </div>

        <div
          onClick={() => setFilterLight('YELLOW')}
          className={`p-4 rounded-xl border shadow-sm cursor-pointer transition-all ${
            filterLight === 'YELLOW' ? 'border-amber-500 bg-amber-50/40' : 'bg-white border-slate-200 hover:border-amber-300'
          }`}
        >
          <div className="text-[11px] font-bold text-amber-600 uppercase tracking-wide flex items-center justify-between">
            <span>Atención Requerida</span>
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-2xl font-bold text-amber-700 font-mono mt-1">{yellowCount}</div>
        </div>

        <div
          onClick={() => setFilterLight('GREEN')}
          className={`p-4 rounded-xl border shadow-sm cursor-pointer transition-all ${
            filterLight === 'GREEN' ? 'border-emerald-500 bg-emerald-50/40' : 'bg-white border-slate-200 hover:border-emerald-300'
          }`}
        >
          <div className="text-[11px] font-bold text-emerald-600 uppercase tracking-wide flex items-center justify-between">
            <span>Al Día / Cuadrados</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-emerald-700 font-mono mt-1">{greenCount}</div>
        </div>
      </div>

      {/* Buscador y Tabla de Clientes */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between gap-4">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Buscar por Razón Social o CIF..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs border rounded-lg outline-none bg-slate-50 focus:bg-white"
            />
          </div>
          <div className="text-xs text-slate-400">
            Mostrando {filteredClients.length} de {clients.length} empresas
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold border-b">
              <tr>
                <th className="py-3 px-4 text-left">Empresa Cliente</th>
                <th className="py-3 px-3 text-center">Semáforo Fiscal</th>
                <th className="py-3 px-3 text-center">Buzón Email (Pend.)</th>
                <th className="py-3 px-3 text-center">Conciliación Bancaria</th>
                <th className="py-3 px-3 text-center">Estado PSD2</th>
                <th className="py-3 px-4 text-right">Acción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredClients.map((c) => {
                const isCurrent = c.company_id === currentCompanyId;
                return (
                  <tr key={c.company_id} className={`hover:bg-slate-50/80 ${isCurrent ? 'bg-indigo-50/30' : ''}`}>
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900 flex items-center gap-2">
                        <span>{c.razon_social}</span>
                        {isCurrent && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-100 text-indigo-700">
                            Activa
                          </span>
                        )}
                      </div>
                      <div className="font-mono text-slate-400 text-[11px]">{c.cif}</div>
                    </td>

                    <td className="py-3 px-3 text-center">
                      <div className="inline-flex flex-col items-center">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            c.tax_traffic_light === 'RED'
                              ? 'bg-rose-100 text-rose-700'
                              : c.tax_traffic_light === 'YELLOW'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-emerald-100 text-emerald-700'
                          }`}
                        >
                          {c.tax_traffic_light === 'RED'
                            ? 'Crítico'
                            : c.tax_traffic_light === 'YELLOW'
                            ? 'Pendiente'
                            : 'Al Día'}
                        </span>
                        <span className="text-[10px] text-slate-400 mt-0.5">{c.tax_period}</span>
                      </div>
                    </td>

                    <td className="py-3 px-3 text-center">
                      <div className="flex items-center justify-center gap-1 font-mono font-bold">
                        <Mail className="w-3.5 h-3.5 text-slate-400" />
                        <span className={c.pending_inbound_invoices > 0 ? 'text-amber-600' : 'text-slate-600'}>
                          {c.pending_inbound_invoices}
                        </span>
                      </div>
                    </td>

                    <td className="py-3 px-3 text-center">
                      <div className="space-y-1">
                        <div className="flex items-center justify-center gap-1.5">
                          <span className="font-mono font-bold text-slate-800">
                            {c.bank_reconciliation_rate}%
                          </span>
                          <span className="text-[10px] text-slate-400">
                            ({c.unreconciled_bank_transactions} sin casar)
                          </span>
                        </div>
                        <div className="w-24 h-1.5 bg-slate-100 rounded-full mx-auto overflow-hidden">
                          <div
                            className={`h-full ${
                              c.bank_reconciliation_rate >= 85
                                ? 'bg-emerald-500'
                                : c.bank_reconciliation_rate >= 50
                                ? 'bg-amber-500'
                                : 'bg-rose-500'
                            }`}
                            style={{ width: `${c.bank_reconciliation_rate}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-3 text-center">
                      {c.is_psd2_connected ? (
                        <div className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                          <span>Sincronizado</span>
                        </div>
                      ) : (
                        <div className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-300"></span>
                          <span>Manual</span>
                        </div>
                      )}
                    </td>

                    <td className="py-3 px-4 text-right">
                      {isCurrent ? (
                        <span className="text-xs text-indigo-600 font-bold">Seleccionada</span>
                      ) : (
                        <button
                          onClick={() => {
                            onSelectCompany(c.company_id);
                            onNotify('success', `Conmutado a la empresa ${c.razon_social}`, 'Conmutador Multi-Tenant');
                          }}
                          className="flex items-center gap-1 text-xs font-bold text-slate-700 hover:text-indigo-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:border-indigo-300 bg-white hover:bg-indigo-50/50 transition-all ml-auto shadow-sm"
                        >
                          Gestionar <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

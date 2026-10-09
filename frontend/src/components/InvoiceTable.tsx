'use client';

import React, { useState, useEffect } from 'react';
import { Invoice, TrafficLightStatus } from '@/types';
import { TrafficLightBadge } from './TrafficLightBadge';
import {
  Search,
  SlidersHorizontal,
  FileText,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  Trash2,
  CheckSquare,
  Square,
  X,
  AlertTriangle,
  Scissors,
  Sparkles,
} from 'lucide-react';

interface Props {
  invoices: Invoice[];
  onSelectInvoice: (invoice: Invoice) => void;
  selectedInvoiceId?: string;
  onDeleteInvoice?: (invoice: Invoice) => void;
  onBulkDelete?: (invoiceIds: string[]) => void;
  onOpenSplitter?: (invoice: Invoice) => void;
}

export const InvoiceTable: React.FC<Props> = ({
  invoices,
  onSelectInvoice,
  selectedInvoiceId,
  onDeleteInvoice,
  onBulkDelete,
  onOpenSplitter,
}) => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [processedFilter, setProcessedFilter] = useState<string>('ALL');

  // Selección múltiple para borrado por lotes
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Sincronización estricta: sólo conservar IDs que efectivamente sigan existiendo en invoices
  useEffect(() => {
    setSelectedIds((prev) => {
      if (prev.length === 0) return prev;
      const valid = prev.filter((id) => invoices.some((inv) => inv.id === id));
      return valid.length === prev.length ? prev : valid;
    });
  }, [invoices]);

  // IDs seleccionados actualmente válidos y presentes en los datos
  const validSelectedIds = selectedIds.filter((id) =>
    invoices.some((inv) => inv.id === id)
  );

  // Filtrado reactivo sobre las facturas
  const filteredInvoices = invoices.filter((inv) => {
    // Búsqueda
    const term = search.toLowerCase();
    const matchesSearch =
      inv.issuer_name.toLowerCase().includes(term) ||
      inv.issuer_cif.toLowerCase().includes(term) ||
      inv.invoice_number.toLowerCase().includes(term);

    // Estado de semáforo
    const matchesStatus =
      statusFilter === 'ALL' || inv.status === statusFilter;

    // Estado de procesada
    const matchesProcessed =
      processedFilter === 'ALL' ||
      (processedFilter === 'PENDING' && !inv.is_processed) ||
      (processedFilter === 'PROCESSED' && inv.is_processed);

    return matchesSearch && matchesStatus && matchesProcessed;
  });

  // Manejo de selección masiva
  const handleToggleSelectAll = () => {
    if (validSelectedIds.length > 0) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredInvoices.map((inv) => inv.id));
    }
  };

  const handleToggleSelectRow = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleClearSelection = () => {
    setSelectedIds([]);
  };

  // Solicita la confirmación de borrado masivo al padre
  const handleExecuteBulkDelete = () => {
    if (validSelectedIds.length === 0 || !onBulkDelete) return;
    onBulkDelete([...validSelectedIds]);
  };

  // Borrado individual asegurando limpieza de selección
  const handleDeleteRow = (inv: Invoice, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedIds((prev) => prev.filter((id) => id !== inv.id));
    if (onDeleteInvoice) {
      onDeleteInvoice(inv);
    }
  };

  const isAllSelected =
    filteredInvoices.length > 0 &&
    validSelectedIds.length === filteredInvoices.length;

  return (
    <div className="relative bg-slate-900/60 rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
      {/* Barra de Filtros y Búsqueda */}
      <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-900/80">
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por emisor, CIF o nº factura..."
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-950 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Pills de Semáforo */}
          <div className="flex items-center p-0.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-medium">
            <button
              type="button"
              onClick={() => setStatusFilter('ALL')}
              className={`px-3 py-1 rounded-lg transition ${
                statusFilter === 'ALL'
                  ? 'bg-slate-800 text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Todas ({invoices.length})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter('GREEN')}
              className={`px-2.5 py-1 rounded-lg flex items-center gap-1 transition ${
                statusFilter === 'GREEN'
                  ? 'bg-emerald-950 text-emerald-300 font-semibold border border-emerald-800/40'
                  : 'text-emerald-400/80 hover:text-emerald-300'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              Verdes
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter('YELLOW')}
              className={`px-2.5 py-1 rounded-lg flex items-center gap-1 transition ${
                statusFilter === 'YELLOW'
                  ? 'bg-amber-950 text-amber-300 font-semibold border border-amber-800/40'
                  : 'text-amber-400/80 hover:text-amber-300'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              Amarillas
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter('RED')}
              className={`px-2.5 py-1 rounded-lg flex items-center gap-1 transition ${
                statusFilter === 'RED'
                  ? 'bg-rose-950 text-rose-300 font-semibold border border-rose-800/40'
                  : 'text-rose-400/80 hover:text-rose-300'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-rose-400" />
              Rojas
            </button>
          </div>

          {/* Filtro Procesadas */}
          <select
            value={processedFilter}
            onChange={(e) => setProcessedFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-xl text-slate-300 focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">Todos los estados</option>
            <option value="PENDING">Pendientes de triaje</option>
            <option value="PROCESSED">Aprobadas / Archivadas</option>
          </select>
        </div>
      </div>

      {/* Tabla de Facturas */}
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full min-w-[850px] text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-950/40 text-[11px] text-slate-400 uppercase tracking-wider">
              {/* Checkbox select all */}
              <th className="py-3 px-3 w-10 text-center">
                <input
                  type="checkbox"
                  checked={isAllSelected}
                  onChange={handleToggleSelectAll}
                  className="w-4 h-4 rounded bg-slate-950 border-slate-700 text-cyan-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
                  title="Seleccionar todas"
                />
              </th>
              <th className="py-3 px-4 font-semibold">Semáforo</th>
              <th className="py-3 px-4 font-semibold">Confianza IA</th>
              <th className="py-3 px-4 font-semibold">Nº Factura</th>
              <th className="py-3 px-4 font-semibold">Emisor (Proveedor)</th>
              <th className="py-3 px-4 font-semibold">Fecha</th>
              <th className="py-3 px-4 font-semibold text-right">Total (€)</th>
              <th className="py-3 px-4 font-semibold">Estado</th>
              <th className="py-3 px-4 font-semibold text-right">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filteredInvoices.length === 0 ? (
              <tr>
                <td colSpan={9} className="text-center py-12 text-slate-500">
                  <FileText className="w-10 h-10 mx-auto mb-2 opacity-30 text-slate-400" />
                  <p className="text-sm font-medium">No hay facturas que coincidan con los filtros</p>
                </td>
              </tr>
            ) : (
              filteredInvoices.map((inv) => {
                const isSelected = inv.id === selectedInvoiceId;
                const isChecked = selectedIds.includes(inv.id);

                return (
                  <tr
                    key={inv.id}
                    onClick={() => onSelectInvoice(inv)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-cyan-950/30 border-l-2 border-l-cyan-400'
                        : isChecked
                        ? 'bg-slate-800/30'
                        : 'hover:bg-slate-850/40'
                    }`}
                  >
                    {/* Checkbox de fila */}
                    <td
                      className="py-3 px-3 text-center"
                      onClick={(e) => handleToggleSelectRow(inv.id, e)}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => {}}
                        className="w-4 h-4 rounded bg-slate-950 border-slate-700 text-cyan-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
                      />
                    </td>

                    <td className="py-3 px-4">
                      <TrafficLightBadge
                        status={inv.status}
                        reasonsCount={inv.status_reasons?.length}
                        size="sm"
                        esMultifactura={inv.es_multifactura}
                      />
                    </td>
                    <td className="py-3 px-4">
                      {inv.status === 'GREEN' ? (
                        <div
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-[11px] font-medium"
                          title="Extracción limpia de todos los campos, sin descuadre ni incidencias"
                        >
                          <Sparkles className="w-3 h-3 text-emerald-400" />
                          <span>Certeza: 98%</span>
                        </div>
                      ) : inv.status === 'YELLOW' ? (
                        <div
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/25 text-[11px] font-medium"
                          title="Revisar subcuenta contable o proveedor nuevo sugerido"
                        >
                          <Sparkles className="w-3 h-3 text-amber-400" />
                          <span>Certeza: 82%</span>
                        </div>
                      ) : (
                        <div
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-500/10 text-rose-300 border border-rose-500/25 text-[11px] font-medium animate-pulse"
                          title={inv.status_reasons?.[0] || 'Descuadre aritmético o CIF inválido'}
                        >
                          <AlertTriangle className="w-3 h-3 text-rose-400" />
                          <span>Atención requerida</span>
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono font-medium text-white">
                      <div className="flex items-center gap-2">
                        <span>{inv.invoice_number}</span>
                        {inv.num_paginas && inv.num_paginas > 1 && (
                          <span className="text-[10px] font-sans px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 border border-slate-700">
                            {inv.num_paginas} págs
                          </span>
                        )}
                      </div>
                      {inv.status === 'RED' && inv.status_reasons && inv.status_reasons.length > 0 && (
                        <div
                          className="mt-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-rose-950/60 text-rose-300 border border-rose-800/60 text-[10px] font-sans font-medium max-w-[240px] truncate shadow-sm"
                          title={inv.status_reasons[0]}
                        >
                          <AlertTriangle className="w-3 h-3 text-rose-400 shrink-0" />
                          <span className="truncate">{inv.status_reasons[0]}</span>
                        </div>
                      )}
                      {inv.status === 'YELLOW' && (
                        <div
                          className="mt-1 text-[10px] text-amber-300/90 font-sans flex items-center gap-1 truncate max-w-[220px]"
                          title="Proveedor nuevo: subcuentas asignadas para alta automática al aprobar"
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
                          <span>Alta asistida preparada</span>
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-200 truncate max-w-[200px]">
                        {inv.issuer_name}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {inv.issuer_cif}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-400 font-mono">
                      {inv.issue_date}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-white">
                      {inv.total_amount?.toLocaleString('es-ES', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}{' '}
                      €
                    </td>
                    <td className="py-3 px-4">
                      {inv.is_processed ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                          <FileCheck className="w-3 h-3" />
                          Archivada
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                          <AlertCircle className="w-3 h-3" />
                          Pendiente
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        {/* Botón Maquetador de Corte para documentos Multi-Factura */}
                        {inv.es_multifactura && onOpenSplitter && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onOpenSplitter(inv);
                            }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg bg-purple-600/20 hover:bg-purple-600/35 text-purple-300 border border-purple-500/40 shadow-sm transition cursor-pointer"
                            title="Abrir Maquetador Visual de Corte (Multi-Factura)"
                          >
                            <Scissors className="w-3.5 h-3.5 text-purple-300" />
                            Cortar
                          </button>
                        )}

                        {/* Botón de papelera individual */}
                        {onDeleteInvoice && (
                          <button
                            type="button"
                            onClick={(e) => handleDeleteRow(inv, e)}
                            className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition border border-transparent hover:border-rose-500/20 cursor-pointer"
                            title="Eliminar factura y fichero"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectInvoice(inv);
                          }}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg bg-cyan-600/15 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 transition cursor-pointer"
                        >
                          Triaje
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 2. BARRA DE ACCIONES FLOTANTE: Oculta estrictamente si no hay facturas seleccionadas válidas */}
      {validSelectedIds.length > 0 && (
        <div className="sticky bottom-0 left-0 right-0 z-20 px-6 py-3 bg-slate-950/95 border-t border-cyan-500/40 backdrop-blur-md flex items-center justify-between shadow-2xl animate-in slide-in-from-bottom-2 duration-150">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-cyan-500/20 text-cyan-400 font-bold text-xs font-mono">
              {validSelectedIds.length}
            </span>
            <span className="text-xs text-slate-300 font-medium">
              {validSelectedIds.length === 1
                ? '1 factura seleccionada'
                : `${validSelectedIds.length} facturas seleccionadas`}
            </span>
            <button
              type="button"
              onClick={handleClearSelection}
              className="text-xs text-slate-400 hover:text-white underline ml-2 cursor-pointer transition"
            >
              Deseleccionar todas
            </button>
          </div>

          <div className="flex items-center gap-2">
            {onBulkDelete && (
              <button
                type="button"
                onClick={handleExecuteBulkDelete}
                className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-xl bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-950/50 transition cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Borrar {validSelectedIds.length} {validSelectedIds.length === 1 ? 'factura' : 'facturas'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

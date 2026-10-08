'use client';

import React, { useState, useEffect } from 'react';
import { Invoice, InvoicePagesResponse, PageThumbnail } from '@/types';
import { fetchInvoicePages, splitInvoice, getPageThumbnailUrl } from '@/lib/api';
import {
  Scissors,
  Layers,
  Trash2,
  Undo2,
  Check,
  X,
  FileText,
  AlertCircle,
  Plus,
  ArrowRight,
  Sparkles,
  RefreshCw,
  Eye,
  CheckCircle2,
} from 'lucide-react';

interface Props {
  isOpen: boolean;
  invoice: Invoice;
  onClose: () => void;
  onSuccess: (newInvoices: Invoice[]) => void;
  onNotify?: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
}

interface SplitItem {
  id: string;
  name: string;
  color: string;
  borderColor: string;
  bgBadge: string;
}

const SPLIT_COLORS = [
  { color: 'text-indigo-400', borderColor: 'border-indigo-500', bgBadge: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40' },
  { color: 'text-emerald-400', borderColor: 'border-emerald-500', bgBadge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' },
  { color: 'text-amber-400', borderColor: 'border-amber-500', bgBadge: 'bg-amber-500/20 text-amber-300 border-amber-500/40' },
  { color: 'text-purple-400', borderColor: 'border-purple-500', bgBadge: 'bg-purple-500/20 text-purple-300 border-purple-500/40' },
  { color: 'text-cyan-400', borderColor: 'border-cyan-500', bgBadge: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40' },
  { color: 'text-rose-400', borderColor: 'border-rose-500', bgBadge: 'bg-rose-500/20 text-rose-300 border-rose-500/40' },
];

export const MultiInvoiceSplitterModal: React.FC<Props> = ({
  isOpen,
  invoice,
  onClose,
  onSuccess,
  onNotify = () => {},
}) => {
  const [loadingPages, setLoadingPages] = useState<boolean>(true);
  const [pages, setPages] = useState<PageThumbnail[]>([]);
  const [totalPages, setTotalPages] = useState<number>(0);

  // Mapeo de número de página -> ID de factura asignada (o 'DISCARDED')
  const [pageAssignments, setPageAssignments] = useState<Record<number, string>>({});

  // Lista de facturas creadas en la sesión de maquetado
  const [splits, setSplits] = useState<SplitItem[]>([
    { id: 'split_1', name: 'Factura 1', ...SPLIT_COLORS[0] },
  ]);

  const [activeSplitId, setActiveSplitId] = useState<string>('split_1');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [previewPage, setPreviewPage] = useState<number | null>(null);

  // Cargar páginas del documento
  useEffect(() => {
    if (!isOpen || !invoice) return;

    const loadPages = async () => {
      setLoadingPages(true);
      try {
        const data = await fetchInvoicePages(invoice.id);
        setPages(data.pages);
        setTotalPages(data.num_paginas);

        // Inicializar: Asignar cada página a una factura independiente por defecto
        // o a Factura 1
        const initialAssignments: Record<number, string> = {};
        const initialSplits: SplitItem[] = [];

        if (data.num_paginas <= 4) {
          // Si tiene 2-4 páginas, sugerir inicialmente cada página como factura separada
          data.pages.forEach((p, idx) => {
            const splitId = `split_${idx + 1}`;
            const colorCfg = SPLIT_COLORS[idx % SPLIT_COLORS.length];
            initialSplits.push({
              id: splitId,
              name: `Factura ${idx + 1}`,
              ...colorCfg,
            });
            initialAssignments[p.page_number] = splitId;
          });
          setSplits(initialSplits);
          setActiveSplitId(initialSplits[0]?.id || 'split_1');
        } else {
          // Documentos más largos: Asignar a Factura 1 e ir cortando
          initialSplits.push({
            id: 'split_1',
            name: 'Factura 1',
            ...SPLIT_COLORS[0],
          });
          data.pages.forEach((p) => {
            initialAssignments[p.page_number] = 'split_1';
          });
          setSplits(initialSplits);
          setActiveSplitId('split_1');
        }

        setPageAssignments(initialAssignments);
      } catch (err: any) {
        onNotify('error', err.message || 'Error al cargar las páginas del documento');
      } finally {
        setLoadingPages(false);
      }
    };

    loadPages();
  }, [isOpen, invoice]);

  if (!isOpen) return null;

  // Añadir un nuevo grupo de factura
  const handleAddNewSplit = () => {
    const nextIdx = splits.length + 1;
    const colorCfg = SPLIT_COLORS[(nextIdx - 1) % SPLIT_COLORS.length];
    const newId = `split_${Date.now()}`;
    const newSplit: SplitItem = {
      id: newId,
      name: `Factura ${nextIdx}`,
      ...colorCfg,
    };
    setSplits([...splits, newSplit]);
    setActiveSplitId(newId);
  };

  // Asignar una página a un split específico
  const handleAssignPage = (pageNum: number, splitId: string) => {
    setPageAssignments((prev) => ({
      ...prev,
      [pageNum]: splitId,
    }));
  };

  // Botón de tijeras ✂️: Cortar y crear una nueva factura a partir de esta página
  const handleCutAtPage = (pageNum: number) => {
    const nextIdx = splits.length + 1;
    const colorCfg = SPLIT_COLORS[(nextIdx - 1) % SPLIT_COLORS.length];
    const newId = `split_${Date.now()}`;
    const newSplit: SplitItem = {
      id: newId,
      name: `Factura ${nextIdx}`,
      ...colorCfg,
    };
    setSplits([...splits, newSplit]);

    // Asignar esta página al nuevo split
    setPageAssignments((prev) => ({
      ...prev,
      [pageNum]: newId,
    }));
    setActiveSplitId(newId);
  };

  // Eliminar/descartar página sobrante
  const handleToggleDiscardPage = (pageNum: number) => {
    setPageAssignments((prev) => {
      const current = prev[pageNum];
      if (current === 'DISCARDED') {
        // Restaurar a la primera factura activa
        return { ...prev, [pageNum]: splits[0]?.id || 'split_1' };
      } else {
        // Descartar
        return { ...prev, [pageNum]: 'DISCARDED' };
      }
    });
  };

  // Calcular resumen de splits
  const activeSplitsWithPages = splits
    .map((s) => {
      const assignedPages = Object.entries(pageAssignments)
        .filter(([_, assignedId]) => assignedId === s.id)
        .map(([num]) => Number(num))
        .sort((a, b) => a - b);
      return { ...s, assignedPages };
    })
    .filter((s) => s.assignedPages.length > 0);

  const discardedPages = Object.entries(pageAssignments)
    .filter(([_, assignedId]) => assignedId === 'DISCARDED')
    .map(([num]) => Number(num))
    .sort((a, b) => a - b);

  // Confirmar y ejecutar la disgregación
  const handleConfirmSplit = async () => {
    if (activeSplitsWithPages.length === 0) {
      onNotify('error', 'Debe haber al menos una factura con páginas asignadas.');
      return;
    }

    setSubmitting(true);
    try {
      const payloadSplits = activeSplitsWithPages.map((s, idx) => ({
        page_numbers: s.assignedPages,
        custom_name: s.name,
      }));

      const newInvoices = await splitInvoice(invoice.id, {
        splits: payloadSplits,
      });

      onNotify(
        'success',
        `Documento separado con éxito en ${newInvoices.length} facturas independientes.`,
        'Separación Completada'
      );
      onSuccess(newInvoices);
      onClose();
    } catch (err: any) {
      onNotify('error', err.message || 'Error al separar las facturas', 'Fallo de Separación');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-6xl shadow-2xl flex flex-col max-h-[92vh] overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Cabecera Principal */}
        <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <Scissors className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white tracking-tight">
                  Maquetador Visual de Corte Multi-Factura (MF)
                </h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40">
                  MF • {totalPages} Páginas
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Archivo: <span className="text-slate-200 font-mono">{invoice.file_name}</span> • Disgrega en sub-documentos independientes nombrados automáticamente.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Barra de Herramientas y Gestión de Sub-Facturas */}
        <div className="px-6 py-3 bg-slate-900/90 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-slate-400 mr-1 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              Grupos de Corte:
            </span>

            {splits.map((s, idx) => {
              const assignedCount = Object.values(pageAssignments).filter((id) => id === s.id).length;
              const isActive = activeSplitId === s.id;
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setActiveSplitId(s.id)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium border transition-all ${
                    isActive
                      ? `${s.bgBadge} ring-1 ring-purple-500 font-bold shadow-sm`
                      : 'bg-slate-800/60 border-slate-700 text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <span className="w-2 h-2 rounded-full bg-current" />
                  <span>{s.name}</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-black/40 text-white">
                    {assignedCount} pág{assignedCount !== 1 ? 's' : ''}
                  </span>
                </button>
              );
            })}

            <button
              type="button"
              onClick={handleAddNewSplit}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 transition"
            >
              <Plus className="w-3.5 h-3.5" />
              Nueva Factura
            </button>
          </div>

          <div className="text-xs text-slate-400 flex items-center gap-3">
            {discardedPages.length > 0 && (
              <span className="text-rose-400 text-xs font-medium flex items-center gap-1">
                <Trash2 className="w-3.5 h-3.5" />
                {discardedPages.length} página{discardedPages.length !== 1 ? 's' : ''} descartada{discardedPages.length !== 1 ? 's' : ''}
              </span>
            )}
            <span className="text-slate-500 font-mono text-[11px]">
              Se generarán {activeSplitsWithPages.length} factura{activeSplitsWithPages.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        {/* Zona Central: Cuadrícula de Páginas con Miniaturas */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-950/40 space-y-6">
          {loadingPages ? (
            <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400 text-sm">
              <RefreshCw className="w-7 h-7 animate-spin text-purple-400" />
              <span>Generando miniaturas de las páginas del PDF...</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
              {pages.map((p) => {
                const assignedSplitId = pageAssignments[p.page_number];
                const isDiscarded = assignedSplitId === 'DISCARDED';
                const assignedSplit = splits.find((s) => s.id === assignedSplitId);

                return (
                  <div
                    key={p.page_number}
                    className={`relative rounded-xl border-2 transition-all flex flex-col overflow-hidden group ${
                      isDiscarded
                        ? 'border-rose-900/50 bg-rose-950/20 opacity-50 grayscale'
                        : assignedSplit
                        ? `${assignedSplit.borderColor} bg-slate-900 shadow-lg`
                        : 'border-slate-800 bg-slate-900'
                    }`}
                  >
                    {/* Barra superior de la página */}
                    <div className="px-3 py-2 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold text-white font-mono">
                          Pág. {p.page_number}
                        </span>
                        {assignedSplit && !isDiscarded && (
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${assignedSplit.bgBadge}`}
                          >
                            {assignedSplit.name}
                          </span>
                        )}
                        {isDiscarded && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-900/40 text-rose-300 border border-rose-800/40">
                            Descartada
                          </span>
                        )}
                      </div>

                      {/* Botón de descartar / restaurar */}
                      <button
                        type="button"
                        onClick={() => handleToggleDiscardPage(p.page_number)}
                        className={`p-1 rounded transition ${
                          isDiscarded
                            ? 'text-emerald-400 hover:bg-emerald-500/20'
                            : 'text-slate-400 hover:text-rose-400 hover:bg-rose-500/10'
                        }`}
                        title={isDiscarded ? 'Restaurar página' : 'Descartar página sobrante'}
                      >
                        {isDiscarded ? <Undo2 className="w-3.5 h-3.5" /> : <Trash2 className="w-3.5 h-3.5" />}
                      </button>
                    </div>

                    {/* Miniatura visual de la página */}
                    <div className="relative aspect-[3/4] bg-slate-950 flex items-center justify-center p-2 overflow-hidden">
                      <img
                        src={getPageThumbnailUrl(invoice.id, p.page_number)}
                        alt={`Página ${p.page_number}`}
                        className="w-full h-full object-contain rounded shadow-sm transition group-hover:scale-102"
                        loading="lazy"
                      />

                      {/* Botón flotante para ver en grande */}
                      <button
                        type="button"
                        onClick={() => setPreviewPage(p.page_number)}
                        className="absolute bottom-3 right-3 p-1.5 rounded-lg bg-black/60 hover:bg-black/90 text-white opacity-0 group-hover:opacity-100 transition shadow"
                        title="Ver página ampliada"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Acciones de corte y asignación en la base de la tarjeta */}
                    <div className="p-2.5 bg-slate-900/90 border-t border-slate-800 flex items-center justify-between gap-2">
                      {/* Selector de grupo de corte */}
                      <select
                        value={isDiscarded ? 'DISCARDED' : assignedSplitId || splits[0]?.id}
                        onChange={(e) => {
                          if (e.target.value === 'DISCARDED') {
                            handleToggleDiscardPage(p.page_number);
                          } else {
                            handleAssignPage(p.page_number, e.target.value);
                          }
                        }}
                        className="flex-1 text-[11px] font-medium px-2 py-1 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-purple-500"
                      >
                        {splits.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name}
                          </option>
                        ))}
                        <option value="DISCARDED">🗑️ Descartar</option>
                      </select>

                      {/* Botón de tijeras ✂️: Cortar aquí e iniciar nueva factura */}
                      <button
                        type="button"
                        onClick={() => handleCutAtPage(p.page_number)}
                        className="p-1.5 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 transition flex items-center gap-1 text-[10px] font-bold"
                        title="Cortar aquí: inicia una nueva factura con esta página"
                      >
                        <Scissors className="w-3.5 h-3.5 text-purple-400" />
                        <span>Cortar</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Modal de previsualización ampliada de página */}
        {previewPage && (
          <div
            className="fixed inset-0 z-60 bg-black/90 flex items-center justify-center p-6 cursor-pointer"
            onClick={() => setPreviewPage(null)}
          >
            <div className="relative max-w-3xl max-h-[90vh] bg-slate-900 rounded-xl overflow-hidden p-2">
              <img
                src={getPageThumbnailUrl(invoice.id, previewPage)}
                alt={`Página ${previewPage}`}
                className="max-h-[85vh] w-auto object-contain mx-auto"
              />
              <div className="text-center text-xs text-slate-300 mt-2 font-mono">
                Página {previewPage} de {totalPages} • Clic para cerrar
              </div>
            </div>
          </div>
        )}

        {/* Pie de Página: Resumen y Botón de Separación */}
        <div className="px-6 py-4 bg-slate-950 border-t border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4 shrink-0">
          <div>
            <div className="text-xs font-bold text-white mb-1 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              Sub-Documentos a Generar:
            </div>
            <div className="flex flex-wrap gap-2 text-[11px] font-mono text-slate-300">
              {activeSplitsWithPages.map((s, idx) => (
                <span
                  key={s.id}
                  className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 flex items-center gap-1.5"
                >
                  <strong className={s.color}>{s.name}:</strong>
                  <span>
                    [original]_factura_{idx + 1}.pdf (págs: {s.assignedPages.join(', ')})
                  </span>
                </span>
              ))}
              {discardedPages.length > 0 && (
                <span className="px-2.5 py-1 rounded bg-rose-950/40 border border-rose-900/50 text-rose-300">
                  Descartadas: págs {discardedPages.join(', ')}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            >
              Cancelar
            </button>

            <button
              type="button"
              onClick={handleConfirmSplit}
              disabled={submitting || activeSplitsWithPages.length === 0}
              className={`flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-bold text-white shadow-lg transition-all ${
                submitting || activeSplitsWithPages.length === 0
                  ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                  : 'bg-purple-600 hover:bg-purple-500 shadow-purple-950/40 active:scale-95'
              }`}
            >
              {submitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Disgregando con IA...
                </>
              ) : (
                <>
                  <Scissors className="w-4 h-4" />
                  Separar Factura ({activeSplitsWithPages.length} Documentos)
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

'use client';

import React, { useState, useEffect } from 'react';
import { fetchProposedArchivePath } from '@/lib/api';
import { ProposedArchivePath } from '@/types';
import {
  Archive,
  FolderTree,
  FileText,
  Check,
  X,
  AlertTriangle,
  FolderCog,
  FolderCheck,
  Tags,
  Sparkles,
} from 'lucide-react';

interface Props {
  isOpen: boolean;
  invoiceId: string;
  invoiceNumber: string;
  companyCif: string;
  onClose: () => void;
  onConfirm: (customDest?: {
    custom_subfolder?: string;
    custom_filename?: string;
  }) => Promise<void>;
}

const QUICK_SUBFOLDERS = [
  { label: 'Recibidas', key: 'recibidas', color: 'border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10' },
  { label: 'Emitidas', key: 'emitidas', color: 'border-blue-500/40 text-blue-300 hover:bg-blue-500/10' },
  { label: 'Tickets / Gastos varios', key: 'tickets_gastos', color: 'border-amber-500/40 text-amber-300 hover:bg-amber-500/10' },
  { label: 'Inversiones', key: 'inversiones', color: 'border-purple-500/40 text-purple-300 hover:bg-purple-500/10' },
];

export const ArchiveConfirmationModal: React.FC<Props> = ({
  isOpen,
  invoiceId,
  invoiceNumber,
  companyCif,
  onClose,
  onConfirm,
}) => {
  const [loading, setLoading] = useState(false);
  const [fetchingPath, setFetchingPath] = useState(false);
  const [proposed, setProposed] = useState<ProposedArchivePath | null>(null);

  // Campos editables
  const [customSubfolder, setCustomSubfolder] = useState('');
  const [customFilename, setCustomFilename] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !invoiceId) return;

    const loadProposed = async () => {
      setFetchingPath(true);
      setError(null);
      try {
        const data = await fetchProposedArchivePath(invoiceId);
        setProposed(data);
        setCustomSubfolder(data.subfolder);
        setCustomFilename(data.filename);
      } catch (err: any) {
        console.error('Error fetching proposed path:', err);
        setError('No se pudo calcular la ruta automática. Puedes introducirla manualmente.');
        const fallbackSubfolder = `storage/${companyCif}/2026/T1/recibidas`;
        const fallbackFilename = `factura_${invoiceNumber.replace(/[\/\\:]/g, '_')}.pdf`;
        setCustomSubfolder(fallbackSubfolder);
        setCustomFilename(fallbackFilename);
      } finally {
        setFetchingPath(false);
      }
    };

    loadProposed();
  }, [isOpen, invoiceId, companyCif, invoiceNumber]);

  if (!isOpen) return null;

  // Cambiar subcarpeta rápida
  const handleQuickFolderSelect = (folderKey: string) => {
    const trimmed = customSubfolder.trim().replace(/[\\\/]+$/, '');
    const parts = trimmed.split('/');
    if (parts.length > 0) {
      parts[parts.length - 1] = folderKey;
      setCustomSubfolder(parts.join('/'));
    } else {
      setCustomSubfolder(folderKey);
    }
  };

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = {
        custom_subfolder: customSubfolder.trim(),
        custom_filename: customFilename.trim(),
      };
      await onConfirm(payload);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Error al archivar la factura');
    } finally {
      setLoading(false);
    }
  };

  const fullPathPreview = `${customSubfolder.replace(/[\\\/]+$/, '')}/${customFilename.replace(/^[\\\/]+/, '')}`;
  const currentLastFolder = customSubfolder.split('/').filter(Boolean).pop() || '';

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Cabecera */}
        <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Archive className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white tracking-tight">
                Selección de Carpeta de Destino al Archivar
              </h3>
              <p className="text-[11px] text-slate-400">
                Factura <span className="font-mono text-cyan-400">{invoiceNumber}</span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Contenido */}
        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {fetchingPath ? (
            <div className="py-8 flex flex-col items-center justify-center gap-2 text-slate-400 text-xs">
              <FolderCog className="w-6 h-6 animate-spin text-cyan-400" />
              <span>Calculando estructura de carpetas...</span>
            </div>
          ) : (
            <>
              {/* Ruta sugerida por defecto y preview */}
              <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <FolderTree className="w-3.5 h-3.5 text-cyan-400" />
                    Ruta final en disco / servidor de archivos:
                  </span>
                  {proposed && (
                    <span className="text-[10px] text-slate-500">
                      Sugerida: <code className="text-slate-400">{proposed.subfolder}</code>
                    </span>
                  )}
                </div>
                <p className="text-xs font-mono text-emerald-400 break-all bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
                  {fullPathPreview}
                </p>
              </div>

              {/* Selector de subcarpeta rápida */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
                  <Tags className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Selector de subcarpeta rápida:</span>
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {QUICK_SUBFOLDERS.map((qs) => {
                    const isSelected = currentLastFolder.toLowerCase() === qs.key.toLowerCase();
                    return (
                      <button
                        key={qs.key}
                        type="button"
                        onClick={() => handleQuickFolderSelect(qs.key)}
                        className={`px-2.5 py-1.5 rounded-xl text-xs font-medium border text-center transition flex items-center justify-center gap-1.5 ${
                          isSelected
                            ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200 shadow-sm shadow-cyan-900/50'
                            : `bg-slate-950/60 ${qs.color}`
                        }`}
                      >
                        {isSelected && <FolderCheck className="w-3 h-3 text-cyan-400 shrink-0" />}
                        <span>{qs.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Campo editable de carpeta / subcarpeta de destino */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1 flex items-center justify-between">
                  <span>Carpeta o subcarpeta de destino:</span>
                  <span className="text-[11px] text-slate-500 font-mono">
                    Editable (ej. [CIF]/[Año]/[Periodo]/recibidas)
                  </span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={customSubfolder}
                    onChange={(e) => setCustomSubfolder(e.target.value)}
                    placeholder="B12345678/2026/T1/recibidas"
                    className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-700 rounded-xl text-white font-mono focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>

              {/* Nombre de archivo editable */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1 flex items-center justify-between">
                  <span>Nombre del archivo guardado:</span>
                  <span className="text-[11px] text-slate-500 font-mono">
                    [fecha]_[cif_emisor]_[num].pdf
                  </span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={customFilename}
                    onChange={(e) => setCustomFilename(e.target.value)}
                    placeholder="2026-03-15_B12345678_FAC-001.pdf"
                    className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-700 rounded-xl text-white font-mono focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-slate-950 border-t border-slate-800 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-xs font-medium rounded-xl text-slate-400 hover:text-white bg-slate-900 border border-slate-800 hover:bg-slate-800 transition"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={loading || fetchingPath}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-950/50 transition"
          >
            <Check className="w-3.5 h-3.5" />
            {loading ? 'Moviendo y Archivando...' : 'Confirmar y Archivar'}
          </button>
        </div>
      </div>
    </div>
  );
};

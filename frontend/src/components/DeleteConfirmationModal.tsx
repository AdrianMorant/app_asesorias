'use client';

import React, { useState } from 'react';
import { AlertTriangle, Trash2, X, FileX, HardDrive } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  title?: string;
  count?: number;
  itemDescription?: string;
}

export const DeleteConfirmationModal: React.FC<Props> = ({
  isOpen,
  onClose,
  onConfirm,
  title = '¿Eliminar facturas seleccionadas?',
  count = 1,
  itemDescription,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Error al procesar la eliminación');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Cabecera de Peligro */}
        <div className="px-6 py-4 bg-rose-950/40 border-b border-rose-900/30 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <Trash2 className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white tracking-tight">
                {title}
              </h3>
              <p className="text-[11px] text-rose-300/80">
                Acción destructiva e irreversible
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

          <p className="text-xs text-slate-300 leading-relaxed">
            {count > 1 ? (
              <>
                Estás a punto de eliminar permanentemente{' '}
                <strong className="text-white font-semibold">{count} facturas</strong> seleccionadas.
              </>
            ) : (
              <>
                Estás a punto de eliminar permanentemente la factura{' '}
                {itemDescription ? (
                  <strong className="text-white font-semibold font-mono">{itemDescription}</strong>
                ) : (
                  'seleccionada'
                )}
                .
              </>
            )}
          </p>

          <div className="p-3.5 bg-slate-950 border border-slate-800/80 rounded-xl space-y-2 text-xs">
            <div className="font-semibold text-slate-300 flex items-center gap-1.5 text-[11px]">
              <HardDrive className="w-3.5 h-3.5 text-amber-400" />
              Efectos de esta operación:
            </div>
            <ul className="space-y-1 text-slate-400 text-[11px] list-disc list-inside">
              <li>Se cancelarán los apuntes contables y desgloses multi-IVA asociados en base de datos.</li>
              <li>
                <span className="text-rose-400 font-medium">Borrado físico en disco:</span> El archivo PDF se eliminará permanentemente de las carpetas locales o archivador digital.
              </li>
              <li>Esta acción no se puede deshacer.</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-950 border-t border-slate-800 flex items-center justify-end gap-2.5">
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
            disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-950/50 transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
            {loading ? 'Eliminando...' : count > 1 ? `Eliminar ${count} Facturas` : 'Eliminar Factura'}
          </button>
        </div>
      </div>
    </div>
  );
};

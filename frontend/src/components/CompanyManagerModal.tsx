'use client';

import React, { useState, useEffect } from 'react';
import { Company } from '@/types';
import { updateCompany, deleteCompany } from '@/lib/api';
import {
  Building2,
  X,
  Save,
  Trash2,
  AlertTriangle,
  FolderTree,
  Sliders,
  CheckCircle2,
} from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  company: Company | null;
  onCompanyUpdated: (updated: Company) => void;
  onCompanyDeleted: (deletedId: string) => void;
  notify: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
}

export const CompanyManagerModal: React.FC<Props> = ({
  isOpen,
  onClose,
  company,
  onCompanyUpdated,
  onCompanyDeleted,
  notify,
}) => {
  const [razonSocial, setRazonSocial] = useState('');
  const [planLongitud, setPlanLongitud] = useState(9);
  const [storageBasePath, setStorageBasePath] = useState('storage');
  const [ivaPeriodicity, setIvaPeriodicity] = useState<'Trimestral' | 'Mensual' | 'Anual'>('Trimestral');
  const [saving, setSaving] = useState(false);

  // Estado para la confirmación de eliminación estricta
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [confirmCifInput, setConfirmCifInput] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (company) {
      setRazonSocial(company.razon_social);
      setPlanLongitud(company.plan_cuentas_longitud || 9);
      setStorageBasePath(company.storage_base_path || 'storage');
      setIvaPeriodicity(company.iva_periodicity || 'Trimestral');
      setShowDeleteConfirm(false);
      setConfirmCifInput('');
    }
  }, [company]);

  if (!isOpen || !company) return null;

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updateCompany(company.id, {
        razon_social: razonSocial.trim(),
        plan_cuentas_longitud: planLongitud,
        storage_base_path: storageBasePath.trim(),
        iva_periodicity: ivaPeriodicity,
      });
      onCompanyUpdated(updated);
      notify('success', `Datos de la empresa '${updated.razon_social}' actualizados.`, 'Empresa Guardada');
      onClose();
    } catch (err: any) {
      notify('error', err.message || 'Error al actualizar empresa', 'Error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (confirmCifInput.trim().toUpperCase() !== company.cif.toUpperCase()) {
      notify('error', `El CIF tecleado no coincide con '${company.cif}'`, 'Confirmación Requerida');
      return;
    }
    setDeleting(true);
    try {
      await deleteCompany(company.id, confirmCifInput.trim());
      notify('success', `La empresa '${company.razon_social}' y sus documentos se han eliminado por completo.`, 'Empresa Eliminada');
      onCompanyDeleted(company.id);
      onClose();
    } catch (err: any) {
      notify('error', err.message || 'Error al eliminar la empresa', 'Error');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
        {/* Cabecera */}
        <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Building2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">Configuración de Empresa Asesorada</h2>
              <p className="text-[11px] text-slate-400">CIF: {company.cif}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Formulario */}
        <form onSubmit={handleUpdate} className="p-6 space-y-4 text-xs">
          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1">
              Razón Social / Nombre Comercial
            </label>
            <input
              type="text"
              required
              value={razonSocial}
              onChange={(e) => setRazonSocial(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                CIF / NIF (Identificador fiscal)
              </label>
              <input
                type="text"
                disabled
                value={company.cif}
                className="w-full px-3 py-2 bg-slate-900/50 border border-slate-800 rounded-xl text-slate-400 font-mono text-xs cursor-not-allowed"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                Longitud de Subcuentas (PGC)
              </label>
              <select
                value={planLongitud}
                onChange={(e) => setPlanLongitud(Number(e.target.value))}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-200 focus:outline-none focus:border-cyan-500 text-xs"
              >
                <option value={8}>8 dígitos</option>
                <option value={9}>9 dígitos (Estándar)</option>
                <option value={10}>10 dígitos</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1 flex items-center justify-between">
              <span>Periodicidad de Liquidación de IVA</span>
              <span className="text-[10px] text-cyan-400 font-mono">Modelo 303 / Carpetas</span>
            </label>
            <select
              value={ivaPeriodicity}
              onChange={(e) => setIvaPeriodicity(e.target.value as any)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-200 focus:outline-none focus:border-cyan-500 text-xs"
            >
              <option value="Trimestral">Trimestral (Régimen general PYMES: T1, T2, T3, T4)</option>
              <option value="Mensual">Mensual (Grandes empresas / REDEME / SII: 01_Enero a 12_Diciembre)</option>
              <option value="Anual">Anual (Regímenes especiales específicos)</option>
            </select>
            <p className="text-[10px] text-slate-500 mt-1">
              Determina las subcarpetas cronológicas automáticas del archivador digital.
            </p>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
              <FolderTree className="w-3.5 h-3.5 text-cyan-400" />
              Ruta Base de Archivado (Disco o Red)
            </label>
            <input
              type="text"
              value={storageBasePath}
              onChange={(e) => setStorageBasePath(e.target.value)}
              placeholder="storage o \\servidor\contabilidad\facturas"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white font-mono text-xs focus:outline-none focus:border-cyan-500"
            />
            <p className="text-[10px] text-slate-500 mt-1">
              Las facturas aprobadas se clasificarán en: <code className="text-slate-400">{storageBasePath}/{company.cif}/[año]/{ivaPeriodicity === 'Mensual' ? '[01_Enero..12_Diciembre]' : (ivaPeriodicity === 'Anual' ? '[Anual]' : '[T1..T4]')}/recibidas/</code>
            </p>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 font-medium text-slate-400 hover:text-white transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-1.5 px-4 py-2 font-semibold rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white transition shadow shadow-cyan-950"
            >
              <Save className="w-3.5 h-3.5" />
              {saving ? 'Guardando...' : 'Guardar Cambios'}
            </button>
          </div>
        </form>

        {/* Zona de Peligro: Eliminación de Empresa */}
        <div className="p-6 bg-rose-950/20 border-t border-rose-900/40 space-y-3 text-xs">
          <div className="flex items-center gap-2 text-rose-400 font-bold">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Zona de Peligro: Eliminación de Empresa</span>
          </div>
          <p className="text-slate-400 text-[11px] leading-relaxed">
            Elimina en cascada todos los proveedores, catálogo contable, facturas y <strong className="text-rose-300">borra físicamente los archivos del disco</strong> para evitar archivos huérfanos.
          </p>

          {!showDeleteConfirm ? (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 font-semibold rounded-xl bg-rose-600/15 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 transition"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Eliminar Empresa Definitivamente
            </button>
          ) : (
            <div className="p-3 bg-slate-950 rounded-xl border border-rose-800/60 space-y-2.5 animate-in fade-in">
              <p className="text-[11px] text-rose-300 font-medium">
                Para confirmar, teclea exactamente el CIF <strong className="text-white underline">{company.cif}</strong>:
              </p>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={confirmCifInput}
                  onChange={(e) => setConfirmCifInput(e.target.value)}
                  placeholder={`Teclea ${company.cif}`}
                  className="flex-1 px-3 py-1.5 bg-slate-900 border border-rose-700 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-rose-500 uppercase"
                />
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={deleting || confirmCifInput.trim().toUpperCase() !== company.cif.toUpperCase()}
                  className="px-3.5 py-1.5 font-bold rounded-lg bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white transition text-xs shrink-0"
                >
                  {deleting ? 'Borrando...' : 'Confirmar Borrado'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowDeleteConfirm(false);
                    setConfirmCifInput('');
                  }}
                  className="px-2 py-1 text-slate-400 hover:text-white text-xs"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

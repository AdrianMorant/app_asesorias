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
  Cpu,
  Layers,
  FileSpreadsheet,
  Mail,
  Phone,
  MapPin,
  ShieldCheck,
  Zap,
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
  const [activeTab, setActiveTab] = useState<'modalidad' | 'general' | 'contable' | 'peligro'>('modalidad');

  // Estados del formulario
  const [razonSocial, setRazonSocial] = useState('');
  const [planLongitud, setPlanLongitud] = useState(9);
  const [storageBasePath, setStorageBasePath] = useState('storage');
  const [ivaPeriodicity, setIvaPeriodicity] = useState<'Trimestral' | 'Mensual' | 'Anual'>('Trimestral');
  const [modalidadUso, setModalidadUso] = useState<'erp_completo' | 'copiloto_contable'>('copiloto_contable');
  const [regimenTributario, setRegimenTributario] = useState('general');
  const [softwareDestino, setSoftwareDestino] = useState('a3');
  const [domicilioFiscal, setDomicilioFiscal] = useState('');
  const [emailContacto, setEmailContacto] = useState('');
  const [telefonoContacto, setTelefonoContacto] = useState('');
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
      setModalidadUso(company.modalidad_uso || 'copiloto_contable');
      setRegimenTributario(company.regimen_tributario || 'general');
      setSoftwareDestino(company.software_destino || 'a3');
      setDomicilioFiscal(company.domicilio_fiscal || '');
      setEmailContacto(company.email_contacto || '');
      setTelefonoContacto(company.telefono_contacto || '');
      setShowDeleteConfirm(false);
      setConfirmCifInput('');
      setActiveTab('modalidad');
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
        modalidad_uso: modalidadUso,
        regimen_tributario: regimenTributario,
        software_destino: softwareDestino,
        domicilio_fiscal: domicilioFiscal.trim() || null,
        email_contacto: emailContacto.trim() || null,
        telefono_contacto: telefonoContacto.trim() || null,
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
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Cabecera */}
        <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-white">{company.razon_social}</h2>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                  modalidadUso === 'erp_completo'
                    ? 'bg-purple-500/10 text-purple-400 border-purple-500/30'
                    : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
                }`}>
                  {modalidadUso === 'erp_completo' ? 'MODALIDAD A: ERP' : 'MODALIDAD B: COPILOTO'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">CIF: {company.cif} • ID: {company.id.substring(0, 8)}...</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Pestañas de Navegación */}
        <div className="flex border-b border-slate-800 bg-slate-950/60 px-6 pt-2 shrink-0 gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('modalidad')}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition flex items-center gap-1.5 ${
              activeTab === 'modalidad'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            Modalidad & Régimen
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('general')}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition flex items-center gap-1.5 ${
              activeTab === 'general'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            Datos Fiscales
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('contable')}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition flex items-center gap-1.5 ${
              activeTab === 'contable'
                ? 'border-cyan-500 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <FolderTree className="w-3.5 h-3.5" />
            Plan & Archivado
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('peligro')}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition flex items-center gap-1.5 ml-auto ${
              activeTab === 'peligro'
                ? 'border-rose-500 text-rose-400'
                : 'border-transparent text-rose-400/70 hover:text-rose-300'
            }`}
          >
            <Trash2 className="w-3.5 h-3.5" />
            Eliminar
          </button>
        </div>

        {/* Contenido scrolleable */}
        <div className="overflow-y-auto flex-1 p-6 text-xs">
          {activeTab === 'modalidad' && (
            <div className="space-y-5 animate-in fade-in">
              <div>
                <label className="block text-xs font-bold text-slate-200 mb-2">
                  Modalidad de Uso de la Empresa
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <div
                    onClick={() => setModalidadUso('copiloto_contable')}
                    className={`cursor-pointer p-4 rounded-xl border transition-all ${
                      modalidadUso === 'copiloto_contable'
                        ? 'bg-cyan-950/40 border-cyan-500 text-white shadow-lg shadow-cyan-950/50'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2 font-bold text-xs text-cyan-400">
                        <Cpu className="w-4 h-4" />
                        MODALIDAD B: COPILOTO
                      </div>
                      <input
                        type="radio"
                        checked={modalidadUso === 'copiloto_contable'}
                        onChange={() => setModalidadUso('copiloto_contable')}
                        className="accent-cyan-500"
                      />
                    </div>
                    <p className="text-[11px] text-slate-300 leading-relaxed">
                      La asesoría usa su software contable habitual (A3, Contasol, Sage). KontaAI automatiza la recepción, extracción con IA, validación semafórica y exporta asientos listos para importar.
                    </p>
                  </div>

                  <div
                    onClick={() => setModalidadUso('erp_completo')}
                    className={`cursor-pointer p-4 rounded-xl border transition-all ${
                      modalidadUso === 'erp_completo'
                        ? 'bg-purple-950/40 border-purple-500 text-white shadow-lg shadow-purple-950/50'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2 font-bold text-xs text-purple-400">
                        <Layers className="w-4 h-4" />
                        MODALIDAD A: ERP COMPLETO
                      </div>
                      <input
                        type="radio"
                        checked={modalidadUso === 'erp_completo'}
                        onChange={() => setModalidadUso('erp_completo')}
                        className="accent-purple-500"
                      />
                    </div>
                    <p className="text-[11px] text-slate-300 leading-relaxed">
                      La empresa gestiona todo en la plataforma: emisión de facturas (Veri*factu), Libro Diario, Balances, impuestos trimestrales, tesorería y gastos con IA sin necesidad de software externo.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                    Software Contable de Destino (Enlace)
                  </label>
                  <select
                    value={softwareDestino}
                    onChange={(e) => setSoftwareDestino(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-200 focus:outline-none focus:border-cyan-500 text-xs"
                  >
                    <option value="a3">Wolters Kluwer A3 (a3asesor Eco / Con - SUENLACE.DAT)</option>
                    <option value="contasol">Software DELSOL Contasol (CSV de Diario)</option>
                    <option value="sage">Sage 50 / Sage Despachos Connected</option>
                    <option value="holded">Holded (CSV / Enlace API)</option>
                    <option value="anfix">Anfix</option>
                    <option value="cegid">Cegid / Diez Software</option>
                    <option value="otro">Otro software compatible</option>
                  </select>
                  <p className="text-[10px] text-slate-500 mt-1">
                    Determina la plantilla de exportación y reglas de asiento.
                  </p>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                    Régimen Tributario
                  </label>
                  <select
                    value={regimenTributario}
                    onChange={(e) => setRegimenTributario(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-200 focus:outline-none focus:border-cyan-500 text-xs"
                  >
                    <option value="general">Régimen General de IVA (Ordinario)</option>
                    <option value="simplificado">Régimen Simplificado (Módulos)</option>
                    <option value="recargo_equivalencia">Comercio Minorista (Recargo de Equivalencia)</option>
                    <option value="exento">Actividades Exentas (Sanitarias, Docencia)</option>
                  </select>
                  <p className="text-[10px] text-slate-500 mt-1">
                    Aplica reglas fiscales y casuísticas de IVA en la validación.
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'general' && (
            <div className="space-y-4 animate-in fade-in">
              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                  Razón Social / Nombre Oficial
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
                    CIF / NIF (Identificador Fiscal)
                  </label>
                  <input
                    type="text"
                    disabled
                    value={company.cif}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-800 rounded-xl text-slate-400 font-mono text-xs cursor-not-allowed"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1 flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                    Domicilio Fiscal
                  </label>
                  <input
                    type="text"
                    value={domicilioFiscal}
                    onChange={(e) => setDomicilioFiscal(e.target.value)}
                    placeholder="Calle, Número, CP, Ciudad"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1 flex items-center gap-1">
                    <Mail className="w-3.5 h-3.5 text-cyan-400" />
                    Email de Contacto / Notificaciones
                  </label>
                  <input
                    type="email"
                    value={emailContacto}
                    onChange={(e) => setEmailContacto(e.target.value)}
                    placeholder="administracion@empresa.es"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1 flex items-center gap-1">
                    <Phone className="w-3.5 h-3.5 text-cyan-400" />
                    Teléfono de Contacto
                  </label>
                  <input
                    type="tel"
                    value={telefonoContacto}
                    onChange={(e) => setTelefonoContacto(e.target.value)}
                    placeholder="+34 912 345 678"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'contable' && (
            <div className="space-y-4 animate-in fade-in">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                    Longitud de Subcuentas (Plan Contable)
                  </label>
                  <select
                    value={planLongitud}
                    onChange={(e) => setPlanLongitud(Number(e.target.value))}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-200 focus:outline-none focus:border-cyan-500 text-xs"
                  >
                    <option value={8}>8 dígitos</option>
                    <option value={9}>9 dígitos (Estándar PYMES)</option>
                    <option value={10}>10 dígitos</option>
                  </select>
                  <p className="text-[10px] text-slate-500 mt-1">
                    Debe coincidir exactamente con la configuración de su software contable de destino.
                  </p>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                    Periodicidad de Liquidación de IVA
                  </label>
                  <select
                    value={ivaPeriodicity}
                    onChange={(e) => setIvaPeriodicity(e.target.value as any)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-200 focus:outline-none focus:border-cyan-500 text-xs"
                  >
                    <option value="Trimestral">Trimestral (T1, T2, T3, T4 - Modelo 303)</option>
                    <option value="Mensual">Mensual (01..12 - REDEME / Grandes empresas)</option>
                    <option value="Anual">Anual</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                  <FolderTree className="w-3.5 h-3.5 text-cyan-400" />
                  Ruta Base de Archivado (Disco o Red Local)
                </label>
                <input
                  type="text"
                  value={storageBasePath}
                  onChange={(e) => setStorageBasePath(e.target.value)}
                  placeholder="storage o \\servidor\contabilidad\facturas"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white font-mono text-xs focus:outline-none focus:border-cyan-500"
                />
                <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 mt-2 space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Estructura Automática Generada:</span>
                  <p className="text-[11px] text-cyan-300 font-mono break-all">
                    {storageBasePath}/{company.cif}/[año]/{ivaPeriodicity === 'Mensual' ? '[01_Enero..12_Diciembre]' : (ivaPeriodicity === 'Anual' ? '[Anual]' : '[T1..T4]')}/recibidas/
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'peligro' && (
            <div className="space-y-4 animate-in fade-in">
              <div className="p-4 bg-rose-950/20 border border-rose-900/40 rounded-xl space-y-3">
                <div className="flex items-center gap-2 text-rose-400 font-bold">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>Zona de Peligro: Eliminación de Empresa</span>
                </div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Esta acción elimina en cascada todos los proveedores, catálogo contable, facturas y <strong className="text-rose-300">borra físicamente los archivos del disco</strong> para evitar archivos huérfanos. No se puede deshacer.
                </p>

                {!showDeleteConfirm ? (
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirm(true)}
                    className="flex items-center gap-1.5 px-3 py-2 font-semibold rounded-xl bg-rose-600/15 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 transition"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Proceder a Eliminar Empresa Definitivamente
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
          )}
        </div>

        {/* Pie de Acciones */}
        <div className="px-6 py-4 bg-slate-950 border-t border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-slate-500 text-[11px]">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Aislamiento multi-empresa verificado en servidor</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 font-medium text-slate-400 hover:text-white transition"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleUpdate}
              disabled={saving}
              className="flex items-center gap-1.5 px-4 py-2 font-semibold rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white transition shadow shadow-cyan-950 disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              {saving ? 'Guardando...' : 'Guardar Cambios'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

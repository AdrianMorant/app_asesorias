'use client';

import React, { useState, useEffect } from 'react';
import { Invoice, Supplier, AccountingEntryLine } from '@/types';
import { TrafficLightBadge } from './TrafficLightBadge';
import { ArchiveConfirmationModal } from './ArchiveConfirmationModal';
import { fetchNextSubaccount } from '@/lib/api';
import {
  Building2,
  Calendar,
  DollarSign,
  AlertCircle,
  CheckCircle,
  Save,
  Archive,
  Layers,
  HelpCircle,
  PlusCircle,
  FileCheck2,
  Trash2,
  X,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  Scissors,
  ShieldAlert,
  Percent,
  Coins,
  FileText,
  FileMinus,
  RefreshCw,
  MapPin,
  Globe,
} from 'lucide-react';

interface Props {
  invoice: Invoice;
  companyCif?: string;
  companyPlanLongitud?: number;
  suppliers: Supplier[];
  onSave: (updatedData: any) => Promise<void>;
  onApprove: (
    invoiceId: string,
    customDest?: { custom_subfolder?: string; custom_filename?: string }
  ) => Promise<void>;
  onDelete?: (invoice: Invoice) => void;
  onCreateSupplier?: (supplierData: {
    cif: string;
    nombre: string;
    subcuenta_proveedor: string;
    subcuenta_gasto_defecto: string;
  }) => Promise<void>;
  onOpenSplitter?: (invoice: Invoice) => void;
}

export const TriageForm: React.FC<Props> = ({
  invoice,
  companyCif = '',
  companyPlanLongitud = 9,
  suppliers,
  onSave,
  onApprove,
  onDelete,
  onCreateSupplier,
  onOpenSplitter,
}) => {
  // Estado local para los campos editables
  const [issuerName, setIssuerName] = useState(invoice.issuer_name || '');
  const [issuerCif, setIssuerCif] = useState(invoice.issuer_cif || '');
  const [invoiceNumber, setInvoiceNumber] = useState(invoice.invoice_number || '');
  const [issueDate, setIssueDate] = useState(invoice.issue_date || '');
  const [dueDate, setDueDate] = useState(invoice.due_date || '');
  const [fechaContable, setFechaContable] = useState(invoice.fecha_contable || invoice.issue_date || '');
  const [totalBase, setTotalBase] = useState<number>(invoice.total_base || 0);
  const [totalTax, setTotalTax] = useState<number>(invoice.total_tax || 0);
  const [totalRetention, setTotalRetention] = useState<number>(invoice.total_retention || 0);
  const [totalAmount, setTotalAmount] = useState<number>(invoice.total_amount || 0);
  const [conceptSummary, setConceptSummary] = useState(invoice.concept_summary || '');
  const [selectedSupplierId, setSelectedSupplierId] = useState<string>(invoice.supplier_id || '');

  // 1. CASUÍSTICA: PROVEEDOR NUEVO (Subcuenta correlativa vs genérica)
  const [isNewSupplier, setIsNewSupplier] = useState<boolean>(!invoice.supplier_id);
  const [assignedSubaccount, setAssignedSubaccount] = useState<string>(
    invoice.accounting_entries?.find(e => e.subcuenta.startsWith('400') || e.subcuenta.startsWith('410'))?.subcuenta ||
    '410'.padEnd(companyPlanLongitud, '0')
  );
  const [loadingSubaccount, setLoadingSubaccount] = useState(false);

  // 2. CASUÍSTICA: RETENCIÓN IRPF (Modelo 111 / 190 o 115 / 180)
  const [hasRetention, setHasRetention] = useState<boolean>(
    Boolean(invoice.has_retention || (invoice.total_retention && invoice.total_retention > 0))
  );
  const [retentionPercentage, setRetentionPercentage] = useState<number>(
    invoice.retention_percentage || (invoice.total_retention && invoice.total_base ? Number(((invoice.total_retention / invoice.total_base) * 100).toFixed(0)) : 15)
  );
  const [retentionModel, setRetentionModel] = useState<string>(
    invoice.retention_model || '111/190'
  );

  // 3. CASUÍSTICA: SUPLIDOS (Provisión y suplidos cuenta 554)
  const [hasSuplidos, setHasSuplidos] = useState<boolean>(Boolean(invoice.has_suplidos));
  const [suplidosAmount, setSuplidosAmount] = useState<number>(invoice.suplidos_amount || 0);
  const [suplidosAccount, setSuplidosAccount] = useState<string>(
    invoice.suplidos_account || '554'.padEnd(companyPlanLongitud, '0')
  );

  // 4. CASUÍSTICA: FACTURA RECTIFICATIVA (Abono)
  const [isRectificativa, setIsRectificativa] = useState<boolean>(Boolean(invoice.is_rectificativa));
  const [rectifiedInvoiceNumber, setRectifiedInvoiceNumber] = useState<string>(
    invoice.rectified_invoice_number || ''
  );
  const [rectifiedInvoiceDate, setRectifiedInvoiceDate] = useState<string>(
    invoice.rectified_invoice_date || ''
  );

  // 5. CAMPOS CENSALES: Código Postal y País para Modelo 347
  const [postalCode, setPostalCode] = useState<string>(invoice.postal_code || '');
  const [countryCode, setCountryCode] = useState<string>(invoice.country_code || 'ES');

  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Modal para confirmar la ruta de archivado
  const [showArchiveModal, setShowArchiveModal] = useState(false);

  // Modal para alta asistida de proveedor con cuentas PGC
  const [showAddSupplierModal, setShowAddSupplierModal] = useState(false);
  const [newProvAccount, setNewProvAccount] = useState('400' + '0'.repeat(Math.max(0, companyPlanLongitud - 4)) + '1');
  const [newGastoAccount, setNewGastoAccount] = useState('628'.padEnd(companyPlanLongitud, '0'));
  const [addingSupplier, setAddingSupplier] = useState(false);

  // Opciones de cuentas de gasto PGC Grupo 6 adaptadas a los dígitos de la empresa
  const pgcGastoOptions = [
    { base: '628', desc: 'Suministros (electricidad, agua, gas, telefonía, internet)' },
    { base: '629', desc: 'Otros servicios (software, material de oficina, viajes)' },
    { base: '623', desc: 'Servicios de profesionales independientes (abogados, asesores, notaría)' },
    { base: '621', desc: 'Arrendamientos y cánones (alquiler de oficinas y naves)' },
    { base: '622', desc: 'Reparaciones y conservación' },
    { base: '600', desc: 'Compras de mercaderías' },
    { base: '602', desc: 'Compras de otros aprovisionamientos' },
    { base: '607', desc: 'Trabajos realizados por otras empresas (subcontratación)' },
    { base: '624', desc: 'Transportes y envíos' },
    { base: '625', desc: 'Primas de seguros' },
    { base: '626', desc: 'Servicios bancarios y comisiones similares' },
    { base: '627', desc: 'Publicidad, propaganda y relaciones públicas' },
    { base: '640', desc: 'Sueldos y salarios del personal' },
  ].map((opt) => ({
    codigo: opt.base.padEnd(companyPlanLongitud, '0'),
    label: `${opt.base.padEnd(companyPlanLongitud, '0')} - ${opt.desc}`,
  }));

  const handleOpenAddSupplier = () => {
    setNewProvAccount(assignedSubaccount || ('400' + '0'.repeat(Math.max(0, companyPlanLongitud - 4)) + '1'));
    setNewGastoAccount('628'.padEnd(companyPlanLongitud, '0'));
    setShowAddSupplierModal(true);
  };

  const handleConfirmAddSupplier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!onCreateSupplier) return;
    setAddingSupplier(true);
    try {
      await onCreateSupplier({
        cif: issuerCif.trim(),
        nombre: issuerName.trim(),
        subcuenta_proveedor: newProvAccount.trim(),
        subcuenta_gasto_defecto: newGastoAccount.trim(),
      });
      setShowAddSupplierModal(false);
      setMessage({
        type: 'success',
        text: `Proveedor registrado: Subcuenta ${newProvAccount} / Gasto PGC ${newGastoAccount}.`
      });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Error al dar de alta proveedor.' });
    } finally {
      setAddingSupplier(false);
    }
  };

  // Sincronizar si cambia la factura seleccionada
  useEffect(() => {
    setIssuerName(invoice.issuer_name || '');
    setIssuerCif(invoice.issuer_cif || '');
    setInvoiceNumber(invoice.invoice_number || '');
    setIssueDate(invoice.issue_date || '');
    setDueDate(invoice.due_date || '');
    setFechaContable(invoice.fecha_contable || invoice.issue_date || '');
    setTotalBase(invoice.total_base || 0);
    setTotalTax(invoice.total_tax || 0);
    setTotalRetention(invoice.total_retention || 0);
    setTotalAmount(invoice.total_amount || 0);
    setConceptSummary(invoice.concept_summary || '');
    setSelectedSupplierId(invoice.supplier_id || '');

    // Sincronizar casuísticas fiscales
    setIsNewSupplier(!invoice.supplier_id);
    const existingEntrySub = invoice.accounting_entries?.find(
      e => e.subcuenta.startsWith('400') || e.subcuenta.startsWith('410')
    )?.subcuenta;
    setAssignedSubaccount(existingEntrySub || '410'.padEnd(companyPlanLongitud, '0'));

    setHasRetention(Boolean(invoice.has_retention || (invoice.total_retention && invoice.total_retention > 0)));
    setRetentionPercentage(
      invoice.retention_percentage || (invoice.total_retention && invoice.total_base ? Number(((invoice.total_retention / invoice.total_base) * 100).toFixed(0)) : 15)
    );
    setRetentionModel(invoice.retention_model || '111/190');

    setHasSuplidos(Boolean(invoice.has_suplidos));
    setSuplidosAmount(invoice.suplidos_amount || 0);
    setSuplidosAccount(invoice.suplidos_account || '554'.padEnd(companyPlanLongitud, '0'));

    setIsRectificativa(Boolean(invoice.is_rectificativa));
    setRectifiedInvoiceNumber(invoice.rectified_invoice_number || '');
    setRectifiedInvoiceDate(invoice.rectified_invoice_date || '');

    setPostalCode(invoice.postal_code || '');
    setCountryCode(invoice.country_code || 'ES');

    setMessage(null);
  }, [invoice, companyPlanLongitud]);

  // Manejador interactivo: Checkbox "Proveedor Nuevo"
  const handleToggleNewSupplier = async (checked: boolean) => {
    setIsNewSupplier(checked);
    if (checked) {
      // Consultar al backend para calcular y reservar la siguiente subcuenta libre correlativa
      setLoadingSubaccount(true);
      try {
        const res = await fetchNextSubaccount(invoice.company_id, '410');
        setAssignedSubaccount(res.next_subaccount);
        setMessage({
          type: 'success',
          text: `Siguiente subcuenta libre correlativa reservada: ${res.next_subaccount} (Acreedores/Proveedores).`
        });
      } catch (err: any) {
        // Fallback local si la llamada fallara
        const fallbackSub = '410' + '0'.repeat(Math.max(0, companyPlanLongitud - 4)) + '1';
        setAssignedSubaccount(fallbackSub);
        setMessage({
          type: 'error',
          text: `No se pudo consultar el backend. Se asignó correlativa estimada: ${fallbackSub}`
        });
      } finally {
        setLoadingSubaccount(false);
      }
    } else {
      // Vuelve a la subcuenta genérica configurada
      const genericSub = '410'.padEnd(companyPlanLongitud, '0');
      setAssignedSubaccount(genericSub);
      setMessage({
        type: 'success',
        text: `Revertido a subcuenta genérica: ${genericSub}`
      });
    }
  };

  // Manejador interactivo: Checkbox "Retención IRPF"
  const handleToggleRetention = (checked: boolean) => {
    setHasRetention(checked);
    if (checked) {
      if (totalRetention === 0 && totalBase > 0) {
        const calculatedRet = Number((totalBase * (retentionPercentage / 100)).toFixed(2));
        setTotalRetention(calculatedRet);
      }
    } else {
      setTotalRetention(0);
    }
  };

  // Manejador de cambio de porcentaje de retención
  const handleRetentionPercentageChange = (pct: number) => {
    setRetentionPercentage(pct);
    if (hasRetention && totalBase > 0) {
      const calculatedRet = Number((totalBase * (pct / 100)).toFixed(2));
      setTotalRetention(calculatedRet);
    }
  };

  // Manejador interactivo: Checkbox "Suplidos"
  const handleToggleSuplidos = (checked: boolean) => {
    setHasSuplidos(checked);
    if (checked) {
      if (!suplidosAccount) {
        setSuplidosAccount('554'.padEnd(companyPlanLongitud, '0'));
      }
    } else {
      setSuplidosAmount(0);
    }
  };

  // Manejador interactivo: Checkbox "Factura Rectificativa"
  const handleToggleRectificativa = (checked: boolean) => {
    setIsRectificativa(checked);
    if (!checked) {
      setRectifiedInvoiceNumber('');
      setRectifiedInvoiceDate('');
    }
  };

  // Cuadre aritmético en vivo considerando retención y suplidos
  const calculatedTotal = Number(
    (totalBase + totalTax - (hasRetention ? totalRetention : 0) + (hasSuplidos ? suplidosAmount : 0)).toFixed(2)
  );
  const arithmeticDiff = Number(Math.abs(calculatedTotal - totalAmount).toFixed(2));
  const isArithmeticBalanced = arithmeticDiff <= 0.01;

  // Detección de duplicado
  const isDuplicateDetected = Boolean(
    invoice.is_duplicate ||
    invoice.duplicate_of_id ||
    invoice.status_reasons?.some((r) => r.toLowerCase().includes('duplicad'))
  );

  // Manejar guardado
  const handleSave = async () => {
    if (isRectificativa) {
      if (!rectifiedInvoiceNumber.trim() || !rectifiedInvoiceDate) {
        setMessage({
          type: 'error',
          text: 'En facturas rectificativas es obligatorio indicar el Número y la Fecha de la factura original (RD 1619/2012).'
        });
        return;
      }
    }

    setSaving(true);
    setMessage(null);
    try {
      await onSave({
        issuer_name: issuerName,
        issuer_cif: issuerCif,
        invoice_number: invoiceNumber,
        issue_date: issueDate,
        due_date: dueDate || null,
        fecha_contable: fechaContable || issueDate,
        total_base: Number(totalBase),
        total_tax: Number(totalTax),
        total_retention: hasRetention ? Number(totalRetention) : 0,
        total_amount: Number(totalAmount),
        concept_summary: conceptSummary,
        supplier_id: selectedSupplierId || null,
        // Casuísticas fiscales FASE 2
        is_rectificativa: isRectificativa,
        rectified_invoice_number: isRectificativa ? rectifiedInvoiceNumber.trim() : null,
        rectified_invoice_date: isRectificativa ? rectifiedInvoiceDate : null,
        has_retention: hasRetention,
        retention_percentage: hasRetention ? Number(retentionPercentage) : 0,
        retention_model: hasRetention ? retentionModel : '111/190',
        has_suplidos: hasSuplidos,
        suplidos_amount: hasSuplidos ? Number(suplidosAmount) : 0,
        suplidos_account: hasSuplidos ? suplidosAccount.trim() : null,
        postal_code: postalCode.trim() || null,
        country_code: countryCode.trim() || 'ES',
      });
      setMessage({ type: 'success', text: 'Datos guardados, casuísticas fiscales aplicadas y asiento recalculado.' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Error al guardar cambios.' });
    } finally {
      setSaving(false);
    }
  };

  // Manejar click en "Aprobar y Archivar" (Abre selección visual de carpeta de destino)
  const handleApproveClick = () => {
    setShowArchiveModal(true);
  };

  // Ejecución directa de aprobación
  const executeApprove = async (customDest?: {
    custom_subfolder?: string;
    custom_filename?: string;
  }) => {
    setApproving(true);
    setMessage(null);
    try {
      await onApprove(invoice.id, customDest);
      setMessage({ type: 'success', text: '¡Factura aprobada y archivada con éxito!' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Error al aprobar y archivar.' });
    } finally {
      setApproving(false);
    }
  };

  // Alta rápida de proveedor si no existe
  const handleQuickAddSupplier = async () => {
    if (!onCreateSupplier) return;
    try {
      await onCreateSupplier({
        cif: issuerCif,
        nombre: issuerName,
        subcuenta_proveedor: '400000001',
        subcuenta_gasto_defecto: '629000001',
      });
      setMessage({ type: 'success', text: 'Proveedor registrado en el maestro contable.' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Error al dar de alta proveedor.' });
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900/60 rounded-xl border border-slate-800 overflow-hidden shadow-2xl">
      {/* Cabecera del panel de triaje */}
      <div className="px-6 py-4 bg-slate-900/90 border-b border-slate-800 backdrop-blur-md">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-bold text-white tracking-tight">
                {invoiceNumber || 'Factura Sin Número'}
              </h2>
              <TrafficLightBadge
                status={invoice.status}
                reasonsCount={invoice.status_reasons?.length}
                size="md"
                esMultifactura={invoice.es_multifactura}
              />
              {/* Badge de Nivel de Confianza IA */}
              {invoice.status === 'GREEN' ? (
                <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 font-medium">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                  Certeza IA: 98%
                </span>
              ) : invoice.status === 'YELLOW' ? (
                <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/25 font-medium">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  Certeza IA: 82%
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-0.5 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/25 font-medium animate-pulse">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                  Atención requerida
                </span>
              )}
              {invoice.is_processed && (
                <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <FileCheck2 className="w-3.5 h-3.5" />
                  Archivada / Contabilizada
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Emisor: <span className="text-slate-200 font-medium">{issuerName || 'Desconocido'}</span> ({issuerCif || 'Sin CIF'})
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* Botón Maquetador de Corte si es multifactura */}
            {invoice.es_multifactura && onOpenSplitter && (
              <button
                type="button"
                onClick={() => onOpenSplitter(invoice)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-purple-600/25 hover:bg-purple-600/40 text-purple-200 border border-purple-500/50 shadow-md transition cursor-pointer"
                title="Abrir Maquetador Visual de Corte (Multi-Factura)"
              >
                <Scissors className="w-3.5 h-3.5 text-purple-300" />
                Maquetador de Corte (MF)
              </button>
            )}
            {/* Botón de papelera en triaje */}
            {onDelete && (
              <button
                type="button"
                onClick={() => onDelete(invoice)}
                className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition border border-transparent hover:border-rose-500/20"
                title="Eliminar factura y fichero"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}

            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition shadow"
            >
              <Save className="w-3.5 h-3.5" />
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
            <button
              type="button"
              onClick={handleApproveClick}
              disabled={approving || invoice.is_processed || invoice.status === 'RED' || isDuplicateDetected}
              title={
                isDuplicateDetected
                  ? 'Bloqueo de seguridad: Esta factura es un duplicado detectado y no puede ser aprobada ni contabilizada.'
                  : invoice.status === 'RED'
                  ? 'Bloqueo de seguridad: No se puede aprobar una factura en Semáforo Rojo con anomalías graves.'
                  : invoice.is_processed
                  ? 'Factura ya aprobada'
                  : 'Aprobar factura y dar de alta asistida en el Plan Contable'
              }
              className={`flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition shadow ${
                isDuplicateDetected || invoice.status === 'RED'
                  ? 'bg-rose-950/40 text-rose-400/60 border border-rose-900/40 cursor-not-allowed'
                  : invoice.is_processed
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-850'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/40'
              }`}
            >
              <Archive className="w-3.5 h-3.5" />
              {approving
                ? 'Archivando...'
                : invoice.is_processed
                ? 'Aprobada'
                : isDuplicateDetected
                ? 'Duplicado Bloqueado'
                : invoice.status === 'RED'
                ? 'Bloqueada (Rojo)'
                : 'Aprobar y Archivar'}
            </button>
          </div>
        </div>

        {/* EXPLICACIÓN CONTEXTUAL DE LA IA (Fase B) */}
        <div
          className={`mt-3 p-3 rounded-xl border text-xs shadow-sm flex items-start gap-3 transition-all ${
            invoice.status === 'GREEN'
              ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-200'
              : invoice.status === 'YELLOW'
              ? 'bg-amber-950/40 border-amber-500/30 text-amber-200'
              : 'bg-rose-950/50 border-rose-500/30 text-rose-200'
          }`}
        >
          <div
            className={`p-2 rounded-lg shrink-0 mt-0.5 ${
              invoice.status === 'GREEN'
                ? 'bg-emerald-500/20 text-emerald-400'
                : invoice.status === 'YELLOW'
                ? 'bg-amber-500/20 text-amber-400'
                : 'bg-rose-500/20 text-rose-400'
            }`}
          >
            <Sparkles className="w-4 h-4" />
          </div>
          <div className="space-y-1 flex-1">
            <div className="font-bold flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5">
                Diagnóstico Contextual de Konta IA
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-black/40 border border-white/10 opacity-90">
                {invoice.status === 'GREEN'
                  ? 'Certeza: 98%'
                  : invoice.status === 'YELLOW'
                  ? 'Certeza: 82%'
                  : 'Atención Requerida'}
              </span>
            </div>
            <p className="text-[11px] leading-relaxed opacity-95">
              {invoice.status === 'YELLOW' ? (
                <>
                  💡 <strong>Proveedor nuevo detectado:</strong> He detectado que es un proveedor nuevo y he reservado la subcuenta{' '}
                  <strong className="underline font-mono text-white">{assignedSubaccount}</strong>. Al pulsar <em>Aprobar</em>, el sistema creará la ficha sin que tengas que teclearla.
                  {hasRetention && (
                    <>
                      <br />
                      ⚠️ <strong>Retención profesional ({retentionPercentage}%):</strong> Confirma si aplica a este profesional para su cómputo automático en el Modelo 111 de la AEAT.
                    </>
                  )}
                </>
              ) : invoice.status === 'RED' ? (
                <>
                  🚨 <strong>Atención requerida:</strong>{' '}
                  {invoice.status_reasons && invoice.status_reasons.length > 0
                    ? invoice.status_reasons.join('. ')
                    : 'Descuadre aritmético entre bases, cuotas o CIF emisor.'}{' '}
                  Corrige los importes señalados en rojo antes de aprobar la factura.
                </>
              ) : (
                <>
                  ✨ <strong>Extracción limpia y 100% coherente:</strong> CIF verificado con el algoritmo oficial de la AEAT, bases imponibles y cuotas de IVA cuadradas al céntimo. El asiento contable en partida doble está generado y listo para sincronizar.
                </>
              )}
            </p>
          </div>
        </div>

        {/* Notificación de feedback */}
        {message && (
          <div
            className={`mt-3 p-2.5 rounded-lg text-xs flex items-center gap-2 ${
              message.type === 'success'
                ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
            }`}
          >
            {message.type === 'success' ? (
              <CheckCircle className="w-4 h-4 shrink-0 text-emerald-400" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            )}
            <span>{message.text}</span>
          </div>
        )}

        {/* BANNER ROJO CRÍTICO: FACTURA DUPLICADA DETECTADA CON BOTÓN DE ELIMINACIÓN */}
        {isDuplicateDetected && (
          <div className="mt-3 p-4 rounded-xl text-xs bg-rose-950/90 border-2 border-rose-500 text-rose-100 shadow-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-in fade-in duration-200">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-lg bg-rose-900 text-rose-200 border border-rose-700 shrink-0">
                <ShieldAlert className="w-5 h-5 text-rose-300 animate-pulse" />
              </div>
              <div>
                <div className="font-bold text-rose-200 text-sm flex items-center gap-2">
                  <span>⚠️ ALERTA: Factura Duplicada Detectada</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] bg-rose-900 border border-rose-700 font-mono text-rose-300">
                    BLOQUEO FISCAL
                  </span>
                </div>
                <p className="text-[11px] text-rose-300/90 mt-1">
                  Esta factura ya existe en el sistema con el mismo CIF emisor (<strong className="text-white">{issuerCif || invoice.issuer_cif}</strong>),
                  número (<strong className="text-white">{invoiceNumber || invoice.invoice_number}</strong>) y fecha (<strong className="text-white">{issueDate || invoice.issue_date}</strong>).
                  Se bloquea la validación para prevenir duplicidades contables ante la Agencia Tributaria.
                </p>
              </div>
            </div>
            {onDelete && (
              <button
                type="button"
                onClick={() => {
                  if (confirm(`¿Deseas eliminar permanentemente esta factura duplicada (${invoiceNumber || 'sin número'})?`)) {
                    onDelete(invoice);
                  }
                }}
                className="shrink-0 flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold rounded-lg bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-950/60 transition cursor-pointer"
                title="Eliminar este duplicado inmediatamente"
              >
                <Trash2 className="w-4 h-4" />
                <span>Eliminar Duplicado</span>
              </button>
            )}
          </div>
        )}

        {/* BANNER INFORMATIVO: FECHA CONTABLE TRASLADADA POR CIERRE CONTABLE */}
        {invoice.fecha_contable && invoice.fecha_contable !== invoice.issue_date && (
          <div className="mt-3 p-3 rounded-xl text-xs bg-cyan-950/40 border border-cyan-800/60 text-cyan-200 flex items-center gap-2.5">
            <Calendar className="w-4 h-4 text-cyan-400 shrink-0" />
            <div>
              <span className="font-semibold text-cyan-300">Bloqueo por Cierre Contable: </span>
              <span>La fecha de emisión ({invoice.issue_date}) pertenece a un ejercicio cerrado. La fecha contable se ha desplazado automáticamente al primer día hábil abierto: </span>
              <strong className="text-white font-mono">{invoice.fecha_contable}</strong>.
            </div>
          </div>
        )}

        {/* BANNER MULTI-FACTURA (MF) */}
        {invoice.es_multifactura && (
          <div className="mt-3 p-3.5 rounded-xl text-xs bg-purple-950/40 border border-purple-800/60 text-purple-200 shadow-sm flex items-center justify-between gap-4">
            <div className="flex items-start gap-2.5">
              <div className="p-2 rounded-lg bg-purple-900/60 text-purple-300 border border-purple-700/50 shrink-0">
                <Scissors className="w-4 h-4" />
              </div>
              <div>
                <div className="font-bold text-purple-300 flex items-center gap-2">
                  <span>Documento Multi-Factura (MF) Detectado</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] bg-purple-500/30 text-purple-200 border border-purple-500/50">
                    {invoice.num_paginas ? `${invoice.num_paginas} páginas` : 'Multi-página'}
                  </span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/40">
                    Estado: {invoice.workflow_status || 'a_revisar'}
                  </span>
                </div>
                <p className="text-[11px] text-purple-300/80 mt-1">
                  Este archivo contiene varias facturas o páginas agrupadas. Utiliza el Maquetador Visual de Corte para separar el documento en sub-facturas independientes.
                </p>
              </div>
            </div>
            {onOpenSplitter && (
              <button
                type="button"
                onClick={() => onOpenSplitter(invoice)}
                className="shrink-0 flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold rounded-lg bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-950/50 transition cursor-pointer"
              >
                <Scissors className="w-3.5 h-3.5" />
                <span>Abrir Maquetador</span>
              </button>
            )}
          </div>
        )}

        {/* BANNER ROJO: BLOQUEO ESTRICTO POR ANOMALÍAS GRAVES */}
        {invoice.status === 'RED' && (
          <div className="mt-3 p-3.5 rounded-xl text-xs bg-rose-950/40 border border-rose-800/60 text-rose-200 shadow-sm">
            <div className="font-bold mb-1.5 flex items-center gap-2 text-rose-400">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>Bloqueo Estricto por Anomalías Graves (Semáforo Rojo)</span>
            </div>
            <p className="text-[11px] text-rose-300/80 mb-2">
              Se bloquea cualquier opción de aprobar o exportar esta factura hasta su corrección manual:
            </p>
            <ul className="list-disc list-inside space-y-1 text-rose-200 text-xs font-semibold pl-1">
              {invoice.status_reasons && invoice.status_reasons.length > 0 ? (
                invoice.status_reasons.map((r, i) => <li key={i}>{r}</li>)
              ) : (
                <li>Error detectado en cuadre aritmético, duplicidad o CIF/NIF formal ante AEAT.</li>
              )}
            </ul>
          </div>
        )}

        {/* BANNER AMARILLO: PROVEEDOR NUEVO / ASISTENCIA INTELIGENTE */}
        {invoice.status === 'YELLOW' && (
          <div className="mt-3 p-3.5 rounded-xl text-xs bg-amber-950/30 border border-amber-800/50 text-amber-200 shadow-sm">
            <div className="font-bold mb-1.5 flex items-center gap-2 text-amber-400">
              <Sparkles className="w-4 h-4 shrink-0 text-amber-400" />
              <span>Asistencia Inteligente: Proveedor Nuevo Detectado</span>
            </div>
            <p className="text-[11px] text-amber-300/90 mb-2">
              La factura cuadra matemáticamente y el CIF es válido, pero el emisor es nuevo. El sistema ha preparado automáticamente la propuesta contable según la longitud configurada ({companyPlanLongitud} dígitos):
            </p>
            <div className="flex flex-wrap gap-2 text-[11px] font-mono mb-2">
              {invoice.accounting_entries?.find(e => e.subcuenta.startsWith('400') || e.subcuenta.startsWith('410')) && (
                <span className="px-2.5 py-1 rounded-md bg-amber-900/50 border border-amber-700/60 text-amber-200">
                  Subcuenta Proveedor Propuesta: <strong>{invoice.accounting_entries.find(e => e.subcuenta.startsWith('400') || e.subcuenta.startsWith('410'))?.subcuenta}</strong>
                </span>
              )}
              {invoice.accounting_entries?.find(e => e.subcuenta.startsWith('6')) && (
                <span className="px-2.5 py-1 rounded-md bg-amber-900/50 border border-amber-700/60 text-amber-200">
                  Subcuenta Gasto Propuesta: <strong>{invoice.accounting_entries.find(e => e.subcuenta.startsWith('6'))?.subcuenta}</strong>
                </span>
              )}
            </div>
            <div className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1.5 pt-1 border-t border-amber-900/40">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              <span>Al pulsar &quot;Aprobar y Archivar&quot;, se dará de alta automáticamente en el Plan Contable PYME y en Contactos sin tener que teclear nada a mano.</span>
            </div>
          </div>
        )}

        {/* BANNER VERDE: COINCIDENCIA CONFIRMADA */}
        {invoice.status === 'GREEN' && (
          <div className="mt-3 p-3 rounded-xl text-xs bg-emerald-950/20 border border-emerald-800/40 text-emerald-200 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>Coincidencia confirmada: Factura 100% cuadrada, CIF válido ante la AEAT y cuentas mapeadas en el Plan Contable.</span>
          </div>
        )}
      </div>

      {/* Cuerpo del formulario scrollable */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* SECCIÓN 1: DATOS FISCALES DEL EMISOR Y CENSALES (MODELO 347) */}
        <div className="bg-slate-950/50 p-4 rounded-xl border border-slate-800/80">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Building2 className="w-4 h-4 text-cyan-400" />
              Emisor / Proveedor & Datos Censales (Modelo 347)
            </h3>
            {!selectedSupplierId && (
              <button
                type="button"
                onClick={handleOpenAddSupplier}
                className="text-[11px] font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
              >
                <PlusCircle className="w-3.5 h-3.5" />
                Dar de alta en maestro
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="lg:col-span-2">
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Razón Social / Nombre Comercial
              </label>
              <input
                type="text"
                value={issuerName}
                onChange={(e) => setIssuerName(e.target.value)}
                className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                NIF / CIF Español
              </label>
              <input
                type="text"
                value={issuerCif}
                onChange={(e) => setIssuerCif(e.target.value.toUpperCase())}
                className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white font-mono uppercase focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1 flex items-center gap-1">
                <MapPin className="w-3 h-3 text-cyan-400" />
                <span>Código Postal (347)</span>
              </label>
              <input
                type="text"
                maxLength={10}
                placeholder="Ej. 28001"
                value={postalCode}
                onChange={(e) => setPostalCode(e.target.value.trim())}
                className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="lg:col-span-1">
              <label className="block text-[11px] font-medium text-slate-400 mb-1 flex items-center gap-1">
                <Globe className="w-3 h-3 text-cyan-400" />
                <span>País de Residencia</span>
              </label>
              <select
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value)}
                className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="ES">ES - España</option>
                <option value="PT">PT - Portugal</option>
                <option value="FR">FR - Francia</option>
                <option value="DE">DE - Alemania</option>
                <option value="IT">IT - Italia</option>
                <option value="GB">GB - Reino Unido</option>
                <option value="US">US - Estados Unidos</option>
                <option value="OT">OT - Otro país</option>
              </select>
            </div>

            <div className="lg:col-span-3">
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Vincular con Proveedor del Maestro
              </label>
              <select
                value={selectedSupplierId}
                onChange={(e) => {
                  setSelectedSupplierId(e.target.value);
                  if (e.target.value) {
                    setIsNewSupplier(false);
                  }
                }}
                className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="">-- Proveedor no vinculado (automático / nuevo) --</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nombre} ({s.cif}) - Cta: {s.subcuenta_proveedor} / Gasto: {s.subcuenta_gasto_defecto}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 flex items-center gap-1">
            <span className="text-cyan-400 font-semibold">• Coherencia Censal AEAT:</span>
            <span>El código postal y país son requeridos para la confección del libro de compras y el Modelo 347.</span>
          </div>
        </div>

        {/* SECCIÓN 2: CASUÍSTICAS FISCALES Y CONTABLES (FASE 2) */}
        <div className="bg-slate-950/60 p-4 rounded-xl border border-cyan-500/20 shadow-md">
          <div className="flex items-center justify-between mb-3 border-b border-slate-800/80 pb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Casuísticas Fiscales y Contables
              </h3>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-mono">
              Fase 2 Reactiva
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Control 1: Proveedor Nuevo */}
            <div className={`p-3 rounded-xl border transition-all ${
              isNewSupplier ? 'bg-cyan-950/30 border-cyan-500/50' : 'bg-slate-900/40 border-slate-800'
            }`}>
              <label className="flex items-center justify-between cursor-pointer select-none mb-2">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <Building2 className="w-3.5 h-3.5 text-cyan-400" />
                  Proveedor Nuevo
                </span>
                <input
                  type="checkbox"
                  checked={isNewSupplier}
                  onChange={(e) => handleToggleNewSupplier(e.target.checked)}
                  className="w-4 h-4 text-cyan-500 rounded border-slate-700 bg-slate-950 focus:ring-cyan-500"
                />
              </label>
              <p className="text-[10px] text-slate-400 mb-2">
                {isNewSupplier
                  ? 'Reserva la siguiente subcuenta libre correlativa.'
                  : 'Aplica la subcuenta genérica configurada.'}
              </p>
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono">
                <span className="text-slate-400">Subcuenta:</span>
                <span className="text-cyan-300 font-bold flex items-center gap-1">
                  {loadingSubaccount ? (
                    <RefreshCw className="w-3 h-3 animate-spin text-cyan-400" />
                  ) : (
                    assignedSubaccount
                  )}
                </span>
              </div>
            </div>

            {/* Control 2: Retención IRPF */}
            <div className={`p-3 rounded-xl border transition-all ${
              hasRetention ? 'bg-amber-950/30 border-amber-500/50' : 'bg-slate-900/40 border-slate-800'
            }`}>
              <label className="flex items-center justify-between cursor-pointer select-none mb-2">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <Percent className="w-3.5 h-3.5 text-amber-400" />
                  Retención IRPF
                </span>
                <input
                  type="checkbox"
                  checked={hasRetention}
                  onChange={(e) => handleToggleRetention(e.target.checked)}
                  className="w-4 h-4 text-amber-500 rounded border-slate-700 bg-slate-950 focus:ring-amber-500"
                />
              </label>
              <p className="text-[10px] text-slate-400 mb-2">
                Deduce retención profesional y vincula con el modelo tributario.
              </p>
              {hasRetention ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <select
                      value={retentionPercentage}
                      onChange={(e) => handleRetentionPercentageChange(Number(e.target.value))}
                      className="w-1/2 px-2 py-1 text-[11px] bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-amber-500"
                    >
                      <option value={15}>15% (General)</option>
                      <option value={7}>7% (Nuevos)</option>
                      <option value={19}>19% (Alquiler)</option>
                      <option value={1}>1% (Módulos)</option>
                    </select>
                    <select
                      value={retentionModel}
                      onChange={(e) => setRetentionModel(e.target.value)}
                      className="w-1/2 px-2 py-1 text-[11px] bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-amber-500"
                    >
                      <option value="111/190">Mod. 111 / 190</option>
                      <option value="115/180">Mod. 115 / 180</option>
                    </select>
                  </div>
                  <div className="text-[11px] text-rose-400 font-mono font-bold text-right">
                    - {totalRetention.toFixed(2)} € (negativo en asiento)
                  </div>
                </div>
              ) : (
                <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800/80 text-[11px] text-slate-500 text-center font-mono">
                  Sin retención
                </div>
              )}
            </div>

            {/* Control 3: Suplidos */}
            <div className={`p-3 rounded-xl border transition-all ${
              hasSuplidos ? 'bg-emerald-950/30 border-emerald-500/50' : 'bg-slate-900/40 border-slate-800'
            }`}>
              <label className="flex items-center justify-between cursor-pointer select-none mb-2">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <Coins className="w-3.5 h-3.5 text-emerald-400" />
                  Suplidos
                </span>
                <input
                  type="checkbox"
                  checked={hasSuplidos}
                  onChange={(e) => handleToggleSuplidos(e.target.checked)}
                  className="w-4 h-4 text-emerald-500 rounded border-slate-700 bg-slate-950 focus:ring-emerald-500"
                />
              </label>
              <p className="text-[10px] text-slate-400 mb-2">
                Gastos por cuenta de terceros (sin IVA, Cta. 554).
              </p>
              {hasSuplidos ? (
                <div className="space-y-2">
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Importe suplidos (€)"
                    value={suplidosAmount || ''}
                    onChange={(e) => setSuplidosAmount(parseFloat(e.target.value) || 0)}
                    className="w-full px-2 py-1 text-[11px] bg-slate-950 border border-slate-800 rounded-lg text-emerald-300 font-mono focus:border-emerald-500 text-right"
                  />
                  <input
                    type="text"
                    placeholder="Cuenta PGC (554...)"
                    value={suplidosAccount}
                    onChange={(e) => setSuplidosAccount(e.target.value.trim())}
                    className="w-full px-2 py-1 text-[11px] bg-slate-950 border border-slate-800 rounded-lg text-slate-300 font-mono focus:border-emerald-500 text-right"
                  />
                </div>
              ) : (
                <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800/80 text-[11px] text-slate-500 text-center font-mono">
                  Sin suplidos
                </div>
              )}
            </div>

            {/* Control 4: Factura Rectificativa */}
            <div className={`p-3 rounded-xl border transition-all ${
              isRectificativa ? 'bg-rose-950/40 border-rose-500/60' : 'bg-slate-900/40 border-slate-800'
            }`}>
              <label className="flex items-center justify-between cursor-pointer select-none mb-2">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <FileMinus className="w-3.5 h-3.5 text-rose-400" />
                  Factura Rectificativa
                </span>
                <input
                  type="checkbox"
                  checked={isRectificativa}
                  onChange={(e) => handleToggleRectificativa(e.target.checked)}
                  className="w-4 h-4 text-rose-500 rounded border-slate-700 bg-slate-950 focus:ring-rose-500"
                />
              </label>
              <p className="text-[10px] text-slate-400 mb-2">
                Abono contable con importes con signo negativo.
              </p>
              {isRectificativa ? (
                <div className="space-y-1.5 animate-in fade-in">
                  <div>
                    <label className="block text-[9px] font-bold text-rose-300 uppercase">
                      * Nº Factura Original:
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Ej. F2025-0012"
                      value={rectifiedInvoiceNumber}
                      onChange={(e) => setRectifiedInvoiceNumber(e.target.value)}
                      className={`w-full px-2 py-1 text-[11px] bg-slate-950 border rounded-lg text-white font-mono focus:outline-none ${
                        !rectifiedInvoiceNumber.trim() ? 'border-rose-500 ring-1 ring-rose-500' : 'border-slate-800'
                      }`}
                    />
                  </div>
                  <div>
                    <label className="block text-[9px] font-bold text-rose-300 uppercase">
                      * Fecha Factura Original:
                    </label>
                    <input
                      type="date"
                      required
                      value={rectifiedInvoiceDate}
                      onChange={(e) => setRectifiedInvoiceDate(e.target.value)}
                      className={`w-full px-2 py-1 text-[11px] bg-slate-950 border rounded-lg text-white font-mono focus:outline-none ${
                        !rectifiedInvoiceDate ? 'border-rose-500 ring-1 ring-rose-500' : 'border-slate-800'
                      }`}
                    />
                  </div>
                </div>
              ) : (
                <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800/80 text-[11px] text-slate-500 text-center font-mono">
                  Factura ordinaria
                </div>
              )}
            </div>
          </div>
        </div>

        {/* SECCIÓN 3: IDENTIFICACIÓN Y FECHAS */}
        <div className="bg-slate-950/50 p-4 rounded-xl border border-slate-800/80">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Calendar className="w-4 h-4 text-cyan-400" />
              Factura y Fechas
            </h3>
            {isRectificativa && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
                Abono / Rectificativa
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Número de Factura
              </label>
              <input
                type="text"
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Fecha de Emisión
              </label>
              <input
                type="date"
                value={issueDate}
                onChange={(e) => {
                  setIssueDate(e.target.value);
                  if (!fechaContable) setFechaContable(e.target.value);
                }}
                className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1 flex items-center justify-between">
                <span>Fecha Contable</span>
                {fechaContable !== issueDate && (
                  <span className="text-[9px] text-cyan-400 font-bold">Ajustada</span>
                )}
              </label>
              <input
                type="date"
                value={fechaContable}
                onChange={(e) => setFechaContable(e.target.value)}
                className={`w-full px-3 py-1.5 text-xs bg-slate-900 border rounded-lg text-white font-mono focus:outline-none ${
                  fechaContable !== issueDate ? 'border-cyan-500 text-cyan-300' : 'border-slate-700'
                }`}
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Fecha de Vencimiento
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div className="md:col-span-4">
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Concepto / Resumen de Factura
              </label>
              <input
                type="text"
                value={conceptSummary}
                onChange={(e) => setConceptSummary(e.target.value)}
                className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        </div>

        {/* SECCIÓN 5: SIMULADOR DE ASIENTO CONTABLE EN PARTIDA DOBLE (PGC) */}
        <div className="bg-slate-950/50 p-4 rounded-xl border border-slate-800/80">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              Asiento Contable en Partida Doble (PGC)
            </h3>
            <span className="text-[11px] text-slate-400 font-mono">
              {invoice.accounting_entries?.length || 0} apuntes generados
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-[11px] text-slate-400 uppercase">
                  <th className="py-2 px-2 font-medium">Subcuenta</th>
                  <th className="py-2 px-2 font-medium">Concepto</th>
                  <th className="py-2 px-2 font-medium text-right">Debe (€)</th>
                  <th className="py-2 px-2 font-medium text-right">Haber (€)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50 font-mono text-[11px]">
                {invoice.accounting_entries?.map((entry, index) => (
                  <tr key={index} className="hover:bg-slate-900/40">
                    <td className="py-2 px-2 text-cyan-400 font-semibold">{entry.subcuenta}</td>
                    <td className="py-2 px-2 text-slate-300 font-sans truncate max-w-[200px]" title={entry.concepto}>
                      {entry.concepto}
                    </td>
                    <td className="py-2 px-2 text-right text-emerald-400">
                      {entry.debe !== 0 ? `${entry.debe.toFixed(2)} €` : '-'}
                    </td>
                    <td className="py-2 px-2 text-right text-amber-400">
                      {entry.haber !== 0 ? `${entry.haber.toFixed(2)} €` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-slate-700 font-mono font-bold text-xs bg-slate-900/60">
                  <td colSpan={2} className="py-2 px-2 text-slate-300 font-sans text-right">
                    Total Asiento:
                  </td>
                  <td className="py-2 px-2 text-right text-emerald-400">
                    {(invoice.accounting_entries?.reduce((acc, e) => acc + e.debe, 0) || 0).toFixed(2)} €
                  </td>
                  <td className="py-2 px-2 text-right text-amber-400">
                    {(invoice.accounting_entries?.reduce((acc, e) => acc + e.haber, 0) || 0).toFixed(2)} €
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>

      {/* Modal interactivo de archivado */}
      <ArchiveConfirmationModal
        isOpen={showArchiveModal}
        invoiceId={invoice.id}
        invoiceNumber={invoiceNumber}
        companyCif={companyCif}
        onClose={() => setShowArchiveModal(false)}
        onConfirm={executeApprove}
      />

      {/* Modal de Alta de Proveedor Asistida por el PGC PYMES */}
      {showAddSupplierModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150">
            <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                  <Building2 className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Alta de Proveedor en Maestro Contable</h3>
                  <p className="text-[11px] text-slate-400">Vinculación directa con el Plan General Contable PYME</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowAddSupplierModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleConfirmAddSupplier} className="p-6 space-y-4 text-xs">
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">
                  Razón Social / Nombre Comercial
                </label>
                <input
                  type="text"
                  required
                  value={issuerName}
                  onChange={(e) => setIssuerName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">
                  NIF / CIF Español
                </label>
                <input
                  type="text"
                  required
                  value={issuerCif}
                  onChange={(e) => setIssuerCif(e.target.value.toUpperCase())}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white font-mono uppercase focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1 flex items-center justify-between">
                  <span>Subcuenta de Proveedor (400.X)</span>
                  <span className="text-[10px] text-cyan-400 font-mono">{companyPlanLongitud} dígitos</span>
                </label>
                <input
                  type="text"
                  required
                  value={newProvAccount}
                  onChange={(e) => setNewProvAccount(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-cyan-300 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">
                  Subcuenta de Gasto por Defecto (Grupo 6 PGC)
                </label>
                <select
                  value={newGastoAccount}
                  onChange={(e) => setNewGastoAccount(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-200 focus:outline-none focus:border-cyan-500 cursor-pointer"
                >
                  {pgcGastoOptions.map((opt) => (
                    <option key={opt.codigo} value={opt.codigo} className="bg-slate-900 text-white">
                      {opt.label}
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-slate-500 mt-1">
                  Se asignará automáticamente al generar los asientos de facturas de este emisor.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddSupplierModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white bg-slate-900 border border-slate-800 transition"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={addingSupplier}
                  className="px-4 py-2 font-semibold rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white shadow shadow-cyan-950 transition"
                >
                  {addingSupplier ? 'Guardando...' : 'Registrar en Maestro'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL DE SELECCIÓN VISUAL DE CARPETA AL ARCHIVAR */}
      <ArchiveConfirmationModal
        isOpen={showArchiveModal}
        invoiceId={invoice.id}
        invoiceNumber={invoiceNumber}
        companyCif={companyCif}
        onClose={() => setShowArchiveModal(false)}
        onConfirm={executeApprove}
      />
    </div>
  );
};

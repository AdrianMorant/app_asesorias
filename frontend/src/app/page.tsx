'use client';

import React, { useState, useEffect } from 'react';
import { Company, Invoice, Supplier, SalesInvoice } from '@/types';
import {
  fetchCompanies,
  createCompany,
  fetchSuppliers,
  createSupplier,
  fetchInvoices,
  updateInvoice,
  approveInvoice,
  deleteInvoice,
  bulkDeleteInvoices,
  getFileUrl,
  fetchSalesInvoices,
} from '@/lib/api';

// Componentes modulares de la suite
import { Sidebar, ActiveNavTab, WorkspaceMode } from '@/components/Sidebar';
import { FinancialDashboardView } from '@/components/FinancialDashboardView';
import { AIAssistantDrawer } from '@/components/AIAssistantDrawer';
import { SalesView } from '@/components/SalesView';
import { ContactsView } from '@/components/ContactsView';
import { JournalView } from '@/components/JournalView';
import { ChartOfAccountsView } from '@/components/ChartOfAccountsView';
import { TaxModelsView } from '@/components/TaxModelsView';
import { TaxDashboardView } from '@/components/TaxDashboardView';
import { IntegrationsView } from '@/components/IntegrationsView';
import { BankReconciliationView } from '@/components/BankReconciliationView';
import { AdvisorPortalView } from '@/components/AdvisorPortalView';
import { AssetsView } from '@/components/AssetsView';

// Componentes de Ingesta IA y Split-screen
import { UploadDropzone } from '@/components/UploadDropzone';
import { InvoiceTable } from '@/components/InvoiceTable';
import { PDFViewer } from '@/components/PDFViewer';
import { TriageForm } from '@/components/TriageForm';
import { ManualModal } from '@/components/ManualModal';
import { CompanyManagerModal } from '@/components/CompanyManagerModal';
import { DeleteConfirmationModal } from '@/components/DeleteConfirmationModal';
import { MultiInvoiceSplitterModal } from '@/components/MultiInvoiceSplitterModal';
import { InteractiveDemoModal } from '@/components/InteractiveDemoModal';
import { NotificationCenterDrawer } from '@/components/NotificationCenterDrawer';
import SecuritySettingsModal from '@/components/SecuritySettingsModal';
import { ToastContainer, ToastMessage } from '@/components/Toast';

import {
  Building2,
  Receipt,
  X,
  Plus,
  RefreshCw,
  BookOpen,
  Settings2,
  HardDrive,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FolderOpen,
  Sparkles,
  Bell,
  Menu,
} from 'lucide-react';

export default function AppSuitePage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [sales, setSales] = useState<SalesInvoice[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // Estados del Modo SaaS, Demo Guiada, Notificaciones y Copiloto IA (Fases A, B, C y D)
  const [isAIAssistantOpen, setIsAIAssistantOpen] = useState<boolean>(false);
  const [isDemoModalOpen, setIsDemoModalOpen] = useState<boolean>(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState<boolean>(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const [aiAssistantInitialQuery, setAiAssistantInitialQuery] = useState<string>('');
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>('client');

  const handleOpenAIAssistantWithQuery = (query: string) => {
    setAiAssistantInitialQuery(query);
    setIsAIAssistantOpen(true);
  };

  // Módulo activo en el Sidebar
  const [currentTab, setCurrentTab] = useState<ActiveNavTab>('dashboard');

  // Sistema de Notificaciones Toast
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const notify = (type: 'success' | 'error' | 'info', message: string, title?: string) => {
    const newToast: ToastMessage = {
      id: `${Date.now()}_${Math.random()}`,
      type,
      title,
      message,
    };
    setToasts((prev) => [...prev, newToast]);
  };
  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Modales
  const [showManualModal, setShowManualModal] = useState<boolean>(false);
  const [showCompanyManagerModal, setShowCompanyManagerModal] = useState<boolean>(false);
  const [showNewCompanyModal, setShowNewCompanyModal] = useState<boolean>(false);
  const [isSecurityModalOpen, setIsSecurityModalOpen] = useState<boolean>(false);
  const [userRole, setUserRole] = useState<string>('ADVISOR');

  // Campos para crear nueva empresa
  const [newCompanyCif, setNewCompanyCif] = useState<string>('');
  const [newCompanyRazon, setNewCompanyRazon] = useState<string>('');
  const [newCompanyPlanLong, setNewCompanyPlanLong] = useState<number>(9);
  const [newCompanyStorageBase, setNewCompanyStorageBase] = useState<string>('storage');
  const [newCompanyIvaPeriod, setNewCompanyIvaPeriod] = useState<string>('Trimestral');
  const [newCompanyModalidad, setNewCompanyModalidad] = useState<'erp_completo' | 'copiloto_contable'>('copiloto_contable');
  const [newCompanySoftwareDestino, setNewCompanySoftwareDestino] = useState<string>('a3');
  const [newCompanyRegimen, setNewCompanyRegimen] = useState<string>('general');
  const [creatingCompany, setCreatingCompany] = useState<boolean>(false);
  const [newCompanyError, setNewCompanyError] = useState<string | null>(null);

  // Factura activa seleccionada para el visor split-screen (Ingesta IA)
  const [activeInvoice, setActiveInvoice] = useState<Invoice | null>(null);

  // Modal de confirmación de borrado
  const [deleteModalState, setDeleteModalState] = useState<{
    isOpen: boolean;
    mode: 'single' | 'bulk';
    invoice?: Invoice;
    ids?: string[];
  }>({
    isOpen: false,
    mode: 'single',
  });

  // Modal Maquetador Visual Multi-Factura (MF)
  const [splitModalInvoice, setSplitModalInvoice] = useState<Invoice | null>(null);
  const [isSplitModalOpen, setIsSplitModalOpen] = useState<boolean>(false);
  const [isBackendOffline, setIsBackendOffline] = useState<boolean>(false);

  // Carga inicial resiliente con timeout de seguridad
  const loadInitialData = async () => {
    setLoading(true);
    setIsBackendOffline(false);
    try {
      // Timeout de 5s para garantizar que la interfaz se libere incluso si el backend está caído o bloqueado
      const timeoutPromise = new Promise<Company[]>((resolve) =>
        setTimeout(() => resolve([]), 5000)
      );

      const comps = await Promise.race([
        fetchCompanies().catch((err) => {
          console.warn('Fallo al obtener empresas:', err);
          return [] as Company[];
        }),
        timeoutPromise,
      ]);

      const safeComps = Array.isArray(comps) ? comps : [];
      setCompanies(safeComps);

      if (safeComps.length === 0) {
        setIsBackendOffline(true);
      }

      let currentCompanyId = selectedCompanyId;
      if (!currentCompanyId && safeComps.length > 0) {
        currentCompanyId = safeComps[0].id;
        setSelectedCompanyId(currentCompanyId);
      } else if (safeComps.length > 0 && !safeComps.some((c) => c.id === currentCompanyId)) {
        currentCompanyId = safeComps[0].id;
        setSelectedCompanyId(currentCompanyId);
      }

      if (currentCompanyId) {
        const [supps, invs, sls] = await Promise.all([
          fetchSuppliers(currentCompanyId).catch(() => []),
          fetchInvoices({ companyId: currentCompanyId }).catch(() => []),
          fetchSalesInvoices(currentCompanyId).catch(() => []),
        ]);
        setSuppliers(Array.isArray(supps) ? supps : []);
        setInvoices(Array.isArray(invs) ? invs : []);
        setSales(Array.isArray(sls) ? sls : []);
      } else {
        setSuppliers([]);
        setInvoices([]);
        setSales([]);
      }
    } catch (err) {
      console.error('Error cargando datos iniciales:', err);
      setIsBackendOffline(true);
      setCompanies([]);
      setSuppliers([]);
      setInvoices([]);
      setSales([]);
      notify('info', 'El backend no respondió de inmediato. La interfaz continúa operativa con datos locales seguros.');
    } finally {
      // Garantizar que loading pase a false bajo cualquier circunstancia
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  // Recarga al cambiar de empresa con resiliencia total
  useEffect(() => {
    if (!selectedCompanyId) {
      setRefreshing(false);
      return;
    }
    let isCancelled = false;

    const reloadForCompany = async () => {
      setRefreshing(true);
      try {
        const [supps, invs, sls] = await Promise.all([
          fetchSuppliers(selectedCompanyId).catch(() => []),
          fetchInvoices({ companyId: selectedCompanyId }).catch(() => []),
          fetchSalesInvoices(selectedCompanyId).catch(() => []),
        ]);
        if (!isCancelled) {
          setSuppliers(Array.isArray(supps) ? supps : []);
          setInvoices(Array.isArray(invs) ? invs : []);
          setSales(Array.isArray(sls) ? sls : []);
          if (activeInvoice && activeInvoice.company_id !== selectedCompanyId) {
            setActiveInvoice(null);
          }
        }
      } catch (err) {
        console.error('Error al cambiar de empresa:', err);
        if (!isCancelled) {
          notify('error', 'Error al sincronizar datos de la empresa.');
        }
      } finally {
        if (!isCancelled) {
          setRefreshing(false);
        }
      }
    };

    reloadForCompany();

    return () => {
      isCancelled = true;
    };
  }, [selectedCompanyId]);

  // Manejo de eventos de facturas recibidas
  const handleInvoiceUploaded = (newInvoice: Invoice) => {
    setInvoices((prev) => [newInvoice, ...prev]);
    setActiveInvoice(newInvoice);
    notify(
      'success',
      `Factura ${newInvoice.invoice_number || 'procesada'} extraída con IA y clasificada (${newInvoice.status}).`,
      'Nueva Factura'
    );
  };

  const handleSaveInvoice = async (updatedData: any) => {
    if (!activeInvoice) return;
    try {
      const updated = await updateInvoice(activeInvoice.id, updatedData);
      setActiveInvoice(updated);
      setInvoices((prev) => prev.map((inv) => (inv.id === updated.id ? updated : inv)));
      notify('success', 'Cambios guardados y reglas recalculadas.', 'Guardado Exitoso');
    } catch (err: any) {
      notify('error', err.message || 'Error al guardar factura.', 'Error');
      throw err;
    }
  };

  const handleApproveInvoice = async (
    invoiceId: string,
    customDest?: { custom_subfolder?: string; custom_filename?: string }
  ) => {
    try {
      const approved = await approveInvoice(invoiceId, customDest);
      setActiveInvoice(approved);
      setInvoices((prev) => prev.map((inv) => (inv.id === approved.id ? approved : inv)));
      notify(
        'success',
        'Factura aprobada y archivada estructuradamente en el almacenamiento local.',
        'Archivado Exitoso'
      );
    } catch (err: any) {
      notify('error', err.message || 'Error al archivar factura.', 'Error');
      throw err;
    }
  };

  const handleCreateSupplier = async (data: {
    cif: string;
    nombre: string;
    subcuenta_proveedor: string;
    subcuenta_gasto_defecto: string;
  }) => {
    if (!selectedCompanyId) return;
    try {
      const created = await createSupplier({
        ...data,
        company_id: selectedCompanyId,
      });
      setSuppliers((prev) => [...prev, created]);
      notify('success', `Proveedor ${created.nombre} registrado en el maestro contable.`);
      if (activeInvoice && activeInvoice.issuer_cif === data.cif) {
        await handleSaveInvoice({ supplier_id: created.id });
      }
    } catch (err: any) {
      notify('error', err.message || 'Error al crear proveedor.', 'Error');
      throw err;
    }
  };

  const handlePromptDeleteSingle = (inv: Invoice) => {
    setDeleteModalState({
      isOpen: true,
      mode: 'single',
      invoice: inv,
    });
  };

  const handlePromptBulkDelete = (ids: string[]) => {
    setDeleteModalState({
      isOpen: true,
      mode: 'bulk',
      ids,
    });
  };

  const handleConfirmDelete = async () => {
    try {
      if (deleteModalState.mode === 'single' && deleteModalState.invoice) {
        const targetId = deleteModalState.invoice.id;
        await deleteInvoice(targetId);
        setInvoices((prev) => prev.filter((i) => i.id !== targetId));
        if (activeInvoice && activeInvoice.id === targetId) {
          setActiveInvoice(null);
        }
        notify('success', 'Factura y fichero físico eliminados permanentemente.', 'Factura Eliminada');
      } else if (deleteModalState.mode === 'bulk' && deleteModalState.ids) {
        const idsToDelete = [...deleteModalState.ids];
        await bulkDeleteInvoices(idsToDelete);
        setInvoices((prev) => prev.filter((i) => !idsToDelete.includes(i.id)));
        if (activeInvoice && idsToDelete.includes(activeInvoice.id)) {
          setActiveInvoice(null);
        }
        notify('success', `${idsToDelete.length} facturas y ficheros eliminados con éxito.`, 'Lote Eliminado');
      }
    } catch (err: any) {
      console.error('Error al eliminar facturas:', err);
      notify('error', err.message || 'Error al eliminar factura(s).', 'Fallo al Eliminar');
      throw err;
    } finally {
      setDeleteModalState({ isOpen: false, mode: 'single', ids: [] });
      if (selectedCompanyId) {
        fetchInvoices({ companyId: selectedCompanyId }).then((fresh) => setInvoices(fresh)).catch(() => {});
      }
    }
  };

  const handleOpenSplitter = (inv: Invoice) => {
    setSplitModalInvoice(inv);
    setIsSplitModalOpen(true);
  };

  const handleSplitSuccess = (newSubInvoices: Invoice[]) => {
    setIsSplitModalOpen(false);
    setSplitModalInvoice(null);
    if (selectedCompanyId) {
      fetchInvoices({ companyId: selectedCompanyId })
        .then((fresh) => {
          setInvoices(fresh);
          if (newSubInvoices.length > 0) {
            const firstChild = fresh.find((i) => i.id === newSubInvoices[0].id) || newSubInvoices[0];
            setActiveInvoice(firstChild);
          }
        })
        .catch(() => {});
    }
    notify(
      'success',
      `Documento disgregado con éxito en ${newSubInvoices.length} sub-facturas independientes.`,
      'Separación Completada'
    );
  };

  const handleCreateCompanySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setNewCompanyError(null);
    setCreatingCompany(true);
    try {
      const created = await createCompany({
        cif: newCompanyCif.trim().toUpperCase(),
        razon_social: newCompanyRazon.trim(),
        plan_cuentas_longitud: newCompanyPlanLong,
        storage_base_path: newCompanyStorageBase.trim() || 'storage',
        iva_periodicity: newCompanyIvaPeriod,
        modalidad_uso: newCompanyModalidad,
        software_destino: newCompanySoftwareDestino,
        regimen_tributario: newCompanyRegimen,
      });
      setCompanies((prev) => [...prev, created]);
      setSelectedCompanyId(created.id);
      setShowNewCompanyModal(false);
      setNewCompanyCif('');
      setNewCompanyRazon('');
      setNewCompanyStorageBase('storage');
      setNewCompanyIvaPeriod('Trimestral');
      setNewCompanyModalidad('copiloto_contable');
      setNewCompanySoftwareDestino('a3');
      setNewCompanyRegimen('general');
      notify('success', `Empresa '${created.razon_social}' creada correctamente.`, 'Empresa Creada');
    } catch (err: any) {
      setNewCompanyError(err.message || 'Error al crear la empresa');
    } finally {
      setCreatingCompany(false);
    }
  };

  const selectedCompany = companies.find((c) => c.id === selectedCompanyId);

  // Contadores para el badge del semáforo
  const yellowCount = invoices.filter((i) => i.status === 'YELLOW' && !i.is_processed).length;
  const redCount = invoices.filter((i) => i.status === 'RED' && !i.is_processed).length;
  const pendingCount = invoices.filter((i) => !i.is_processed).length;

  return (
    <div className="flex h-screen bg-slate-50 font-sans text-slate-900 overflow-hidden">
      {/* Toast Notificaciones Flotantes */}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />

      {/* 1. SIDEBAR DESKTOP */}
      <div className="hidden lg:flex flex-shrink-0">
        <Sidebar
          currentTab={currentTab}
          onSelectTab={(tab) => {
            if (tab === 'companies') {
              setShowCompanyManagerModal(true);
            } else {
              setCurrentTab(tab);
            }
          }}
          companies={companies}
          selectedCompanyId={selectedCompanyId}
          onSelectCompany={(id) => setSelectedCompanyId(id)}
          onOpenCompanyManager={() => setShowCompanyManagerModal(true)}
          pendingInvoicesCount={pendingCount}
          yellowInvoicesCount={yellowCount}
          redInvoicesCount={redCount}
          mode={workspaceMode}
          onModeChange={setWorkspaceMode}
        />
      </div>

      {/* 1.1 SIDEBAR MÓVIL EN DRAWER CON BACKDROP */}
      {isMobileSidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-slate-950/70 backdrop-blur-xs transition-opacity"
            onClick={() => setIsMobileSidebarOpen(false)}
          />
          <div className="relative z-10 flex flex-col w-64 max-w-[85vw] h-full shadow-2xl animate-in slide-in-from-left duration-200">
            <Sidebar
              currentTab={currentTab}
              onSelectTab={(tab) => {
                setIsMobileSidebarOpen(false);
                if (tab === 'companies') {
                  setShowCompanyManagerModal(true);
                } else {
                  setCurrentTab(tab);
                }
              }}
              companies={companies}
              selectedCompanyId={selectedCompanyId}
              onSelectCompany={(id) => {
                setSelectedCompanyId(id);
                setIsMobileSidebarOpen(false);
              }}
              onOpenCompanyManager={() => {
                setIsMobileSidebarOpen(false);
                setShowCompanyManagerModal(true);
              }}
              pendingInvoicesCount={pendingCount}
              yellowInvoicesCount={yellowCount}
              redInvoicesCount={redCount}
              mode={workspaceMode}
              onModeChange={setWorkspaceMode}
            />
          </div>
        </div>
      )}

      {/* 2. ÁREA DE CONTENIDO PRINCIPAL */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Barra Superior Corporativa */}
        <header className="h-14 bg-white border-b border-slate-200/80 px-4 sm:px-6 flex items-center justify-between shrink-0 shadow-xs">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            {/* Botón Hamburguesa Móvil (Fase D) */}
            <button
              onClick={() => setIsMobileSidebarOpen(true)}
              className="lg:hidden p-1.5 -ml-1 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
              title="Abrir menú de navegación"
            >
              <Menu className="w-5 h-5" />
            </button>

            <h2 className="text-sm font-bold text-slate-800 tracking-tight truncate">
              {currentTab === 'dashboard' && 'Dashboard General Financiero'}
              {currentTab === 'sales' && 'Ventas y Facturación Emitida'}
              {currentTab === 'expenses' && 'Gastos, Compras e Ingesta IA'}
              {currentTab === 'contacts' && 'Directorio de Contactos (CRM)'}
              {currentTab === 'journal' && 'Contabilidad y Libros Oficiales'}
              {currentTab === 'chart-of-accounts' && 'Plan General Contable PYME'}
              {currentTab === 'taxes' && 'Impuestos y Modelos Tributarios (AEAT)'}
              {currentTab === 'integrations' && 'Centro de Conexiones y Enlace Contable'}
            </h2>

            {selectedCompany && (
              <div className="hidden md:inline-flex items-center gap-2 shrink-0">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 text-xs font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                  {selectedCompany.razon_social} ({selectedCompany.cif})
                </span>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                  selectedCompany.modalidad_uso === 'erp_completo'
                    ? 'bg-purple-50 text-purple-700 border-purple-200'
                    : 'bg-cyan-50 text-cyan-700 border-cyan-200'
                }`}>
                  {selectedCompany.modalidad_uso === 'erp_completo'
                    ? 'MODALIDAD A: ERP'
                    : `MODALIDAD B: COPILOTO (${(selectedCompany.software_destino || 'A3').toUpperCase()})`}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
            {/* Botón Destacado Copiloto IA */}
            <button
              onClick={() => setIsAIAssistantOpen(true)}
              className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-semibold rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white shadow-sm transition-all active:scale-95"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Copiloto IA</span>
            </button>

            {/* Centro de Notificaciones Inteligentes (Fase D) */}
            <button
              onClick={() => setIsNotificationsOpen(true)}
              className="relative p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors"
              title="Centro de notificaciones y alertas"
            >
              <Bell className="w-4 h-4" />
              {invoices.filter((i) => i.status === 'RED').length > 0 && (
                <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500" />
                </span>
              )}
            </button>

            {/* Recargar datos */}
            <button
              onClick={() => {
                if (selectedCompanyId) {
                  setRefreshing(true);
                  Promise.all([
                    fetchSuppliers(selectedCompanyId),
                    fetchInvoices({ companyId: selectedCompanyId }),
                    fetchSalesInvoices(selectedCompanyId).catch(() => []),
                  ]).then(([s, invs, sls]) => {
                    setSuppliers(s);
                    setInvoices(invs);
                    setSales(sls);
                    notify('info', 'Datos actualizados desde el servidor.');
                    setRefreshing(false);
                  });
                }
              }}
              disabled={refreshing}
              className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors hidden sm:block"
              title="Refrescar datos"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-indigo-600' : ''}`} />
            </button>

            {/* Centro de Seguridad y RBAC */}
            <button
              onClick={() => setIsSecurityModalOpen(true)}
              className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-bold rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 shadow-xs transition-all active:scale-95"
              title="Control de acceso, roles RBAC y copias de seguridad"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
              <span className="hidden sm:inline">Seguridad & RBAC</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-indigo-50 text-indigo-700 font-bold border border-indigo-200">
                {userRole}
              </span>
            </button>

            {/* Probar Demo Guiada (Fase C) */}
            <button
              onClick={() => setIsDemoModalOpen(true)}
              className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-bold rounded-xl bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white shadow-sm shadow-cyan-600/20 active:scale-95 transition-all"
            >
              <Sparkles className="w-3.5 h-3.5 text-cyan-200 animate-pulse" />
              <span className="hidden sm:inline">Probar Demo Guiada (1 min)</span>
              <span className="sm:hidden">Demo</span>
            </button>

            {/* Manual Operativo */}
            <button
              onClick={() => setShowManualModal(true)}
              className="hidden md:flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>Manual</span>
            </button>

            {/* Alta de Empresa */}
            <button
              onClick={() => setShowNewCompanyModal(true)}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg bg-slate-900 hover:bg-slate-800 text-white transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Nueva Empresa</span>
            </button>
          </div>
        </header>

        {/* Contenedor con scroll para cada módulo */}
        <main className="flex-1 overflow-y-auto p-6 custom-scrollbar">
          {loading ? (
            <div className="flex flex-col items-center justify-center min-h-[50vh] text-center p-8 animate-in fade-in duration-200">
              <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-4 shadow-sm">
                <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin" />
              </div>
              <h3 className="text-sm font-bold text-slate-800 mb-1">
                Sincronizando con KontaAI Suite...
              </h3>
              <p className="text-xs text-slate-400 max-w-sm">
                Inicializando espacio contable, comprobando empresas y reglas fiscales.
              </p>
            </div>
          ) : !selectedCompany ? (
            <div className="max-w-2xl mx-auto my-6 p-8 sm:p-10 text-center bg-white rounded-2xl border border-slate-200/90 shadow-sm animate-in fade-in duration-200">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm">
                <Building2 className="w-7 h-7" />
              </div>
              <h3 className="text-base font-bold text-slate-900 mb-2">
                Bienvenido a KontaAI Suite para Asesorías
              </h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mb-6 leading-relaxed">
                Para comenzar a contabilizar facturas y liquidar modelos tributarios, crea una empresa cliente o explora la demostración interactiva guiada.
              </p>

              {isBackendOffline && (
                <div className="mb-6 mx-auto max-w-lg flex items-center gap-2.5 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs font-medium text-left">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>El servidor backend está en espera (http://127.0.0.1:8000). Puedes interactuar con la demo guiada y la interfaz mientras se conecta.</span>
                </div>
              )}

              <div className="flex flex-wrap items-center justify-center gap-3">
                <button
                  onClick={() => setShowNewCompanyModal(true)}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-sm shadow-indigo-600/20 transition-all active:scale-95"
                >
                  <Plus className="w-4 h-4" />
                  <span>Crear Primera Empresa</span>
                </button>
                <button
                  onClick={() => setIsDemoModalOpen(true)}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-bold shadow-sm shadow-cyan-600/20 transition-all active:scale-95"
                >
                  <Sparkles className="w-4 h-4 text-cyan-200" />
                  <span>Probar Demo Guiada (1 min)</span>
                </button>
                <button
                  onClick={loadInitialData}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-all active:scale-95"
                >
                  <RefreshCw className="w-4 h-4" />
                  <span>Reintentar Conexión</span>
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* VISTA 1: DASHBOARD GENERAL */}
              {currentTab === 'dashboard' && (
                <FinancialDashboardView
                  company={selectedCompany}
                  invoices={invoices}
                  onNavigateTab={(tab) => setCurrentTab(tab)}
                  onSelectInvoice={(inv) => {
                    setActiveInvoice(inv);
                    setCurrentTab('expenses');
                  }}
                  onOpenAIAssistant={() => setIsAIAssistantOpen(true)}
                  mode={workspaceMode}
                  onOpenDemo={() => setIsDemoModalOpen(true)}
                  onOpenUpload={() => setCurrentTab('expenses')}
                />
              )}

              {/* VISTA 2: VENTAS (EMISIÓN) */}
              {currentTab === 'sales' && (
                <SalesView
                  company={selectedCompany}
                  onNotify={notify}
                  onNavigateToContacts={() => setCurrentTab('contacts')}
                />
              )}

              {/* VISTA 3: GASTOS E INGESTA IA (NÚCLEO EXISTENTE) */}
              {currentTab === 'expenses' && (
                <div className="space-y-6">
                  {/* Resumen Semafórico de Gastos */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
                    <div className="bg-white border border-slate-200/80 rounded-xl p-3.5 shadow-sm">
                      <span className="text-[11px] font-medium text-slate-500">Total Facturas Recibidas</span>
                      <div className="text-xl font-bold font-mono text-slate-900 mt-1">
                        {invoices.length}
                      </div>
                      <span className="text-[10px] text-slate-400">
                        {invoices.filter((i) => i.is_processed).length} archivadas / revisadas
                      </span>
                    </div>

                    <div className="bg-emerald-50/50 border border-emerald-200/80 rounded-xl p-3.5 shadow-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-medium text-emerald-800">Verdes (Aprobadas)</span>
                        <span className="w-2 h-2 rounded-full bg-emerald-500" />
                      </div>
                      <div className="text-xl font-bold font-mono text-emerald-700 mt-1">
                        {invoices.filter((i) => i.status === 'GREEN').length}
                      </div>
                      <span className="text-[10px] text-emerald-600">100% cuadre y validadas</span>
                    </div>

                    <div className="bg-amber-50/50 border border-amber-200/80 rounded-xl p-3.5 shadow-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-medium text-amber-800">Amarillas (Revisión)</span>
                        <span className="w-2 h-2 rounded-full bg-amber-500" />
                      </div>
                      <div className="text-xl font-bold font-mono text-amber-700 mt-1">
                        {invoices.filter((i) => i.status === 'YELLOW').length}
                      </div>
                      <span className="text-[10px] text-amber-600">Subcuenta o proveedor nuevo</span>
                    </div>

                    <div className="bg-rose-50/50 border border-rose-200/80 rounded-xl p-3.5 shadow-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-medium text-rose-800">Rojas (Bloqueadas)</span>
                        <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
                      </div>
                      <div className="text-xl font-bold font-mono text-rose-700 mt-1">
                        {invoices.filter((i) => i.status === 'RED').length}
                      </div>
                      <span className="text-[10px] text-rose-600">Anomalía o descuadre</span>
                    </div>
                  </div>

                  {/* Drag and Drop Ingesta IA */}
                  <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm">
                    <h3 className="text-sm font-bold text-slate-800 mb-1">
                      Ingesta Multimodal con IA (Gemini Vision)
                    </h3>
                    <p className="text-xs text-slate-500 mb-4">
                      Arrastra facturas en formato PDF, PNG o JPEG. El modelo extraerá datos fiscales,
                      verificará CIF/NIF con la AEAT y generará los asientos contables en el PGC.
                    </p>
                    <UploadDropzone
                      companyId={selectedCompanyId}
                      onInvoiceUploaded={handleInvoiceUploaded}
                      onOpenSplitter={handleOpenSplitter}
                    />
                  </div>

                  {/* Bandeja de Facturas */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-slate-800">
                        Bandeja de Facturas y Triaje
                      </h3>
                      <span className="text-xs text-slate-400">
                        Haz clic en cualquier factura para abrir la consola Split-Screen
                      </span>
                    </div>

                    <InvoiceTable
                      invoices={invoices}
                      onSelectInvoice={(inv) => setActiveInvoice(inv)}
                      selectedInvoiceId={activeInvoice?.id}
                      onDeleteInvoice={handlePromptDeleteSingle}
                      onBulkDelete={handlePromptBulkDelete}
                      onOpenSplitter={handleOpenSplitter}
                    />
                  </div>
                </div>
              )}

              {/* VISTA 4: CONTACTOS (CRM CONTABLE) */}
              {currentTab === 'contacts' && (
                <ContactsView company={selectedCompany} onNotify={notify} />
              )}

              {/* VISTA 5: CONCILIACIÓN BANCARIA INTELIGENTE */}
              {currentTab === 'banking' && (
                <BankReconciliationView
                  company={selectedCompany}
                  onNotify={notify}
                  onRefreshData={() => {
                    if (selectedCompanyId) {
                      fetchInvoices({ companyId: selectedCompanyId }).then((invs) => setInvoices(invs));
                    }
                  }}
                />
              )}

              {/* VISTA 6: LIBROS CONTABLES (DIARIO, MAYOR, SUMAS Y SALDOS) */}
              {currentTab === 'journal' && (
                <JournalView company={selectedCompany} onNotify={notify} />
              )}

              {/* VISTA 6: PLAN GENERAL CONTABLE PYME */}
              {currentTab === 'chart-of-accounts' && (
                <ChartOfAccountsView company={selectedCompany} notify={notify} />
              )}

              {/* VISTA 7: PANEL FISCAL PARA NO CONTABLES Y MODELOS TRIBUTARIOS (FASE B) */}
              {currentTab === 'taxes' && (
                <TaxDashboardView
                  company={selectedCompany}
                  invoices={invoices}
                  sales={sales}
                  onNotify={notify}
                  onNavigateTab={(tab) => setCurrentTab(tab)}
                  onOpenAIAssistantWithQuery={handleOpenAIAssistantWithQuery}
                  mode={workspaceMode}
                />
              )}

              {/* VISTA 7.5: INMOVILIZADO Y AMORTIZACIONES PGC (FASE 6) */}
              {currentTab === 'assets' && (
                <AssetsView company={selectedCompany} onNotify={notify} />
              )}

              {/* VISTA 8: CENTRO DE INTEGRACIONES Y ENLACE CONTABLE */}
              {currentTab === 'integrations' && (
                <IntegrationsView
                  company={selectedCompany}
                  invoices={invoices}
                  onNotify={notify}
                  onRefreshData={() => {
                    if (selectedCompanyId) {
                      fetchInvoices({ companyId: selectedCompanyId }).then((invs) => setInvoices(invs));
                    }
                  }}
                />
              )}

              {/* VISTA 9: PORTAL DEL ASESOR Y SUPERVISIÓN MULTI-TENANT */}
              {currentTab === 'advisor' && (
                <AdvisorPortalView
                  currentCompanyId={selectedCompanyId}
                  onSelectCompany={(newCompanyId) => {
                    setSelectedCompanyId(newCompanyId);
                    setCurrentTab('dashboard');
                  }}
                  onNotify={notify}
                />
              )}
            </>
          )}
        </main>
      </div>

      {/* 3. CONSOLA SPLIT-SCREEN (VISOR PDF + FORMULARIO REACTIVO DE TRIAJE) */}
      {activeInvoice && (
        <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-md flex flex-col animate-in fade-in duration-200">
          {/* Barra superior de la vista dividida */}
          <div className="h-14 bg-slate-950 border-b border-slate-800 px-6 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                Consola de Triaje y Contabilización
              </span>
              <span className="text-slate-600">/</span>
              <span className="text-xs text-white font-mono font-bold">
                {activeInvoice.invoice_number || 'S/N'}
              </span>
              <span className="text-xs text-slate-400">
                ({activeInvoice.issuer_name})
              </span>
            </div>

            <button
              type="button"
              onClick={() => setActiveInvoice(null)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Cerrar panel de triaje (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Área Split-Screen */}
          <div className="flex-1 flex flex-col lg:flex-row overflow-hidden p-4 gap-4">
            {/* Panel Izquierdo: Visor PDF interactivo */}
            <div className="w-full lg:w-1/2 h-[50vh] lg:h-full bg-slate-950 rounded-xl overflow-hidden border border-slate-800">
              <PDFViewer
                fileUrl={getFileUrl(activeInvoice.file_path)}
                fileName={activeInvoice.file_name}
              />
            </div>

            {/* Panel Derecho: Formulario Reactivo de Triaje con Semáforo y Modal de Archivo */}
            <div className="w-full lg:w-1/2 h-[50vh] lg:h-full overflow-y-auto custom-scrollbar">
              <TriageForm
                invoice={activeInvoice}
                companyCif={selectedCompany?.cif}
                companyPlanLongitud={selectedCompany?.plan_cuentas_longitud || 9}
                suppliers={suppliers}
                onSave={handleSaveInvoice}
                onApprove={handleApproveInvoice}
                onDelete={handlePromptDeleteSingle}
                onCreateSupplier={handleCreateSupplier}
                onOpenSplitter={handleOpenSplitter}
              />
            </div>
          </div>
        </div>
      )}

      {/* 4. MODALES AUXILIARES */}
      {/* Modal Manual Operativo */}
      <ManualModal isOpen={showManualModal} onClose={() => setShowManualModal(false)} />

      {/* Modal Administración de Empresa */}
      <CompanyManagerModal
        isOpen={showCompanyManagerModal}
        company={selectedCompany || null}
        onClose={() => setShowCompanyManagerModal(false)}
        onCompanyUpdated={(updated) => {
          setCompanies((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
          notify('success', `Datos actualizados para ${updated.razon_social}.`);
        }}
        onCompanyDeleted={(deletedId) => {
          setCompanies((prev) => prev.filter((c) => c.id !== deletedId));
          setSelectedCompanyId('');
          loadInitialData();
          notify('info', 'Empresa eliminada.');
        }}
        notify={notify}
      />

      {/* Modal Alta Nueva Empresa */}
      {showNewCompanyModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-indigo-600" />
                Nueva Empresa Asesorada
              </h3>
              <button
                type="button"
                onClick={() => setShowNewCompanyModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {newCompanyError && (
              <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                {newCompanyError}
              </div>
            )}

            <form onSubmit={handleCreateCompanySubmit} className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  CIF / NIF de la Empresa *
                </label>
                <input
                  type="text"
                  required
                  value={newCompanyCif}
                  onChange={(e) => setNewCompanyCif(e.target.value.toUpperCase())}
                  placeholder="Ej. B12345674 o A28015865"
                  className="w-full px-3 py-2 border rounded-xl font-mono uppercase focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  Razón Social / Nombre Comercial *
                </label>
                <input
                  type="text"
                  required
                  value={newCompanyRazon}
                  onChange={(e) => setNewCompanyRazon(e.target.value)}
                  placeholder="Ej. Soluciones Digitales Mediterráneo S.L."
                  className="w-full px-3 py-2 border rounded-xl focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Modalidad de Trabajo *
                  </label>
                  <select
                    value={newCompanyModalidad}
                    onChange={(e) => setNewCompanyModalidad(e.target.value as any)}
                    className="w-full px-3 py-2 border rounded-xl focus:ring-1 focus:ring-indigo-500 outline-none text-xs"
                  >
                    <option value="copiloto_contable">Modalidad B: Copiloto (Enlace ERP)</option>
                    <option value="erp_completo">Modalidad A: ERP Completo</option>
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Software Contable Enlace
                  </label>
                  <select
                    value={newCompanySoftwareDestino}
                    onChange={(e) => setNewCompanySoftwareDestino(e.target.value)}
                    className="w-full px-3 py-2 border rounded-xl focus:ring-1 focus:ring-indigo-500 outline-none text-xs"
                  >
                    <option value="a3">Wolters Kluwer A3 (SUENLACE.DAT)</option>
                    <option value="contasol">Software DELSOL Contasol</option>
                    <option value="sage">Sage 50 / Despachos Connected</option>
                    <option value="holded">Holded</option>
                    <option value="otro">Otro</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Longitud Subcuentas (PGC)
                  </label>
                  <select
                    value={newCompanyPlanLong}
                    onChange={(e) => setNewCompanyPlanLong(Number(e.target.value))}
                    className="w-full px-3 py-2 border rounded-xl focus:ring-1 focus:ring-indigo-500 outline-none text-xs"
                  >
                    <option value={9}>9 dígitos (Estándar)</option>
                    <option value={8}>8 dígitos</option>
                    <option value={10}>10 dígitos</option>
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Liquidación de IVA
                  </label>
                  <select
                    value={newCompanyIvaPeriod}
                    onChange={(e) => setNewCompanyIvaPeriod(e.target.value)}
                    className="w-full px-3 py-2 border rounded-xl focus:ring-1 focus:ring-indigo-500 outline-none text-xs"
                  >
                    <option value="Trimestral">Trimestral (T1..T4)</option>
                    <option value="Mensual">Mensual (SII/REDEME)</option>
                    <option value="Anual">Anual</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  Ruta Base de Almacenamiento
                </label>
                <input
                  type="text"
                  value={newCompanyStorageBase}
                  onChange={(e) => setNewCompanyStorageBase(e.target.value)}
                  placeholder="storage"
                  className="w-full px-3 py-2 border rounded-xl font-mono focus:ring-1 focus:ring-indigo-500 outline-none text-xs"
                />
              </div>

              <div className="pt-3 border-t flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowNewCompanyModal(false)}
                  className="px-4 py-2 border rounded-lg text-slate-600 hover:bg-slate-50 font-medium"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={creatingCompany}
                  className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold"
                >
                  {creatingCompany ? 'Creando...' : 'Crear Empresa'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Confirmación de Borrado */}
      <DeleteConfirmationModal
        isOpen={deleteModalState.isOpen}
        onClose={() => setDeleteModalState({ isOpen: false, mode: 'single' })}
        onConfirm={handleConfirmDelete}
        count={deleteModalState.mode === 'bulk' ? deleteModalState.ids?.length : 1}
        itemDescription={
          deleteModalState.mode === 'single' && deleteModalState.invoice
            ? `Factura ${deleteModalState.invoice.invoice_number || 'S/N'} (${deleteModalState.invoice.issuer_name})`
            : undefined
        }
      />

      {/* Modal Maquetador Visual de Corte Multi-Factura (MF) */}
      {isSplitModalOpen && splitModalInvoice && (
        <MultiInvoiceSplitterModal
          invoice={splitModalInvoice}
          isOpen={isSplitModalOpen}
          onClose={() => {
            setIsSplitModalOpen(false);
            setSplitModalInvoice(null);
          }}
          onSuccess={handleSplitSuccess}
          onNotify={notify}
        />
      )}

      {/* Modal de Demostración Interactiva Guiada (Fase C) */}
      <InteractiveDemoModal
        isOpen={isDemoModalOpen}
        onClose={() => setIsDemoModalOpen(false)}
        onGoToRealApp={() => {
          setIsDemoModalOpen(false);
          setCurrentTab('expenses');
        }}
      />

      {/* Botón Flotante Permanente del Copiloto Konta IA */}
      <button
        onClick={() => setIsAIAssistantOpen(true)}
        className={`fixed bottom-6 right-6 z-40 flex items-center gap-2.5 px-4 py-3 rounded-full shadow-2xl border transition-all group active:scale-95 hover:scale-105 ${
          workspaceMode === 'advisor'
            ? 'bg-slate-900 border-blue-500/40 text-white shadow-blue-500/10'
            : 'bg-slate-900 border-slate-700/80 text-white shadow-slate-950/40'
        }`}
      >
        <div
          className={`w-7 h-7 rounded-full flex items-center justify-center shadow-sm ${
            workspaceMode === 'advisor'
              ? 'bg-gradient-to-br from-blue-600 to-indigo-600 text-white'
              : 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white'
          }`}
        >
          <Sparkles className="w-4 h-4" />
        </div>
        <div className="text-left pr-1">
          <span className="text-xs font-bold block leading-none">Copiloto IA</span>
          <span className="text-[10px] text-slate-400 block leading-tight mt-0.5">Asistente Financiero</span>
        </div>
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse ml-0.5" />
      </button>

      {/* Drawer Deslizante del Copiloto Financiero IA */}
      {selectedCompany && (
        <AIAssistantDrawer
          isOpen={isAIAssistantOpen}
          onClose={() => {
            setIsAIAssistantOpen(false);
            setAiAssistantInitialQuery('');
          }}
          company={selectedCompany}
          invoices={invoices}
          sales={sales}
          onNavigateTab={(tab) => setCurrentTab(tab)}
          onSelectInvoice={(inv) => {
            setActiveInvoice(inv);
            setCurrentTab('expenses');
          }}
          mode={workspaceMode}
          initialQuery={aiAssistantInitialQuery}
        />
      )}

      {/* Centro de Notificaciones Inteligentes (Fase D) */}
      {selectedCompany && (
        <NotificationCenterDrawer
          isOpen={isNotificationsOpen}
          onClose={() => setIsNotificationsOpen(false)}
          invoices={invoices}
          company={selectedCompany}
          onNavigateTab={(tab) => setCurrentTab(tab)}
          onSelectInvoice={(inv) => {
            setActiveInvoice(inv);
            setCurrentTab('expenses');
          }}
        />
      )}

      {/* Modal del Centro de Seguridad, RBAC y Fiabilidad Operativa */}
      <SecuritySettingsModal
        isOpen={isSecurityModalOpen}
        onClose={() => setIsSecurityModalOpen(false)}
        currentRole={userRole}
        onRoleChange={(newRole) => {
          setUserRole(newRole);
          notify('info', `Rol activo cambiado a '${newRole}' para pruebas RBAC.`);
        }}
        currentUserEmail="asesor@konta.ai"
      />
    </div>
  );
}

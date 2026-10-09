import {
  Company,
  Invoice,
  InvoiceUpdatePayload,
  Supplier,
  Account,
  AccountPaginatedResponse,
  AccountImportSummary,
  ProposedArchivePath,
  CompanyIntegration,
  ExportBatch,
  Contact,
  ContactCreatePayload,
  SalesInvoice,
  SalesInvoiceCreatePayload,
  TaxSummaryResponse,
  JournalResponse,
  LedgerResponse,
  TrialBalanceResponse,
  SoftwareType,
  InvoicePagesResponse,
  SplitInvoiceRequest,
  NextSubaccountResponse,
} from '@/types';

/**
 * Resolucion dinamica de la URL base del API.
 * En Server Functions / SSR, utiliza la vinculacion interna BACKEND_URL inyectada por Vercel Services.
 * En el navegador del cliente o fallback local, utiliza NEXT_PUBLIC_API_URL o la ruta relativa '/api/v1'.
 */
export function getApiBase(): string {
  if (typeof window === 'undefined' && process.env.BACKEND_URL) {
    return `${process.env.BACKEND_URL.replace(/\/$/, '')}/api/v1`;
  }
  return process.env.NEXT_PUBLIC_API_URL || '/api/v1';
}

export function getBackendBase(): string {
  if (typeof window === 'undefined' && process.env.BACKEND_URL) {
    return process.env.BACKEND_URL.replace(/\/$/, '');
  }
  return process.env.NEXT_PUBLIC_BACKEND_URL || '';
}

export const API_BASE = {
  toString: () => getApiBase(),
} as unknown as string;

export const BACKEND_BASE = {
  toString: () => getBackendBase(),
} as unknown as string;


// -------------------------------------------------------------
// EMPRESAS
// -------------------------------------------------------------
export async function fetchCompanies(): Promise<Company[]> {
  try {
    const res = await fetch(`${API_BASE}/companies`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Error al obtener empresas');
    return await res.json();
  } catch (error) {
    console.error('fetchCompanies error:', error);
    return [];
  }
}

export async function createCompany(data: {
  cif: string;
  razon_social: string;
  plan_cuentas_longitud: number;
  storage_base_path?: string;
  iva_periodicity?: string;
  modalidad_uso?: string;
  regimen_tributario?: string;
  software_destino?: string;
  domicilio_fiscal?: string | null;
  email_contacto?: string | null;
  telefono_contacto?: string | null;
}): Promise<Company> {
  const res = await fetch(`${API_BASE}/companies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al crear la empresa');
  }
  return await res.json();
}

export async function updateCompany(
  companyId: string,
  data: {
    razon_social?: string;
    plan_cuentas_longitud?: number;
    storage_base_path?: string;
    iva_periodicity?: string;
    modalidad_uso?: string;
    regimen_tributario?: string;
    software_destino?: string;
    domicilio_fiscal?: string | null;
    email_contacto?: string | null;
    telefono_contacto?: string | null;
    is_active?: boolean;
  }
): Promise<Company> {
  const res = await fetch(`${API_BASE}/companies/${companyId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al actualizar la empresa');
  }
  return await res.json();
}

export async function deleteCompany(companyId: string, cifConfirmation: string): Promise<any> {
  const query = new URLSearchParams({ cif_confirmation: cifConfirmation.trim() });
  const res = await fetch(`${API_BASE}/companies/${companyId}?${query.toString()}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al eliminar la empresa');
  }
  return await res.json();
}

// -------------------------------------------------------------
// PROVEEDORES
// -------------------------------------------------------------
export async function fetchSuppliers(companyId?: string): Promise<Supplier[]> {
  try {
    const url = companyId ? `${API_BASE}/suppliers?company_id=${companyId}` : `${API_BASE}/suppliers`;
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error('Error al obtener proveedores');
    return await res.json();
  } catch (error) {
    console.error('fetchSuppliers error:', error);
    return [];
  }
}

export async function createSupplier(data: {
  company_id: string;
  cif: string;
  nombre: string;
  subcuenta_proveedor: string;
  subcuenta_gasto_defecto: string;
}): Promise<Supplier> {
  const res = await fetch(`${API_BASE}/suppliers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al registrar el proveedor');
  }
  return await res.json();
}

// -------------------------------------------------------------
// PLAN CONTABLE PYME (SUBCUENTAS)
// -------------------------------------------------------------
export async function fetchAccounts(
  companyId: string,
  params?: {
    search?: string;
    tipo?: string;
    sort_by?: string;
    sort_order?: string;
    page?: number;
    page_size?: number;
  }
): Promise<AccountPaginatedResponse> {
  try {
    const query = new URLSearchParams();
    if (params?.search) query.append('search', params.search);
    if (params?.tipo && params.tipo !== 'ALL') query.append('tipo', params.tipo);
    if (params?.sort_by) query.append('sort_by', params.sort_by);
    if (params?.sort_order) query.append('sort_order', params.sort_order);
    if (params?.page) query.append('page', String(params.page));
    if (params?.page_size) query.append('page_size', String(params.page_size));

    const res = await fetch(`${API_BASE}/companies/${companyId}/accounts?${query.toString()}`, {
      cache: 'no-store',
    });
    if (!res.ok) throw new Error('Error al obtener cuentas');
    return await res.json();
  } catch (error) {
    console.error('fetchAccounts error:', error);
    return { total: 0, page: 1, page_size: 50, items: [] };
  }
}

export async function createAccount(
  companyId: string,
  data: { codigo: string; descripcion: string; tipo?: string; cif_asociado?: string }
): Promise<Account> {
  const res = await fetch(`${API_BASE}/companies/${companyId}/accounts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al crear la subcuenta');
  }
  return await res.json();
}

export async function updateAccount(
  companyId: string,
  accountId: string,
  data: { descripcion?: string; tipo?: string; cif_asociado?: string }
): Promise<Account> {
  const res = await fetch(`${API_BASE}/companies/${companyId}/accounts/${accountId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al actualizar la subcuenta');
  }
  return await res.json();
}

export async function deleteAccount(companyId: string, accountId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/companies/${companyId}/accounts/${accountId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al eliminar la subcuenta');
  }
  return await res.json();
}

export async function importChartOfAccounts(companyId: string, file: File): Promise<AccountImportSummary> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/companies/${companyId}/chart-of-accounts/import`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al importar catálogo de cuentas');
  }
  return await res.json();
}

export function getChartOfAccountsExportUrl(companyId: string): string {
  return `${API_BASE}/companies/${companyId}/chart-of-accounts/export`;
}

export async function seedChartOfAccounts(companyId: string): Promise<{ success: boolean; created_count: number; message: string }> {
  const res = await fetch(`${API_BASE}/companies/${companyId}/chart-of-accounts/seed`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al precargar el Plan General Contable');
  }
  return await res.json();
}

// -------------------------------------------------------------
// FACTURAS RECIBIDAS (GASTOS)
// -------------------------------------------------------------
export async function fetchInvoices(params?: {
  companyId?: string;
  status?: string;
  isProcessed?: boolean;
}): Promise<Invoice[]> {
  try {
    const query = new URLSearchParams();
    if (params?.companyId) query.append('company_id', params.companyId);
    if (params?.status) query.append('status', params.status);
    if (params?.isProcessed !== undefined) query.append('is_processed', String(params.isProcessed));

    const url = `${API_BASE}/invoices${query.toString() ? `?${query.toString()}` : ''}`;
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error('Error al listar facturas');
    return await res.json();
  } catch (error) {
    console.error('fetchInvoices error:', error);
    return [];
  }
}

export async function fetchInvoiceById(invoiceId: string): Promise<Invoice> {
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Factura no encontrada');
  return await res.json();
}

export async function uploadInvoice(file: File, companyId: string): Promise<Invoice> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('company_id', companyId);

  const res = await fetch(`${API_BASE}/invoices/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al procesar la factura');
  }

  return await res.json();
}

export async function updateInvoice(invoiceId: string, payload: InvoiceUpdatePayload): Promise<Invoice> {
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al actualizar la factura');
  }

  return await res.json();
}

export async function reprocessInvoice(invoiceId: string): Promise<Invoice> {
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/reprocess`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al reintentar la extracción con IA');
  }

  return await res.json();
}

export async function fetchProposedArchivePath(invoiceId: string): Promise<ProposedArchivePath> {
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/proposed-archive-path`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Error al obtener la ruta propuesta');
  return await res.json();
}

export async function approveInvoice(
  invoiceId: string,
  options?: { custom_subfolder?: string; custom_filename?: string }
): Promise<Invoice> {
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options || {}),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al aprobar y archivar la factura');
  }

  return await res.json();
}

export async function deleteInvoice(invoiceId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al eliminar la factura');
  }
  return await res.json();
}

export async function fetchInvoicePages(invoiceId: string): Promise<InvoicePagesResponse> {
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/pages`, { cache: 'no-store' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al obtener páginas del documento');
  }
  return await res.json();
}

export function getPageThumbnailUrl(invoiceId: string, pageNumber: number): string {
  return `${API_BASE}/invoices/${invoiceId}/pages/${pageNumber}/thumbnail`;
}

export async function splitInvoice(
  invoiceId: string,
  payload: SplitInvoiceRequest
): Promise<Invoice[]> {
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/split`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al disgregar el documento');
  }
  return await res.json();
}

export async function fetchNextSubaccount(
  companyId: string,
  prefix: string = '410'
): Promise<NextSubaccountResponse> {
  const query = new URLSearchParams({ prefix });
  const res = await fetch(`${API_BASE}/invoices/companies/${companyId}/next-subaccount?${query.toString()}`, {
    cache: 'no-store',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al obtener la siguiente subcuenta disponible');
  }
  return await res.json();
}

export async function bulkDeleteInvoices(invoiceIds: string[]): Promise<any> {
  const res = await fetch(`${API_BASE}/invoices/bulk-delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ invoice_ids: invoiceIds }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al eliminar facturas por lotes');
  }
  return await res.json();
}

// -------------------------------------------------------------
// CENTRO DE INTEGRACIONES Y ENLACE CONTABLE (A3, CONTASOL, SAGE, HOLDED)
// -------------------------------------------------------------
export async function fetchIntegrations(companyId: string): Promise<CompanyIntegration[]> {
  try {
    const res = await fetch(`${API_BASE}/companies/${companyId}/integrations`, { cache: 'no-store' });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function saveIntegration(
  companyId: string,
  data: { software_type: SoftwareType; is_active: boolean; configuration_json: Record<string, any> }
): Promise<CompanyIntegration> {
  const res = await fetch(`${API_BASE}/companies/${companyId}/integrations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al guardar la integración');
  }
  return await res.json();
}

export async function fetchExportBatches(companyId: string): Promise<ExportBatch[]> {
  try {
    const res = await fetch(`${API_BASE}/companies/${companyId}/export-batches`, { cache: 'no-store' });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function generateExportBatch(
  companyId: string,
  data: {
    software_type: SoftwareType;
    only_pending: boolean;
    invoice_ids?: string[];
    config_overrides?: Record<string, any>;
  }
): Promise<ExportBatch> {
  const res = await fetch(`${API_BASE}/companies/${companyId}/generate-export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al generar el lote contable');
  }
  return await res.json();
}

export function getBatchDownloadUrl(batchId: string): string {
  return `${API_BASE}/companies/batches/${batchId}/download`;
}

// -------------------------------------------------------------
// CONTACTOS (CRM CONTABLE)
// -------------------------------------------------------------
export async function fetchContacts(
  companyId: string,
  contactType?: string,
  search?: string
): Promise<Contact[]> {
  try {
    const query = new URLSearchParams();
    if (contactType && contactType !== 'ALL') query.append('contact_type', contactType);
    if (search) query.append('search', search);

    const res = await fetch(`${API_BASE}/companies/${companyId}/contacts?${query.toString()}`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function createContact(companyId: string, data: ContactCreatePayload): Promise<Contact> {
  const res = await fetch(`${API_BASE}/companies/${companyId}/contacts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al crear el contacto');
  }
  return await res.json();
}

export async function updateContact(contactId: string, data: Partial<ContactCreatePayload>): Promise<Contact> {
  const res = await fetch(`${API_BASE}/companies/contacts/${contactId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al actualizar contacto');
  }
  return await res.json();
}

export async function deleteContact(contactId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/companies/contacts/${contactId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al eliminar contacto');
  }
  return await res.json();
}

// -------------------------------------------------------------
// VENTAS Y FACTURACIÓN EMITIDA
// -------------------------------------------------------------
export async function fetchSalesInvoices(
  companyId: string,
  docType?: string,
  status?: string
): Promise<SalesInvoice[]> {
  try {
    const query = new URLSearchParams();
    if (docType && docType !== 'ALL') query.append('doc_type', docType);
    if (status && status !== 'ALL') query.append('status', status);

    const res = await fetch(`${API_BASE}/companies/${companyId}/sales-invoices?${query.toString()}`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function createSalesInvoice(
  companyId: string,
  data: SalesInvoiceCreatePayload
): Promise<SalesInvoice> {
  const res = await fetch(`${API_BASE}/companies/${companyId}/sales-invoices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al crear la factura de venta');
  }
  return await res.json();
}

export async function updateSalesInvoiceStatus(invoiceId: string, status: string): Promise<any> {
  const res = await fetch(`${API_BASE}/companies/sales-invoices/${invoiceId}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al cambiar estado de la factura');
  }
  return await res.json();
}

export async function deleteSalesInvoice(invoiceId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/companies/sales-invoices/${invoiceId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al eliminar la factura de venta');
  }
  return await res.json();
}

// -------------------------------------------------------------
// IMPUESTOS Y MODELOS TRIBUTARIOS (303, 111, 115, 347)
// -------------------------------------------------------------
export async function fetchTaxSummary(
  companyId: string,
  year: number = 2026,
  period: string = '1T'
): Promise<TaxSummaryResponse> {
  const query = new URLSearchParams({ year: String(year), period });
  const res = await fetch(`${API_BASE}/companies/${companyId}/taxes/summary?${query.toString()}`, {
    cache: 'no-store',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al calcular liquidación de impuestos');
  }
  return await res.json();
}

// -------------------------------------------------------------
// LIBRO DIARIO, MAYOR Y BALANCE DE SUMAS Y SALDOS
// -------------------------------------------------------------
export async function fetchJournalEntries(
  companyId: string,
  params?: { fromDate?: string; toDate?: string; search?: string }
): Promise<JournalResponse> {
  try {
    const query = new URLSearchParams();
    if (params?.fromDate) query.append('from_date', params.fromDate);
    if (params?.toDate) query.append('to_date', params.toDate);
    if (params?.search) query.append('search', params.search);

    const res = await fetch(`${API_BASE}/companies/${companyId}/journal?${query.toString()}`, {
      cache: 'no-store',
    });
    if (!res.ok) return { company_id: companyId, total_asientos: 0, total_apuntes: 0, asientos: [] };
    return await res.json();
  } catch {
    return { company_id: companyId, total_asientos: 0, total_apuntes: 0, asientos: [] };
  }
}

export async function fetchAccountLedger(
  companyId: string,
  subcuenta: string,
  params?: { fromDate?: string; toDate?: string }
): Promise<LedgerResponse> {
  const query = new URLSearchParams();
  if (params?.fromDate) query.append('from_date', params.fromDate);
  if (params?.toDate) query.append('to_date', params.toDate);

  const res = await fetch(`${API_BASE}/companies/${companyId}/ledger/${subcuenta}?${query.toString()}`, {
    cache: 'no-store',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al obtener extracto de mayor');
  }
  return await res.json();
}

export async function fetchTrialBalance(companyId: string): Promise<TrialBalanceResponse> {
  const res = await fetch(`${API_BASE}/companies/${companyId}/trial-balance`, {
    cache: 'no-store',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al calcular el balance de sumas y saldos');
  }
  return await res.json();
}

// -------------------------------------------------------------
// UTILIDADES Y EXPORTACIÓN LEGACY
// -------------------------------------------------------------
export function getFileUrl(filePath: string): string {
  if (!filePath) return '';
  const normalized = filePath.replace(/\\/g, '/');
  if (normalized.includes('/storage/')) {
    const sub = normalized.split('/storage/')[1];
    return `${BACKEND_BASE}/storage/${sub}`;
  }
  if (normalized.includes('/uploads/')) {
    const sub = normalized.split('/uploads/')[1];
    return `${BACKEND_BASE}/uploads/${sub}`;
  }
  return `${BACKEND_BASE}/${normalized}`;
}

export function getContasolExportUrl(companyId?: string): string {
  const query = companyId ? `?company_id=${companyId}` : '';
  return `${API_BASE}/exports/contasol${query}`;
}

export function getA3ExportUrl(companyId?: string, companyCode: string = '00001'): string {
  const query = new URLSearchParams();
  if (companyId) query.append('company_id', companyId);
  query.append('company_code', companyCode);
  return `${API_BASE}/exports/a3-suenlace?${query.toString()}`;
}

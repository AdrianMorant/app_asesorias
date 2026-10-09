export type TrafficLightStatus = 'GREEN' | 'YELLOW' | 'RED';

export interface TaxBreakdown {
  id?: string;
  tax_rate: number;
  tax_base: number;
  tax_amount: number;
}

export interface AccountingEntryLine {
  id?: string;
  entry_number: number;
  fecha: string;
  subcuenta: string;
  concepto: string;
  debe: number;
  haber: number;
  documento?: string;
  exported_to_erp?: boolean;
  export_batch_id?: string | null;
}

export type WorkflowStatus = 'a_revisar' | 'prevalidado' | 'validado' | 'contabilizado' | 'archivado';

export interface Invoice {
  id: string;
  company_id: string;
  supplier_id?: string | null;
  file_path: string;
  file_name: string;
  file_hash?: string;
  invoice_number: string;
  issue_date: string;
  fecha_contable?: string;
  due_date?: string | null;
  issuer_name: string;
  issuer_cif: string;
  recipient_name?: string | null;
  recipient_cif?: string | null;
  total_base: number;
  total_tax: number;
  total_retention: number;
  total_amount: number;
  currency: string;
  concept_summary?: string | null;
  is_rectificativa?: boolean;
  rectified_invoice_number?: string | null;
  rectified_invoice_date?: string | null;
  has_retention?: boolean;
  retention_percentage?: number;
  retention_model?: string;
  has_suplidos?: boolean;
  suplidos_amount?: number;
  suplidos_account?: string;
  postal_code?: string | null;
  country_code?: string;
  is_duplicate?: boolean;
  duplicate_of_id?: string | null;
  status: TrafficLightStatus;
  status_reasons: string[];
  workflow_status?: WorkflowStatus;
  es_multifactura?: boolean;
  num_paginas?: number;
  parent_invoice_id?: string | null;
  raw_extraction?: any;
  is_processed: boolean;
  exported_to_erp?: boolean;
  export_batch_id?: string | null;
  created_at: string;
  tax_breakdown: TaxBreakdown[];
  accounting_entries: AccountingEntryLine[];
}

export interface NextSubaccountResponse {
  next_subaccount: string;
  generic_subaccount: string;
  prefix: string;
  digits: number;
}

export interface PageThumbnail {
  page_number: number;
  thumbnail_url: string;
}

export interface InvoicePagesResponse {
  invoice_id: string;
  file_name: string;
  num_paginas: number;
  es_multifactura: boolean;
  pages: PageThumbnail[];
}

export interface SplitGroup {
  page_numbers: number[];
  custom_name?: string;
}

export interface SplitInvoiceRequest {
  splits: SplitGroup[];
}

export interface Company {
  id: string;
  cif: string;
  razon_social: string;
  plan_cuentas_longitud: number;
  storage_base_path: string;
  iva_periodicity?: 'Trimestral' | 'Mensual' | 'Anual';
  modalidad_uso?: 'erp_completo' | 'copiloto_contable';
  regimen_tributario?: 'general' | 'simplificado' | 'recargo_equivalencia' | 'exento' | string;
  software_destino?: 'a3' | 'contasol' | 'sage' | 'holded' | 'anfix' | 'cegid' | 'otro' | string;
  domicilio_fiscal?: string | null;
  email_contacto?: string | null;
  telefono_contacto?: string | null;
  is_active?: boolean;
  fecha_cierre_contable?: string | null;
  subcuenta_suplidos_defecto?: string | null;
  created_at: string;
}

export interface Supplier {
  id: string;
  company_id: string;
  cif: string;
  nombre: string;
  subcuenta_proveedor: string;
  subcuenta_gasto_defecto: string;
  created_at: string;
}

export interface Account {
  id: string;
  company_id: string;
  codigo: string;
  descripcion: string;
  tipo: string;
  cif_asociado?: string | null;
  debe_inicial?: number;
  haber_inicial?: number;
  debe_acumulado?: number;
  haber_acumulado?: number;
  saldo_actual?: number;
  tipo_saldo?: 'DEUDOR' | 'ACREEDOR' | 'CERO';
  created_at: string;
}

export interface AccountPaginatedResponse {
  total: number;
  page: number;
  page_size: number;
  items: Account[];
}

export interface AccountImportSummary {
  total_processed: number;
  created: number;
  updated: number;
  errors: string[];
}

export interface ProposedArchivePath {
  base_path: string;
  subfolder: string;
  filename: string;
  full_path: string;
}

export interface InvoiceUpdatePayload {
  supplier_id?: string;
  invoice_number?: string;
  issue_date?: string;
  due_date?: string;
  issuer_name?: string;
  issuer_cif?: string;
  total_base?: number;
  total_tax?: number;
  total_retention?: number;
  total_amount?: number;
  concept_summary?: string;
  is_processed?: boolean;
  fecha_contable?: string;
  is_rectificativa?: boolean;
  rectified_invoice_number?: string | null;
  rectified_invoice_date?: string | null;
  has_retention?: boolean;
  retention_percentage?: number;
  retention_model?: string;
  has_suplidos?: boolean;
  suplidos_amount?: number;
  suplidos_account?: string;
  postal_code?: string | null;
  country_code?: string;
}

// -------------------------------------------------------------
// NUEVOS TIPOS: CENTRO DE INTEGRACIONES Y ENLACE CONTABLE
// -------------------------------------------------------------
export type SoftwareType = 'A3' | 'CONTASOL' | 'SAGE' | 'HOLDED_API';

export interface CompanyIntegration {
  id: string;
  company_id: string;
  software_type: SoftwareType;
  is_active: boolean;
  configuration_json: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface ExportBatch {
  id: string;
  company_id: string;
  software_type: SoftwareType;
  file_format: string;
  entries_count: number;
  invoices_count: number;
  total_debe: number;
  total_haber: number;
  file_name?: string;
  file_path?: string;
  status: string;
  log_notes?: string;
  created_at: string;
}

// -------------------------------------------------------------
// NUEVOS TIPOS: CRM CONTABLE (CONTACTOS)
// -------------------------------------------------------------
export type ContactType = 'CLIENT' | 'SUPPLIER' | 'CREDITOR';

export interface Contact {
  id: string;
  company_id: string;
  contact_type: ContactType;
  cif: string;
  razon_social: string;
  nombre_comercial?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  postal_code?: string | null;
  city?: string | null;
  subcuenta_default?: string | null;
  payment_method: string;
  iban?: string | null;
  payment_terms_days?: string | null;
  notes?: string | null;
  total_invoiced?: number;
  created_at: string;
}

export interface ContactCreatePayload {
  contact_type: ContactType;
  cif: string;
  razon_social: string;
  nombre_comercial?: string;
  email?: string;
  phone?: string;
  address?: string;
  postal_code?: string;
  city?: string;
  subcuenta_default?: string;
  payment_method?: string;
  iban?: string;
  payment_terms_days?: string;
  notes?: string;
}

// -------------------------------------------------------------
// NUEVOS TIPOS: VENTAS Y FACTURACIÓN EMITIDA
// -------------------------------------------------------------
export type SalesDocType = 'INVOICE' | 'ESTIMATE' | 'PROFORMA';
export type SalesStatus = 'DRAFT' | 'ISSUED' | 'SENT' | 'PAID' | 'CANCELLED';

export interface SalesInvoiceLine {
  id?: string;
  description: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
  retention_rate: number;
  subtotal: number;
}

export interface SalesInvoiceTax {
  id?: string;
  tax_rate: number;
  tax_base: number;
  tax_amount: number;
}

export interface SalesInvoice {
  id: string;
  company_id: string;
  contact_id?: string | null;
  doc_type: SalesDocType;
  series: string;
  invoice_number: string;
  issue_date: string;
  due_date?: string | null;
  customer_name: string;
  customer_cif: string;
  customer_address?: string | null;
  total_base: number;
  total_tax: number;
  total_retention: number;
  total_amount: number;
  currency: string;
  status: SalesStatus;
  notes?: string | null;
  exported_to_erp: boolean;
  export_batch_id?: string | null;
  created_at: string;
  qr_image?: string | null;
  verifactu_hash?: string | null;
  lines: SalesInvoiceLine[];
  tax_breakdown: SalesInvoiceTax[];
}

export interface SalesInvoiceCreatePayload {
  doc_type: SalesDocType;
  series?: string;
  invoice_number?: string;
  contact_id?: string;
  customer_name: string;
  customer_cif: string;
  customer_address?: string;
  issue_date: string;
  due_date?: string;
  lines: {
    description: string;
    quantity: number;
    unit_price: number;
    tax_rate: number;
    retention_rate: number;
  }[];
  notes?: string;
}

// -------------------------------------------------------------
// NUEVOS TIPOS: FISCALIDAD E IMPUESTOS
// -------------------------------------------------------------
export interface TaxSummaryResponse {
  company_id: string;
  year: number;
  period: string;
  modelo_303: {
    periodo: string;
    ejercicio: number;
    devengado: {
      r21: { base: number; cuota: number };
      r10: { base: number; cuota: number };
      r4: { base: number; cuota: number };
      total_cuota: number;
    };
    deducible: {
      base_interior: number;
      cuota_interior: number;
      total_cuota: number;
    };
    resultado: number;
    tipo_resultado: 'A INGRESAR' | 'A COMPENSAR' | 'CERO';
  };
  modelo_111: {
    periodo: string;
    ejercicio: number;
    numero_perceptores: number;
    base_retenciones: number;
    importe_retenciones: number;
  };
  modelo_115: {
    periodo: string;
    ejercicio: number;
    numero_perceptores: number;
    base_retenciones: number;
    importe_retenciones: number;
  };
  modelo_347: {
    ejercicio: number;
    umbral_declarable: number;
    total_declarables: number;
    total_proximos: number;
    declarables: {
      cif: string;
      nombre: string;
      tipo: string;
      t1: number;
      t2: number;
      t3: number;
      t4: number;
      total_anual: number;
    }[];
    en_seguimiento: {
      cif: string;
      nombre: string;
      tipo: string;
      t1: number;
      t2: number;
      t3: number;
      t4: number;
      total_anual: number;
    }[];
  };
}

// -------------------------------------------------------------
// NUEVOS TIPOS: LIBROS CONTABLES PGC (DIARIO / MAYOR / SALDOS)
// -------------------------------------------------------------
export interface JournalEntryGroup {
  entry_number: number;
  fecha: string;
  documento?: string;
  exported_to_erp?: boolean;
  export_batch_id?: string | null;
  total_debe: number;
  total_haber: number;
  is_balanced: boolean;
  lines: {
    id: string;
    subcuenta: string;
    concepto: string;
    debe: number;
    haber: number;
    documento?: string;
    exported_to_erp?: boolean;
  }[];
}

export interface JournalResponse {
  company_id: string;
  total_asientos: number;
  total_apuntes: number;
  asientos: JournalEntryGroup[];
}

export interface LedgerMovement {
  id: string;
  entry_number: number;
  fecha: string;
  concepto: string;
  documento?: string;
  debe: number;
  haber: number;
  saldo_progresivo: number;
  signo: 'D' | 'H' | '0';
}

export interface LedgerResponse {
  company_id: string;
  subcuenta: string;
  descripcion: string;
  debe_inicial: number;
  haber_inicial: number;
  total_debe: number;
  total_haber: number;
  saldo_final: number;
  tipo_saldo: 'DEUDOR' | 'ACREEDOR' | 'CERO';
  movimientos: LedgerMovement[];
}

export interface TrialBalanceItem {
  codigo: string;
  descripcion: string;
  nivel: number;
  es_titulo: boolean;
  suma_debe: number;
  suma_haber: number;
  saldo_deudor: number;
  saldo_acreedor: number;
}

export interface TrialBalanceResponse {
  company_id: string;
  items: TrialBalanceItem[];
  totales: {
    suma_debe: number;
    suma_haber: number;
    saldo_deudor: number;
    saldo_acreedor: number;
    descuadre_sumas: number;
    descuadre_saldos: number;
    cuadrado: boolean;
  };
}

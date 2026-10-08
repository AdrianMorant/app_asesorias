'use client';

import React, { useState, useEffect } from 'react';
import { Company, Invoice, CompanyIntegration, ExportBatch, SoftwareType } from '@/types';
import {
  fetchIntegrations,
  saveIntegration,
  fetchExportBatches,
  generateExportBatch,
  getBatchDownloadUrl,
} from '@/lib/api';
import {
  Network,
  Download,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Layers,
  ArrowRight,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  FileSpreadsheet,
  Cpu,
  Key,
  FolderOpen,
  Info,
} from 'lucide-react';

interface IntegrationsViewProps {
  company: Company;
  invoices: Invoice[];
  onNotify: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
  onRefreshData?: () => void;
}

export const IntegrationsView: React.FC<IntegrationsViewProps> = ({
  company,
  invoices,
  onNotify,
  onRefreshData,
}) => {
  const [integrations, setIntegrations] = useState<CompanyIntegration[]>([]);
  const [batches, setBatches] = useState<ExportBatch[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [exporting, setExporting] = useState<boolean>(false);
  const [savingConfig, setSavingConfig] = useState<boolean>(false);

  // Software contable activo seleccionado para la empresa
  const [selectedSoftware, setSelectedSoftware] = useState<SoftwareType>('A3');
  const [onlyPending, setOnlyPending] = useState<boolean>(true);

  // Estados de configuración por conector
  const [a3Config, setA3Config] = useState({
    company_code: '00001',
    journal_code: '00',
    export_path: 'C:\\A3\\A3ASESOR\\DATOS',
  });

  const [contasolConfig, setContasolConfig] = useState({
    journal_code: '1',
    subaccount_digits: String(company.plan_cuentas_longitud || 9),
  });

  const [sageConfig, setSageConfig] = useState({
    channel: '0',
    sage_company_code: '001',
  });

  const [holdedConfig, setHoldedConfig] = useState({
    api_key: '',
    api_endpoint: 'https://api.holded.com/api/invoicing/v1/entries',
  });

  // Cargar integraciones y lotes históricos
  const loadData = async () => {
    setLoading(true);
    try {
      const [ints, bts] = await Promise.all([
        fetchIntegrations(company.id),
        fetchExportBatches(company.id),
      ]);
      setIntegrations(ints);
      setBatches(bts);

      // Cargar configuraciones guardadas
      const a3 = ints.find((i) => i.software_type === 'A3');
      if (a3 && a3.configuration_json) {
        setA3Config((prev) => ({ ...prev, ...a3.configuration_json }));
      }
      const csol = ints.find((i) => i.software_type === 'CONTASOL');
      if (csol && csol.configuration_json) {
        setContasolConfig((prev) => ({ ...prev, ...csol.configuration_json }));
      }
      const sage = ints.find((i) => i.software_type === 'SAGE');
      if (sage && sage.configuration_json) {
        setSageConfig((prev) => ({ ...prev, ...sage.configuration_json }));
      }
      const holded = ints.find((i) => i.software_type === 'HOLDED_API');
      if (holded && holded.configuration_json) {
        setHoldedConfig((prev) => ({ ...prev, ...holded.configuration_json }));
      }
    } catch {
      onNotify('error', 'Error al cargar la configuración de enlaces contables');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [company.id]);

  // Guardar configuración del conector activo
  const handleSaveConfig = async (swType: SoftwareType) => {
    setSavingConfig(true);
    let cfg: Record<string, any> = {};
    if (swType === 'A3') cfg = a3Config;
    if (swType === 'CONTASOL') cfg = contasolConfig;
    if (swType === 'SAGE') cfg = sageConfig;
    if (swType === 'HOLDED_API') cfg = holdedConfig;

    try {
      await saveIntegration(company.id, {
        software_type: swType,
        is_active: true,
        configuration_json: cfg,
      });
      onNotify('success', `Configuración de ${swType} guardada con éxito`);
      loadData();
    } catch (err: any) {
      onNotify('error', err.message || 'Error al guardar configuración');
    } finally {
      setSavingConfig(false);
    }
  };

  // Facturas y asientos candidatos para exportar
  const approvedInvoices = invoices.filter((inv) => inv.is_processed);
  const pendingInvoices = approvedInvoices.filter((inv) => !inv.exported_to_erp);
  const targetInvoices = onlyPending ? pendingInvoices : approvedInvoices;

  const redCountInBatch = targetInvoices.filter((inv) => inv.status === 'RED').length;
  const totalBatchAmount = targetInvoices.reduce((acc, inv) => acc + inv.total_amount, 0);

  // Ejecutar generación del lote
  const handleGenerateExport = async () => {
    if (targetInvoices.length === 0) {
      onNotify('info', 'No hay facturas aprobadas pendientes para exportar en este momento.');
      return;
    }

    if (redCountInBatch > 0) {
      onNotify(
        'error',
        `Bloqueo de seguridad: Hay ${redCountInBatch} factura(s) en Semáforo Rojo dentro del lote. Corrígelas antes de exportar.`,
        'Bloqueo Contable'
      );
      return;
    }

    setExporting(true);
    try {
      let overrides: Record<string, any> = {};
      if (selectedSoftware === 'A3') overrides = a3Config;
      if (selectedSoftware === 'CONTASOL') overrides = contasolConfig;
      if (selectedSoftware === 'SAGE') overrides = sageConfig;
      if (selectedSoftware === 'HOLDED_API') overrides = holdedConfig;

      const newBatch = await generateExportBatch(company.id, {
        software_type: selectedSoftware,
        only_pending: onlyPending,
        config_overrides: overrides,
      });

      onNotify(
        'success',
        `Lote contable ${newBatch.file_name || newBatch.id.slice(0, 8)} generado con éxito (${newBatch.entries_count} apuntes contables)`,
        'Exportación Completada'
      );

      // Si generó archivo descargable, iniciar descarga automática
      if (newBatch.file_path && newBatch.file_name) {
        window.open(getBatchDownloadUrl(newBatch.id), '_blank');
      }

      await loadData();
      if (onRefreshData) onRefreshData();
    } catch (err: any) {
      onNotify('error', err.message || 'Error al generar el lote contable', 'Fallo de Exportación');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Cabecera Principal */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <Network className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Centro de Conexiones y Enlace Contable
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Vincula la plataforma con el software contable de tu despacho o PYME (Wolters Kluwer A3,
            Contasol DELSOL, Sage 50 o APIs Cloud). Genera lotes auditables y previene duplicidades
            marcando automáticamente los asientos como exportados.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs text-slate-400">Software Seleccionado</div>
            <div className="text-sm font-bold text-indigo-700">{selectedSoftware}</div>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-semibold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Enlace Preparado
          </div>
        </div>
      </div>

      {/* Grid: Catálogo de Conectores Soportados */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* 1. Wolters Kluwer A3 */}
        <div
          onClick={() => setSelectedSoftware('A3')}
          className={`cursor-pointer rounded-xl border p-4 transition-all ${
            selectedSoftware === 'A3'
              ? 'bg-indigo-50/50 border-indigo-500 ring-2 ring-indigo-500/20 shadow-sm'
              : 'bg-white border-slate-200 hover:border-slate-300'
          }`}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
              A3ASESOR
            </span>
            <span className="text-[11px] text-slate-500 font-mono">SUENLACE.DAT</span>
          </div>
          <h3 className="font-bold text-slate-800 text-sm">Wolters Kluwer A3</h3>
          <p className="text-[11px] text-slate-500 mt-1">
            Enlace de longitud fija compatible con A3innuva, A3Eco y A3Con.
          </p>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-400">Tipo:</span>
            <span className="font-medium text-slate-700">Fichero Plano DAT</span>
          </div>
        </div>

        {/* 2. DELSOL Contasol */}
        <div
          onClick={() => setSelectedSoftware('CONTASOL')}
          className={`cursor-pointer rounded-xl border p-4 transition-all ${
            selectedSoftware === 'CONTASOL'
              ? 'bg-indigo-50/50 border-indigo-500 ring-2 ring-indigo-500/20 shadow-sm'
              : 'bg-white border-slate-200 hover:border-slate-300'
          }`}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
              CONTASOL
            </span>
            <span className="text-[11px] text-slate-500 font-mono">CSV Diario</span>
          </div>
          <h3 className="font-bold text-slate-800 text-sm">Software DELSOL</h3>
          <p className="text-[11px] text-slate-500 mt-1">
            Importación estructurada para el Diario General de Contasol.
          </p>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-400">Tipo:</span>
            <span className="font-medium text-slate-700">CSV Delimitado (;)</span>
          </div>
        </div>

        {/* 3. Sage 50 / Despachos */}
        <div
          onClick={() => setSelectedSoftware('SAGE')}
          className={`cursor-pointer rounded-xl border p-4 transition-all ${
            selectedSoftware === 'SAGE'
              ? 'bg-indigo-50/50 border-indigo-500 ring-2 ring-indigo-500/20 shadow-sm'
              : 'bg-white border-slate-200 hover:border-slate-300'
          }`}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800">
              SAGE
            </span>
            <span className="text-[11px] text-slate-500 font-mono">Plantilla</span>
          </div>
          <h3 className="font-bold text-slate-800 text-sm">Sage 50 / Despachos</h3>
          <p className="text-[11px] text-slate-500 mt-1">
            Plantilla oficial de asientos para Sage 50 y Despachos Connected.
          </p>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-400">Tipo:</span>
            <span className="font-medium text-slate-700">CSV Estructurado</span>
          </div>
        </div>

        {/* 4. Holded / Anfix Cloud */}
        <div
          onClick={() => setSelectedSoftware('HOLDED_API')}
          className={`cursor-pointer rounded-xl border p-4 transition-all ${
            selectedSoftware === 'HOLDED_API'
              ? 'bg-indigo-50/50 border-indigo-500 ring-2 ring-indigo-500/20 shadow-sm'
              : 'bg-white border-slate-200 hover:border-slate-300'
          }`}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-purple-100 text-purple-800">
              API CLOUD
            </span>
            <span className="text-[11px] text-slate-500 font-mono">REST JSON</span>
          </div>
          <h3 className="font-bold text-slate-800 text-sm">Holded / ERP Cloud</h3>
          <p className="text-[11px] text-slate-500 mt-1">
            Sincronización directa vía API Key sin archivos manuales intermediarios.
          </p>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-400">Tipo:</span>
            <span className="font-medium text-slate-700">Conexión API</span>
          </div>
        </div>
      </div>

      {/* Panel Detallado de Configuración y Generación de Lote */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Columna Izquierda: Configuración del software seleccionado */}
        <div className="lg:col-span-1 bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <FolderOpen className="w-4 h-4 text-indigo-600" />
              Parámetros de Enlace: {selectedSoftware}
            </h2>
            <button
              onClick={() => handleSaveConfig(selectedSoftware)}
              disabled={savingConfig}
              className="text-xs font-semibold px-2.5 py-1 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg transition-colors"
            >
              {savingConfig ? 'Guardando...' : 'Guardar'}
            </button>
          </div>

          {selectedSoftware === 'A3' && (
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-600 font-medium mb-1">
                  Código de Empresa en A3 (5 dígitos)
                </label>
                <input
                  type="text"
                  value={a3Config.company_code}
                  onChange={(e) => setA3Config({ ...a3Config, company_code: e.target.value })}
                  maxLength={5}
                  placeholder="00001"
                  className="w-full font-mono text-xs px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                />
                <span className="text-[10px] text-slate-400 mt-0.5 block">
                  Código numérico de la empresa cliente en A3ASESOR.
                </span>
              </div>
              <div>
                <label className="block text-slate-600 font-medium mb-1">Código de Diario A3</label>
                <input
                  type="text"
                  value={a3Config.journal_code}
                  onChange={(e) => setA3Config({ ...a3Config, journal_code: e.target.value })}
                  placeholder="00"
                  className="w-full font-mono text-xs px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-600 font-medium mb-1">
                  Ruta Local / Red donde A3 lee enlaces
                </label>
                <input
                  type="text"
                  value={a3Config.export_path}
                  onChange={(e) => setA3Config({ ...a3Config, export_path: e.target.value })}
                  placeholder="C:\A3\A3ASESOR\DATOS"
                  className="w-full text-xs px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
            </div>
          )}

          {selectedSoftware === 'CONTASOL' && (
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-600 font-medium mb-1">
                  Código de Diario Contasol
                </label>
                <input
                  type="text"
                  value={contasolConfig.journal_code}
                  onChange={(e) =>
                    setContasolConfig({ ...contasolConfig, journal_code: e.target.value })
                  }
                  placeholder="1"
                  className="w-full font-mono text-xs px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                />
                <span className="text-[10px] text-slate-400 mt-0.5 block">
                  1 = Diario General principal en DELSOL.
                </span>
              </div>
              <div>
                <label className="block text-slate-600 font-medium mb-1">
                  Longitud de Subcuenta
                </label>
                <input
                  type="text"
                  value={contasolConfig.subaccount_digits}
                  disabled
                  className="w-full bg-slate-50 font-mono text-xs px-3 py-2 border rounded-lg text-slate-500"
                />
                <span className="text-[10px] text-slate-400 mt-0.5 block">
                  Definida en la configuración de la empresa ({company.plan_cuentas_longitud} dígitos).
                </span>
              </div>
            </div>
          )}

          {selectedSoftware === 'SAGE' && (
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-600 font-medium mb-1">Canal de Diario Sage</label>
                <input
                  type="text"
                  value={sageConfig.channel}
                  onChange={(e) => setSageConfig({ ...sageConfig, channel: e.target.value })}
                  placeholder="0"
                  className="w-full font-mono text-xs px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-600 font-medium mb-1">
                  Código Empresa en Sage
                </label>
                <input
                  type="text"
                  value={sageConfig.sage_company_code}
                  onChange={(e) =>
                    setSageConfig({ ...sageConfig, sage_company_code: e.target.value })
                  }
                  placeholder="001"
                  className="w-full font-mono text-xs px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
            </div>
          )}

          {selectedSoftware === 'HOLDED_API' && (
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-600 font-medium mb-1 flex items-center gap-1">
                  <Key className="w-3.5 h-3.5 text-purple-600" /> API Key / Token Secreto
                </label>
                <input
                  type="password"
                  value={holdedConfig.api_key}
                  onChange={(e) => setHoldedConfig({ ...holdedConfig, api_key: e.target.value })}
                  placeholder="holded_sec_key_..."
                  className="w-full font-mono text-xs px-3 py-2 border rounded-lg focus:ring-1 focus:ring-purple-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-600 font-medium mb-1">API Endpoint</label>
                <input
                  type="text"
                  value={holdedConfig.api_endpoint}
                  onChange={(e) =>
                    setHoldedConfig({ ...holdedConfig, api_endpoint: e.target.value })
                  }
                  className="w-full text-xs px-3 py-2 border rounded-lg focus:ring-1 focus:ring-purple-500 outline-none"
                />
              </div>
            </div>
          )}

          <div className="p-3 bg-slate-50 rounded-lg text-[11px] text-slate-600 flex items-start gap-2 border border-slate-200">
            <Info className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
            <span>
              Los archivos generados se guardan con codificación oficial (CP1252 / ANSI) para
              garantizar que caracteres especiales y tildes se lean limpiamente en Windows.
            </span>
          </div>
        </div>

        {/* Columna Derecha: Panel de Acción y Generación de Lote */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-emerald-600" />
                Generación y Disparo del Lote Contable
              </h2>
              <span className="text-xs text-slate-500 font-medium">
                Destino:{' '}
                <strong className="text-indigo-600">{selectedSoftware}</strong>
              </span>
            </div>

            {/* Selector de ámbito */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div
                onClick={() => setOnlyPending(true)}
                className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                  onlyPending
                    ? 'border-indigo-500 bg-indigo-50/40 ring-1 ring-indigo-500'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-slate-800">
                    Solo Pendientes de Exportar
                  </span>
                  <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-indigo-100 text-indigo-700">
                    {pendingInvoices.length} docs
                  </span>
                </div>
                <p className="text-[11px] text-slate-500">
                  Recomendado. Excluye automáticamente documentos y asientos ya exportados para evitar
                  duplicidades.
                </p>
              </div>

              <div
                onClick={() => setOnlyPending(false)}
                className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                  !onlyPending
                    ? 'border-indigo-500 bg-indigo-50/40 ring-1 ring-indigo-500'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-slate-800">
                    Exportación Completa / Histórica
                  </span>
                  <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                    {approvedInvoices.length} docs
                  </span>
                </div>
                <p className="text-[11px] text-slate-500">
                  Exporta todas las facturas aprobadas de la empresa, incluidas las ya sincronizadas
                  anteriormente.
                </p>
              </div>
            </div>

            {/* Resumen numérico del lote */}
            <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 mb-4">
              <div className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                Resumen del Lote a Exportar
              </div>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <div className="text-lg font-bold font-mono text-slate-800">
                    {targetInvoices.length}
                  </div>
                  <div className="text-[11px] text-slate-400">Facturas en Lote</div>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <div className="text-lg font-bold font-mono text-indigo-700">
                    {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
                      totalBatchAmount
                    )}
                  </div>
                  <div className="text-[11px] text-slate-400">Total Importe</div>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <div
                    className={`text-lg font-bold font-mono ${
                      redCountInBatch > 0 ? 'text-rose-600' : 'text-emerald-600'
                    }`}
                  >
                    {redCountInBatch === 0 ? '100% Cuadrado' : `${redCountInBatch} con Errores`}
                  </div>
                  <div className="text-[11px] text-slate-400">Verificación Rigor</div>
                </div>
              </div>
            </div>

            {/* Alerta de bloqueo si hay facturas en ROJO */}
            {redCountInBatch > 0 && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-2 mb-4">
                <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                <div>
                  <strong>Bloqueo de Seguridad Contable Activado:</strong> Existen facturas en
                  estado Semáforo Rojo en este lote. Por rigor legal, la exportación está bloqueada
                  hasta que se verifiquen y aprueben.
                </div>
              </div>
            )}
          </div>

          {/* Botón de Generación y Descarga */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
            <div className="text-xs text-slate-500">
              {targetInvoices.length > 0 ? (
                <span className="flex items-center gap-1.5 text-emerald-700 font-medium">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  Listo para generar y registrar en auditoría
                </span>
              ) : (
                <span className="text-slate-400">No hay asientos pendientes para exportar.</span>
              )}
            </div>

            <button
              onClick={handleGenerateExport}
              disabled={exporting || targetInvoices.length === 0 || redCountInBatch > 0}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold text-white shadow-sm transition-all ${
                exporting || targetInvoices.length === 0 || redCountInBatch > 0
                  ? 'bg-slate-300 cursor-not-allowed text-slate-500'
                  : 'bg-indigo-600 hover:bg-indigo-700 active:scale-95 shadow-indigo-600/20'
              }`}
            >
              {exporting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Procesando Lote...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Generar y Descargar Lote {selectedSoftware}
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Historial de Exportaciones y Sincronizaciones */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200/80 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-600" />
              Historial de Exportaciones y Lotes Generados
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Trazabilidad completa de ficheros emitidos para auditoría fiscal.
            </p>
          </div>
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900 px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Actualizar
          </button>
        </div>

        {batches.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            Aún no se ha generado ningún lote contable para esta empresa.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-4">Fecha y Hora</th>
                  <th className="py-2.5 px-4">Software Destino</th>
                  <th className="py-2.5 px-4">Formato</th>
                  <th className="py-2.5 px-4 text-center">Apuntes</th>
                  <th className="py-2.5 px-4 text-center">Facturas</th>
                  <th className="py-2.5 px-4 text-right">Total Debe / Haber</th>
                  <th className="py-2.5 px-4">Estado</th>
                  <th className="py-2.5 px-4 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {batches.map((b) => (
                  <tr key={b.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4 font-mono text-slate-700">
                      {new Date(b.created_at).toLocaleString('es-ES', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-800">
                      <span className="inline-flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                        {b.software_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-500">{b.file_format}</td>
                    <td className="py-3 px-4 text-center font-mono font-medium">{b.entries_count}</td>
                    <td className="py-3 px-4 text-center font-mono font-medium">{b.invoices_count}</td>
                    <td className="py-3 px-4 text-right font-mono font-semibold text-slate-900">
                      {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
                        b.total_debe
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                          b.status === 'COMPLETED'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : b.status === 'SYNCED'
                            ? 'bg-purple-50 text-purple-700 border border-purple-200'
                            : 'bg-amber-50 text-amber-700'
                        }`}
                      >
                        <CheckCircle2 className="w-3 h-3" />
                        {b.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      {b.file_name ? (
                        <a
                          href={getBatchDownloadUrl(b.id)}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-semibold transition-colors"
                        >
                          <Download className="w-3 h-3" />
                          Descargar ({b.file_name})
                        </a>
                      ) : (
                        <span className="text-slate-400 text-[11px]">Sync API</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

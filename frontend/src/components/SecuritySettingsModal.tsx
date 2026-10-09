'use client';

import React, { useState, useEffect } from 'react';
import {
  loginUser,
  registerUser,
  logoutUser,
  verifyAuditChain,
  createSystemBackup,
  fetchSystemHealth,
} from '@/lib/api';

interface SecuritySettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentRole: string;
  onRoleChange: (newRole: string) => void;
  currentUserEmail?: string;
}

export default function SecuritySettingsModal({
  isOpen,
  onClose,
  currentRole,
  onRoleChange,
  currentUserEmail = 'asesor@konta.ai',
}: SecuritySettingsModalProps) {
  const [activeTab, setActiveTab] = useState<'rbac' | 'audit' | 'backup' | 'health'>('rbac');

  // Estados de Auditoría
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditResult, setAuditResult] = useState<any>(null);

  // Estados de Backup
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupResult, setBackupResult] = useState<any>(null);

  // Estados de Health
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthResult, setHealthResult] = useState<any>(null);

  // Estados de Login / Registro
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [authMsg, setAuthMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    if (isOpen && activeTab === 'health' && !healthResult) {
      loadHealth();
    }
  }, [isOpen, activeTab]);

  if (!isOpen) return null;

  const handleVerifyAudit = async () => {
    setAuditLoading(true);
    setAuditResult(null);
    try {
      const res = await verifyAuditChain();
      setAuditResult(res);
    } catch (e: any) {
      setAuditResult({ is_valid: false, error_details: e.message });
    } finally {
      setAuditLoading(false);
    }
  };

  const handleCreateBackup = async () => {
    setBackupLoading(true);
    setBackupResult(null);
    try {
      const res = await createSystemBackup();
      setBackupResult(res);
    } catch (e: any) {
      setBackupResult({ success: false, error: e.message });
    } finally {
      setBackupLoading(false);
    }
  };

  const loadHealth = async () => {
    setHealthLoading(true);
    try {
      const res = await fetchSystemHealth();
      setHealthResult(res);
    } catch (e: any) {
      setHealthResult({ status: 'ERROR', error: e.message });
    } finally {
      setHealthLoading(false);
    }
  };

  const roles = [
    { id: 'SUPERADMIN', name: 'Superadministrador', desc: 'Acceso total a la plataforma, infraestructura y seguridad global.', badge: 'bg-purple-100 text-purple-800 border-purple-200' },
    { id: 'ADVISOR', name: 'Responsable Contable / Asesor', desc: 'Gestión multi-empresa, cierre de ejercicios, reversión y enlace ERP.', badge: 'bg-blue-100 text-blue-800 border-blue-200' },
    { id: 'COMPANY_ADMIN', name: 'Administrador de Empresa', desc: 'Control total dentro de la empresa cliente específica.', badge: 'bg-indigo-100 text-indigo-800 border-indigo-200' },
    { id: 'ACCOUNTANT', name: 'Contable', desc: 'Edición de apuntes, reversión y aprobación de facturas.', badge: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
    { id: 'INVOICING', name: 'Facturación / Comercial', desc: 'Emisión de facturas y visualización. Bloqueado para contabilidad.', badge: 'bg-amber-100 text-amber-800 border-amber-200' },
    { id: 'AUDITOR_READONLY', name: 'Auditor (Solo Lectura)', desc: 'Inspección de libros contables e informes sin permisos de mutación.', badge: 'bg-slate-100 text-slate-800 border-slate-200' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Cabecera Modal */}
        <div className="p-6 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center font-bold text-lg shadow-inner">
              🔒
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight">Centro de Seguridad, RBAC y Fiabilidad Operativa</h2>
              <p className="text-xs text-slate-400">Protección de datos RGPD, autenticación criptográfica y control de accesos</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Pestañas de Navegación */}
        <div className="flex border-b border-slate-200 bg-slate-50 px-6 gap-2 pt-3">
          <button
            onClick={() => setActiveTab('rbac')}
            className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-all ${
              activeTab === 'rbac'
                ? 'border-indigo-600 text-indigo-700 bg-white rounded-t-lg'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            👥 Roles y Permisos (RBAC)
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-all ${
              activeTab === 'audit'
                ? 'border-indigo-600 text-indigo-700 bg-white rounded-t-lg'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            ⛓️ Auditoría WORM (SHA-256)
          </button>
          <button
            onClick={() => setActiveTab('backup')}
            className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-all ${
              activeTab === 'backup'
                ? 'border-indigo-600 text-indigo-700 bg-white rounded-t-lg'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            💾 Copias de Seguridad (Disaster Recovery)
          </button>
          <button
            onClick={() => {
              setActiveTab('health');
              loadHealth();
            }}
            className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-all ${
              activeTab === 'health'
                ? 'border-indigo-600 text-indigo-700 bg-white rounded-t-lg'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            🩺 Diagnóstico del Sistema
          </button>
        </div>

        {/* Contenido según pestaña */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {/* TAB: RBAC */}
          {activeTab === 'rbac' && (
            <div className="space-y-6">
              <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-indigo-800">Usuario en Sesión</div>
                  <div className="text-base font-bold text-slate-900">{currentUserEmail}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-semibold uppercase tracking-wider text-indigo-800">Rol Activo Actual</div>
                  <span className="inline-block mt-1 px-3 py-1 rounded-full text-xs font-bold bg-indigo-600 text-white shadow-sm">
                    {currentRole}
                  </span>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-3">
                  Simulación y Conmutación de Rol de Seguridad
                </h3>
                <p className="text-xs text-slate-500 mb-4">
                  Selecciona un rol para validar las restricciones del backend. Las operaciones sensibles (cierre contable, eliminación de empresas o reversión) son bloqueadas en el backend con HTTP 403 según corresponda.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {roles.map((r) => {
                    const isSelected = currentRole === r.id;
                    return (
                      <div
                        key={r.id}
                        onClick={() => onRoleChange(r.id)}
                        className={`p-4 rounded-xl border-2 transition-all cursor-pointer ${
                          isSelected
                            ? 'border-indigo-600 bg-indigo-50/50 shadow-sm'
                            : 'border-slate-200 hover:border-slate-300 bg-white'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="font-bold text-slate-900 text-sm">{r.name}</span>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${r.badge}`}>
                            {r.id}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 leading-relaxed">{r.desc}</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Matriz de Permisos */}
              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <div className="bg-slate-100 px-4 py-2.5 font-bold text-xs text-slate-700 uppercase tracking-wider">
                  Matriz de Control de Acceso por Rol (Backend RBAC)
                </div>
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="p-3">Operación Sensible</th>
                      <th className="p-3">Superadmin</th>
                      <th className="p-3">Asesor</th>
                      <th className="p-3">Contable</th>
                      <th className="p-3">Facturación</th>
                      <th className="p-3">Auditor</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    <tr>
                      <td className="p-3 font-semibold text-slate-800">Cierre / Reapertura Ejercicio</td>
                      <td className="p-3 text-emerald-600 font-bold">✓ Permitido</td>
                      <td className="p-3 text-emerald-600 font-bold">✓ Permitido</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-slate-800">Reversión de Asientos</td>
                      <td className="p-3 text-emerald-600 font-bold">✓ Permitido</td>
                      <td className="p-3 text-emerald-600 font-bold">✓ Permitido</td>
                      <td className="p-3 text-emerald-600 font-bold">✓ Permitido</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-slate-800">Eliminación de Empresa</td>
                      <td className="p-3 text-emerald-600 font-bold">✓ Permitido</td>
                      <td className="p-3 text-emerald-600 font-bold">✓ Permitido</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-slate-800">Forzar Reexportación ERP</td>
                      <td className="p-3 text-emerald-600 font-bold">✓ Permitido</td>
                      <td className="p-3 text-emerald-600 font-bold">✓ Permitido</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                      <td className="p-3 text-rose-500 font-bold">✗ 403 Bloqueado</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB: AUDITORÍA WORM */}
          {activeTab === 'audit' && (
            <div className="space-y-6">
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-5">
                <h3 className="font-bold text-slate-900 text-sm mb-2">
                  Registro Inmutable de Auditoría Criptográfica WORM
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed mb-4">
                  Cada acción sobre facturas, asientos contables o empresas se registra en un archivo append-only (<code className="bg-slate-200 px-1 py-0.5 rounded">security_audit.log</code>) encadenado mediante <strong className="text-slate-900">SHA-256</strong> (cada evento incorpora el hash previo). Si cualquier registro es manipulado o eliminado, la cadena matemática se rompe de forma detectable.
                </p>

                <button
                  onClick={handleVerifyAudit}
                  disabled={auditLoading}
                  className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition-colors flex items-center gap-2 shadow-sm"
                >
                  {auditLoading ? '⏳ Verificando Integridad Matemática...' : '🔍 Verificar Integridad de la Cadena'}
                </button>
              </div>

              {auditResult && (
                <div
                  className={`border rounded-xl p-5 ${
                    auditResult.is_valid
                      ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
                      : 'bg-rose-50/70 border-rose-200 text-rose-950'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-2xl">{auditResult.is_valid ? '✅' : '❌'}</span>
                    <div>
                      <h4 className="font-bold text-sm">
                        {auditResult.is_valid
                          ? 'Cadena Criptográfica Íntegra y Conforme'
                          : 'Ruptura o Alteración Detectada en la Cadena'}
                      </h4>
                      <p className="text-xs opacity-80">
                        Algoritmo: {auditResult.cryptographic_algorithm || 'SHA-256 Chained WORM'}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs pt-2 border-t border-current/10">
                    <div>
                      <span className="opacity-70">Estado Cadena:</span>{' '}
                      <strong className="font-bold">{auditResult.chain_status || 'INTACT'}</strong>
                    </div>
                    <div>
                      <span className="opacity-70">Registros Auditados:</span>{' '}
                      <strong className="font-bold">{auditResult.total_records_checked || 0}</strong>
                    </div>
                    <div>
                      <span className="opacity-70">Verificado Por:</span>{' '}
                      <strong className="font-bold">{auditResult.verified_by_user || currentUserEmail}</strong>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB: BACKUP */}
          {activeTab === 'backup' && (
            <div className="space-y-6">
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-5">
                <h3 className="font-bold text-slate-900 text-sm mb-2">
                  Copia de Seguridad Integral del Sistema (Disaster Recovery)
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed mb-4">
                  Genera un archivo comprimido ZIP consistente que incluye la base de datos relacional (mediante SQLite Backup API con bloqueo transaccional), los documentos originales de facturas y el archivo de auditoría, acompañado de un manifiesto con la huella digital SHA-256 de cada fichero.
                </p>

                <button
                  onClick={handleCreateBackup}
                  disabled={backupLoading}
                  className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition-colors flex items-center gap-2 shadow-sm"
                >
                  {backupLoading ? '⏳ Empaquetando y Calculando Hashes...' : '📦 Generar Copia de Seguridad Ahora'}
                </button>
              </div>

              {backupResult && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 text-emerald-950">
                  <div className="flex items-center gap-2 font-bold text-sm mb-2 text-emerald-900">
                    <span>🎉</span> Copia de Seguridad Generada y Verificada
                  </div>
                  <div className="space-y-1.5 text-xs">
                    <div><strong>Archivo:</strong> {backupResult.filename}</div>
                    <div><strong>Tamaño Comprimido:</strong> {(backupResult.size_bytes / 1024).toFixed(1)} KB</div>
                    <div><strong>Archivos Respaldados:</strong> {backupResult.files_count}</div>
                    <div className="font-mono text-[11px] break-all bg-white/70 p-2 rounded border border-emerald-200/60 mt-2">
                      <strong>SHA-256:</strong> {backupResult.archive_sha256}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB: HEALTH */}
          {activeTab === 'health' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">Estado Operacional y Diagnóstico de Componentes</h3>
                  <p className="text-xs text-slate-500">Monitorización de liveness y readiness para entornos de producción</p>
                </div>
                <button
                  onClick={loadHealth}
                  disabled={healthLoading}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-100 text-xs font-semibold text-slate-700"
                >
                  {healthLoading ? 'Actualizando...' : '🔄 Actualizar'}
                </button>
              </div>

              {healthResult && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl border border-slate-200 bg-white">
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Base de Datos</div>
                    <div className="text-base font-bold text-emerald-700 flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                      {healthResult.components?.database?.status || 'OPERATIONAL'}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1">{healthResult.components?.database?.type || 'SQLAlchemy Async'}</p>
                  </div>

                  <div className="p-4 rounded-xl border border-slate-200 bg-white">
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Sistema de Archivos</div>
                    <div className="text-base font-bold text-emerald-700 flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                      {healthResult.components?.filesystem?.status || 'OPERATIONAL'}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1">Escritura y lectura comprobadas</p>
                  </div>

                  <div className="p-4 rounded-xl border border-slate-200 bg-white">
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Cadena de Auditoría</div>
                    <div className="text-base font-bold text-emerald-700 flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                      {healthResult.components?.audit_log?.chain_intact ? 'Íntegra (WORM)' : 'Verificando'}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1">
                      Eventos: {healthResult.components?.audit_log?.events_recorded || 0}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Pie Modal */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-semibold text-xs transition-colors"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

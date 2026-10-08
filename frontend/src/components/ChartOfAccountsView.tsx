'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Company, Account } from '@/types';
import {
  fetchAccounts,
  createAccount,
  updateAccount,
  deleteAccount,
  importChartOfAccounts,
  getChartOfAccountsExportUrl,
  seedChartOfAccounts,
} from '@/lib/api';
import {
  Search,
  Plus,
  Upload,
  Download,
  Trash2,
  Edit2,
  AlertCircle,
  CheckCircle2,
  BookOpen,
  FileSpreadsheet,
  X,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Filter,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Sparkles,
  BookPlus,
  Scale,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';

interface Props {
  company: Company;
  notify: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
}

export const ChartOfAccountsView: React.FC<Props> = ({ company, notify }) => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [totalAccounts, setTotalAccounts] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [search, setSearch] = useState('');
  const [tipoFilter, setTipoFilter] = useState('ALL');
  const [sortBy, setSortBy] = useState<string>('codigo');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [loading, setLoading] = useState(false);

  // Modal para añadir/editar cuenta
  const [showAccountModal, setShowAccountModal] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [formCodigo, setFormCodigo] = useState('');
  const [formDescripcion, setFormDescripcion] = useState('');
  const [formTipo, setFormTipo] = useState('');
  const [formCif, setFormCif] = useState('');
  const [formDebeIni, setFormDebeIni] = useState<string>('0');
  const [formHaberIni, setFormHaberIni] = useState<string>('0');
  const [savingAccount, setSavingAccount] = useState(false);
  const [codeLengthError, setCodeLengthError] = useState<string | null>(null);

  // Modal para importación masiva Excel / CSV
  const [showImportModal, setShowImportModal] = useState(false);
  const [importing, setImporting] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSeedPGC = async () => {
    setSeeding(true);
    try {
      const res = await seedChartOfAccounts(company.id);
      notify(
        'success',
        `Se han incorporado ${res.created_count} subcuentas oficiales del PGC PYMES (${company.plan_cuentas_longitud} dígitos).`,
        'Plan Contable PYME'
      );
      await loadAccounts();
    } catch (err: any) {
      notify('error', err.message || 'Error al precargar catálogo PGC', 'Error');
    } finally {
      setSeeding(false);
    }
  };

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const res = await fetchAccounts(company.id, {
        search: search.trim() || undefined,
        tipo: tipoFilter !== 'ALL' ? tipoFilter : undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: pageSize,
      });
      setAccounts(res.items);
      setTotalAccounts(res.total);
    } catch (err: any) {
      notify('error', err.message || 'Error al cargar catálogo contable', 'Error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
  }, [company.id, page, tipoFilter, sortBy, sortOrder]);

  // Búsqueda con debounce ligero
  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      loadAccounts();
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Manejar cambio de ordenación en columnas
  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      // Por defecto descendente para importes/saldos, ascendente para texto
      if (['saldo', 'debe', 'haber'].includes(field)) {
        setSortOrder('desc');
      } else {
        setSortOrder('asc');
      }
    }
    setPage(1);
  };

  const renderSortIcon = (field: string) => {
    if (sortBy !== field) {
      return <ArrowUpDown className="w-3 h-3 text-slate-500 opacity-60 inline-block ml-1" />;
    }
    return sortOrder === 'asc' ? (
      <ArrowUp className="w-3 h-3 text-cyan-400 inline-block ml-1" />
    ) : (
      <ArrowDown className="w-3 h-3 text-cyan-400 inline-block ml-1" />
    );
  };

  // Validación de longitud en tiempo real
  const handleCodeChange = (val: string) => {
    const clean = val.replace(/\s+/g, '');
    setFormCodigo(clean);
    const expected = company.plan_cuentas_longitud || 9;
    if (clean.length > 0 && clean.length !== expected) {
      setCodeLengthError(
        `Longitud actual: ${clean.length} dígitos. Esta empresa requiere exactamente ${expected} dígitos.`
      );
    } else {
      setCodeLengthError(null);
    }
  };

  const handleOpenCreate = () => {
    setEditingAccount(null);
    setFormCodigo('');
    setFormDescripcion('');
    setFormTipo('');
    setFormCif('');
    setFormDebeIni('0');
    setFormHaberIni('0');
    setCodeLengthError(null);
    setShowAccountModal(true);
  };

  const handleOpenEdit = (acc: Account) => {
    setEditingAccount(acc);
    setFormCodigo(acc.codigo);
    setFormDescripcion(acc.descripcion);
    setFormTipo(acc.tipo);
    setFormCif(acc.cif_asociado || '');
    setFormDebeIni(String(acc.debe_acumulado || 0));
    setFormHaberIni(String(acc.haber_acumulado || 0));
    setCodeLengthError(null);
    setShowAccountModal(true);
  };

  const handleSaveAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    const expected = company.plan_cuentas_longitud || 9;

    if (!editingAccount && formCodigo.length !== expected) {
      notify('error', `El código debe tener exactamente ${expected} dígitos.`, 'Longitud Inválida');
      return;
    }

    setSavingAccount(true);
    try {
      if (editingAccount) {
        await updateAccount(company.id, editingAccount.id, {
          descripcion: formDescripcion.trim(),
          tipo: formTipo || undefined,
          cif_asociado: formCif.trim() || undefined,
        });
        notify('success', `Subcuenta ${formCodigo} actualizada.`, 'Cuenta Guardada');
      } else {
        await createAccount(company.id, {
          codigo: formCodigo.trim(),
          descripcion: formDescripcion.trim(),
          tipo: formTipo || undefined,
          cif_asociado: formCif.trim() || undefined,
        });
        notify('success', `Subcuenta ${formCodigo} creada correctamente.`, 'Cuenta Creada');
      }
      setShowAccountModal(false);
      await loadAccounts();
    } catch (err: any) {
      notify('error', err.message || 'Error al guardar la subcuenta', 'Error');
    } finally {
      setSavingAccount(false);
    }
  };

  const handleDeleteAccount = async (acc: Account) => {
    if (!window.confirm(`¿Seguro que deseas eliminar la subcuenta ${acc.codigo} - ${acc.descripcion}?`)) {
      return;
    }
    try {
      await deleteAccount(company.id, acc.id);
      notify('success', `Subcuenta ${acc.codigo} eliminada.`, 'Cuenta Eliminada');
      await loadAccounts();
    } catch (err: any) {
      notify('error', err.message || 'Error al eliminar la cuenta', 'Error');
    }
  };

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImporting(true);
    try {
      const summary = await importChartOfAccounts(company.id, file);
      notify(
        'success',
        `Importación completada: ${summary.created} creadas, ${summary.updated} actualizadas con sus saldos contables.`,
        'Plan Contable Importado'
      );
      if (summary.errors && summary.errors.length > 0) {
        notify('info', `Aviso: ${summary.errors.length} líneas omitidas por formato.`);
      }
      setShowImportModal(false);
      await loadAccounts();
    } catch (err: any) {
      notify('error', err.message || 'Error durante la importación', 'Error de Importación');
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const totalPages = Math.ceil(totalAccounts / pageSize) || 1;

  // Totales acumulados visibles en pantalla
  const sumDebe = accounts.reduce((acc, a) => acc + (a.debe_acumulado || 0), 0);
  const sumHaber = accounts.reduce((acc, a) => acc + (a.haber_acumulado || 0), 0);

  return (
    <div className="space-y-4">
      {/* Cabecera y Barra de Acciones */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-tight">
                Plan Contable PYME &amp; Libro Mayor
              </h2>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 font-semibold">
                {company.plan_cuentas_longitud} dígitos
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Gestión del cuadro de subcuentas, saldos contables en tiempo real y conciliación con apuntes del PGC.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={handleSeedPGC}
            disabled={seeding}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-500/30 transition shadow-sm"
            title="Añade las subcuentas oficiales del PGC PYMES que falten en el catálogo"
          >
            {seeding ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
            ) : (
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            )}
            <span>{seeding ? 'Precargando...' : 'Precargar Catálogo PGC'}</span>
          </button>
          <button
            type="button"
            onClick={handleOpenCreate}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white transition shadow shadow-cyan-950"
          >
            <Plus className="w-3.5 h-3.5" />
            Añadir Cuenta
          </button>
          <button
            type="button"
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            <Upload className="w-3.5 h-3.5 text-cyan-400" />
            Importar Excel/CSV
          </button>
          <a
            href={getChartOfAccountsExportUrl(company.id)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            <Download className="w-3.5 h-3.5 text-emerald-400" />
            Exportar CSV
          </a>
        </div>
      </div>

      {/* Mini-KPIs de Sumas y Saldos de la página actual */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-3 bg-slate-900/50 border border-slate-800 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <span className="text-xs text-slate-400 font-medium">Debe Acumulado Página:</span>
          </div>
          <span className="text-xs font-mono font-bold text-emerald-400">
            {sumDebe.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
          </span>
        </div>
        <div className="p-3 bg-slate-900/50 border border-slate-800 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-slate-400 font-medium">Haber Acumulado Página:</span>
          </div>
          <span className="text-xs font-mono font-bold text-purple-400">
            {sumHaber.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
          </span>
        </div>
        <div className="p-3 bg-slate-900/50 border border-slate-800 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-cyan-400" />
            <span className="text-xs text-slate-400 font-medium">Total Cuentas Filtradas:</span>
          </div>
          <span className="text-xs font-mono font-bold text-white">
            {totalAccounts} subcuentas
          </span>
        </div>
      </div>

      {/* Barra de Filtros, Búsqueda y Ordenación */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por código (ej. 629), descripción o CIF..."
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-950 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        {/* Filtros de Tipos de Cuenta PGC */}
        <div className="flex items-center gap-1.5 flex-wrap text-xs">
          {[
            { id: 'ALL', label: 'Todas' },
            { id: 'GASTO', label: 'Gastos (6XX)' },
            { id: 'INGRESO', label: 'Ingresos (7XX)' },
            { id: 'PROVEEDOR', label: 'Proveedores (400)' },
            { id: 'ACREEDOR', label: 'Acreedores (410)' },
            { id: 'CLIENTE', label: 'Clientes (430)' },
            { id: 'TRIBUTARIO', label: 'Impuestos (47X)' },
            { id: 'FINANCIERO', label: 'Financiero (5XX)' },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setTipoFilter(t.id);
                setPage(1);
              }}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                tipoFilter === t.id
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-semibold'
                  : 'text-slate-400 hover:text-slate-200 bg-slate-950/50'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tabla de Cuentas con Columnas Contables y Ordenación */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/70 text-[11px] text-slate-400 uppercase tracking-wider select-none">
                <th
                  onClick={() => handleSort('codigo')}
                  className="py-3 px-4 font-semibold cursor-pointer hover:text-white transition"
                >
                  <span>Código</span>
                  {renderSortIcon('codigo')}
                </th>
                <th
                  onClick={() => handleSort('descripcion')}
                  className="py-3 px-4 font-semibold cursor-pointer hover:text-white transition"
                >
                  <span>Descripción Contable</span>
                  {renderSortIcon('descripcion')}
                </th>
                <th className="py-3 px-3 font-semibold">Tipo PGC</th>
                <th className="py-3 px-3 font-semibold">CIF Asociado</th>
                <th
                  onClick={() => handleSort('debe')}
                  className="py-3 px-4 font-semibold text-right cursor-pointer hover:text-white transition"
                >
                  <span>Debe Acum. (€)</span>
                  {renderSortIcon('debe')}
                </th>
                <th
                  onClick={() => handleSort('haber')}
                  className="py-3 px-4 font-semibold text-right cursor-pointer hover:text-white transition"
                >
                  <span>Haber Acum. (€)</span>
                  {renderSortIcon('haber')}
                </th>
                <th
                  onClick={() => handleSort('saldo')}
                  className="py-3 px-4 font-semibold text-right cursor-pointer hover:text-cyan-300 transition"
                >
                  <span>Saldo Actual (€)</span>
                  {renderSortIcon('saldo')}
                </th>
                <th className="py-3 px-4 font-semibold text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    <Loader2 className="w-6 h-6 mx-auto animate-spin text-cyan-400 mb-2" />
                    Cargando cuentas contables y saldos acumulados...
                  </td>
                </tr>
              ) : accounts.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    <BookOpen className="w-10 h-10 mx-auto opacity-30 text-slate-400 mb-2" />
                    <p className="text-sm font-medium">No hay cuentas contables registradas</p>
                    <p className="text-xs text-slate-500 mt-1">
                      Usa el botón &quot;Añadir Cuenta&quot;, &quot;Precargar Catálogo PGC&quot; o importa tu balance de Contasol / A3 en Excel o CSV.
                    </p>
                  </td>
                </tr>
              ) : (
                accounts.map((acc) => {
                  const typeColors: Record<string, string> = {
                    GASTO: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
                    INGRESO: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
                    PROVEEDOR: 'bg-blue-500/10 text-blue-300 border-blue-500/30',
                    ACREEDOR: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30',
                    CLIENTE: 'bg-purple-500/10 text-purple-300 border-purple-500/30',
                    FINANCIERO: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
                    TRIBUTARIO: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
                  };
                  const colorClass = typeColors[acc.tipo] || 'bg-slate-800 text-slate-400 border-slate-700';

                  const debeVal = acc.debe_acumulado || 0;
                  const haberVal = acc.haber_acumulado || 0;
                  const saldoVal = acc.saldo_actual || 0;
                  const tipoSaldo = acc.tipo_saldo || 'CERO';

                  return (
                    <tr key={acc.id} className="hover:bg-slate-850/50 transition-colors">
                      {/* Código */}
                      <td className="py-3 px-4 font-mono font-bold text-cyan-400 text-xs">
                        {acc.codigo}
                      </td>
                      {/* Descripción */}
                      <td className="py-3 px-4 font-medium text-slate-200">
                        {acc.descripcion}
                      </td>
                      {/* Tipo */}
                      <td className="py-3 px-3">
                        <span
                          className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded-full border ${colorClass}`}
                        >
                          {acc.tipo}
                        </span>
                      </td>
                      {/* CIF Asociado */}
                      <td className="py-3 px-3 font-mono text-slate-400">
                        {acc.cif_asociado || '-'}
                      </td>
                      {/* Debe Acumulado (€) */}
                      <td className="py-3 px-4 text-right font-mono text-slate-300">
                        {debeVal > 0 ? (
                          <span>{debeVal.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €</span>
                        ) : (
                          <span className="text-slate-600">0,00 €</span>
                        )}
                      </td>
                      {/* Haber Acumulado (€) */}
                      <td className="py-3 px-4 text-right font-mono text-slate-300">
                        {haberVal > 0 ? (
                          <span>{haberVal.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €</span>
                        ) : (
                          <span className="text-slate-600">0,00 €</span>
                        )}
                      </td>
                      {/* Saldo Actual (€) con indicador Deudor/Acreedor */}
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5 font-mono">
                          <span
                            className={`font-bold ${
                              tipoSaldo === 'DEUDOR'
                                ? 'text-emerald-300'
                                : tipoSaldo === 'ACREEDOR'
                                ? 'text-purple-300'
                                : 'text-slate-500'
                            }`}
                          >
                            {saldoVal.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
                          </span>
                          {tipoSaldo === 'DEUDOR' && (
                            <span
                              className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                              title="Saldo Deudor (Debe > Haber)"
                            >
                              D
                            </span>
                          )}
                          {tipoSaldo === 'ACREEDOR' && (
                            <span
                              className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40"
                              title="Saldo Acreedor (Haber > Debe)"
                            >
                              H
                            </span>
                          )}
                          {tipoSaldo === 'CERO' && (
                            <span className="text-[10px] text-slate-600" title="Cuenta Saldada">
                              0
                            </span>
                          )}
                        </div>
                      </td>
                      {/* Acciones */}
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => handleOpenEdit(acc)}
                            className="p-1 rounded-lg text-slate-400 hover:text-cyan-400 hover:bg-slate-800 transition"
                            title="Editar cuenta"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteAccount(acc)}
                            className="p-1 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition"
                            title="Eliminar cuenta"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Paginación */}
        {totalPages > 1 && (
          <div className="p-3.5 bg-slate-950/60 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <div>
              Mostrando {accounts.length} de {totalAccounts} cuentas (Orden: <strong className="text-white font-mono">{sortBy} {sortOrder}</strong>)
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                className="p-1.5 rounded-lg border border-slate-800 disabled:opacity-40 hover:bg-slate-800 transition"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-mono text-white">
                Página {page} de {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                className="p-1.5 rounded-lg border border-slate-800 disabled:opacity-40 hover:bg-slate-800 transition"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* MODAL CREAR / EDITAR CUENTA */}
      {showAccountModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md shadow-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-cyan-400" />
                {editingAccount ? 'Editar Subcuenta Contable' : 'Nueva Subcuenta Contable'}
              </h3>
              <button
                type="button"
                onClick={() => setShowAccountModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveAccount} className="space-y-4 text-xs">
              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                  Código de Subcuenta
                </label>
                <input
                  type="text"
                  required
                  disabled={!!editingAccount}
                  value={formCodigo}
                  onChange={(e) => handleCodeChange(e.target.value)}
                  placeholder={`Ej. 629000001 (${company.plan_cuentas_longitud} dígitos)`}
                  className={`w-full px-3 py-2 bg-slate-950 border rounded-xl text-white font-mono text-xs focus:outline-none ${
                    codeLengthError
                      ? 'border-rose-500 focus:border-rose-400'
                      : 'border-slate-700 focus:border-cyan-500'
                  }`}
                />
                {codeLengthError && (
                  <p className="text-[11px] text-rose-400 mt-1 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3 shrink-0" />
                    {codeLengthError}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                  Descripción Contable
                </label>
                <input
                  type="text"
                  required
                  value={formDescripcion}
                  onChange={(e) => setFormDescripcion(e.target.value)}
                  placeholder="Ej. Suministros oficina o Telefónica SL"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                    Tipo de Cuenta
                  </label>
                  <select
                    value={formTipo}
                    onChange={(e) => setFormTipo(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
                  >
                    <option value="">Autodetectar por PGC</option>
                    <option value="GASTO">Gasto (6XX)</option>
                    <option value="INGRESO">Ingreso (7XX)</option>
                    <option value="PROVEEDOR">Proveedor (400)</option>
                    <option value="ACREEDOR">Acreedor (410)</option>
                    <option value="CLIENTE">Cliente (430)</option>
                    <option value="TRIBUTARIO">Impuestos (47X)</option>
                    <option value="FINANCIERO">Financiero (5XX)</option>
                    <option value="OTRO">Otro</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                    CIF / NIF (Opcional)
                  </label>
                  <input
                    type="text"
                    value={formCif}
                    onChange={(e) => setFormCif(e.target.value)}
                    placeholder="B12345674"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white font-mono text-xs focus:outline-none focus:border-cyan-500 uppercase"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAccountModal(false)}
                  className="px-3 py-1.5 font-medium text-slate-400 hover:text-white transition"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={savingAccount || (!editingAccount && !!codeLengthError)}
                  className="px-4 py-2 font-semibold rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white transition shadow shadow-cyan-950"
                >
                  {savingAccount ? 'Guardando...' : editingAccount ? 'Guardar Cambios' : 'Crear Subcuenta'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL IMPORTADOR EXCEL / CSV */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md shadow-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <FileSpreadsheet className="w-4 h-4 text-cyan-400" />
                Importar Plan Contable (Excel / CSV)
              </h3>
              <button
                type="button"
                onClick={() => setShowImportModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-400 mb-4 leading-relaxed">
              Sube el balance de sumas y saldos o catálogo de cuentas exportado de <strong className="text-white">Contasol, A3ASESOR o Sage</strong>.
              El sistema detectará automáticamente las columnas de código, descripción, CIF y <strong className="text-cyan-300">columnas de Debe, Haber o Saldo</strong> para calcular el balance.
            </p>

            <div
              onClick={() => !importing && fileInputRef.current?.click()}
              className="border-2 border-dashed border-slate-700 hover:border-cyan-400 rounded-xl p-8 text-center cursor-pointer bg-slate-950/60 transition"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                onChange={handleImportFile}
                disabled={importing}
                className="hidden"
              />
              {importing ? (
                <div className="flex flex-col items-center gap-2">
                  <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
                  <span className="text-xs font-semibold text-white">Importando y sincronizando catálogo y saldos...</span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <Upload className="w-8 h-8 text-cyan-400" />
                  <span className="text-xs font-semibold text-white">Selecciona o arrastra tu archivo Excel / CSV</span>
                  <span className="text-[11px] text-slate-500">Formatos admitidos: .xlsx, .xls, .csv con columnas de saldo opcionales</span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end mt-4">
              <button
                type="button"
                onClick={() => setShowImportModal(false)}
                className="px-3 py-1.5 text-xs text-slate-400 hover:text-white"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

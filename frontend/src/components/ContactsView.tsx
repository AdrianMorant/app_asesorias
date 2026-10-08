'use client';

import React, { useState, useEffect } from 'react';
import { Company, Contact, ContactType } from '@/types';
import { fetchContacts, createContact, updateContact, deleteContact } from '@/lib/api';
import {
  Users,
  Plus,
  Search,
  Building,
  Mail,
  Phone,
  CreditCard,
  Trash2,
  Edit2,
  X,
  CheckCircle2,
  Filter,
} from 'lucide-react';

interface ContactsViewProps {
  company: Company;
  onNotify: (type: 'success' | 'error' | 'info', message: string, title?: string) => void;
}

export const ContactsView: React.FC<ContactsViewProps> = ({ company, onNotify }) => {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [contactTypeFilter, setContactTypeFilter] = useState<'ALL' | 'CLIENT' | 'SUPPLIER'>('ALL');
  const [search, setSearch] = useState<string>('');

  // Modal Crear / Editar
  const [showModal, setShowModal] = useState<boolean>(false);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Campos formulario
  const [formData, setFormData] = useState({
    contact_type: 'CLIENT' as ContactType,
    cif: '',
    razon_social: '',
    nombre_comercial: '',
    email: '',
    phone: '',
    address: '',
    postal_code: '',
    city: '',
    subcuenta_default: '',
    payment_method: 'Transferencia',
    iban: '',
    payment_terms_days: 'Contado',
    notes: '',
  });

  const loadContacts = async () => {
    setLoading(true);
    try {
      const data = await fetchContacts(company.id, contactTypeFilter, search);
      setContacts(data);
    } catch {
      onNotify('error', 'Error al cargar el directorio de contactos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadContacts();
  }, [company.id, contactTypeFilter]);

  const handleOpenCreate = () => {
    setEditingContact(null);
    setFormData({
      contact_type: 'CLIENT',
      cif: '',
      razon_social: '',
      nombre_comercial: '',
      email: '',
      phone: '',
      address: '',
      postal_code: '',
      city: '',
      subcuenta_default: '',
      payment_method: 'Transferencia',
      iban: '',
      payment_terms_days: 'Contado',
      notes: '',
    });
    setShowModal(true);
  };

  const handleOpenEdit = (c: Contact) => {
    setEditingContact(c);
    setFormData({
      contact_type: c.contact_type,
      cif: c.cif,
      razon_social: c.razon_social,
      nombre_comercial: c.nombre_comercial || '',
      email: c.email || '',
      phone: c.phone || '',
      address: c.address || '',
      postal_code: c.postal_code || '',
      city: c.city || '',
      subcuenta_default: c.subcuenta_default || '',
      payment_method: c.payment_method || 'Transferencia',
      iban: c.iban || '',
      payment_terms_days: c.payment_terms_days || 'Contado',
      notes: c.notes || '',
    });
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.cif.trim() || !formData.razon_social.trim()) {
      onNotify('error', 'Indique al menos el CIF y la Razón Social');
      return;
    }

    setSubmitting(true);
    try {
      if (editingContact) {
        await updateContact(editingContact.id, formData);
        onNotify('success', 'Contacto actualizado con éxito');
      } else {
        await createContact(company.id, formData);
        onNotify('success', 'Contacto creado con éxito y subcuenta asignada');
      }
      setShowModal(false);
      loadContacts();
    } catch (err: any) {
      onNotify('error', err.message || 'Error al guardar el contacto');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('¿Eliminar este contacto del CRM?')) return;
    try {
      await deleteContact(id);
      onNotify('success', 'Contacto eliminado');
      loadContacts();
    } catch (err: any) {
      onNotify('error', err.message || 'Error al eliminar');
    }
  };

  return (
    <div className="space-y-6">
      {/* Cabecera */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <Users className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Contactos y CRM Contable
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Directorio unificado de Clientes (Cuentas 430.X) y Proveedores / Acreedores (Cuentas 400.X / 410.X) con
            validación de CIF, asignación de subcuenta contable PGC y condiciones de pago.
          </p>
        </div>

        <button
          onClick={handleOpenCreate}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm transition-all"
        >
          <Plus className="w-4 h-4" />
          Nuevo Contacto
        </button>
      </div>

      {/* Filtros y Buscador */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs font-medium">
          <button
            onClick={() => setContactTypeFilter('ALL')}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              contactTypeFilter === 'ALL'
                ? 'bg-white text-slate-900 font-bold shadow-sm'
                : 'text-slate-600'
            }`}
          >
            Todos ({contacts.length})
          </button>
          <button
            onClick={() => setContactTypeFilter('CLIENT')}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              contactTypeFilter === 'CLIENT'
                ? 'bg-white text-slate-900 font-bold shadow-sm'
                : 'text-slate-600'
            }`}
          >
            Clientes (430)
          </button>
          <button
            onClick={() => setContactTypeFilter('SUPPLIER')}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              contactTypeFilter === 'SUPPLIER'
                ? 'bg-white text-slate-900 font-bold shadow-sm'
                : 'text-slate-600'
            }`}
          >
            Proveedores (400/410)
          </button>
        </div>

        <div className="relative w-full md:w-72">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadContacts()}
            placeholder="Buscar por CIF o Razón Social..."
            className="w-full text-xs pl-8 pr-3 py-2 border border-slate-200 rounded-lg outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
          />
        </div>
      </div>

      {/* Tabla de Contactos */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        {contacts.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-xs">
            No se han encontrado contactos en el directorio.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-4">CIF / NIF</th>
                  <th className="py-2.5 px-4">Razón Social</th>
                  <th className="py-2.5 px-4">Tipo</th>
                  <th className="py-2.5 px-4">Subcuenta PGC</th>
                  <th className="py-2.5 px-4">Forma de Pago</th>
                  <th className="py-2.5 px-4">Contacto</th>
                  <th className="py-2.5 px-4 text-right">Facturado Acum.</th>
                  <th className="py-2.5 px-4 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {contacts.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-slate-800">{c.cif}</td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900">{c.razon_social}</div>
                      {c.nombre_comercial && (
                        <div className="text-[11px] text-slate-400">{c.nombre_comercial}</div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          c.contact_type === 'CLIENT'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        }`}
                      >
                        {c.contact_type === 'CLIENT' ? 'Cliente' : 'Proveedor'}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-indigo-700">
                      {c.subcuenta_default || '-'}
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      {c.payment_method} ({c.payment_terms_days || 'Contado'})
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-[11px]">
                      {c.email && <div>{c.email}</div>}
                      {c.phone && <div>{c.phone}</div>}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                      {Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(
                        c.total_invoiced || 0
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleOpenEdit(c)}
                          title="Editar Contacto"
                          className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-slate-100 rounded"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(c.id)}
                          title="Eliminar Contacto"
                          className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal Crear / Editar Contacto */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-xl my-8 overflow-hidden">
            <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <h3 className="font-bold text-slate-900 text-sm">
                {editingContact ? 'Editar Contacto' : 'Nuevo Contacto (Cliente / Proveedor)'}
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-600 font-medium mb-1">Tipo de Contacto</label>
                  <select
                    value={formData.contact_type}
                    onChange={(e) =>
                      setFormData({ ...formData, contact_type: e.target.value as ContactType })
                    }
                    className="w-full px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                  >
                    <option value="CLIENT">Cliente (Cuenta 430)</option>
                    <option value="SUPPLIER">Proveedor (Cuenta 400)</option>
                    <option value="CREDITOR">Acreedor de Servicios (Cuenta 410)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-600 font-medium mb-1">CIF / NIF *</label>
                  <input
                    type="text"
                    required
                    value={formData.cif}
                    onChange={(e) => setFormData({ ...formData, cif: e.target.value })}
                    placeholder="B12345678"
                    className="w-full font-mono uppercase px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-600 font-medium mb-1">Razón Social *</label>
                <input
                  type="text"
                  required
                  value={formData.razon_social}
                  onChange={(e) => setFormData({ ...formData, razon_social: e.target.value })}
                  placeholder="Empresa o Profesional SL"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-600 font-medium mb-1">Nombre Comercial</label>
                  <input
                    type="text"
                    value={formData.nombre_comercial}
                    onChange={(e) =>
                      setFormData({ ...formData, nombre_comercial: e.target.value })
                    }
                    className="w-full px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-600 font-medium mb-1">
                    Subcuenta Contable PGC
                  </label>
                  <input
                    type="text"
                    value={formData.subcuenta_default}
                    onChange={(e) =>
                      setFormData({ ...formData, subcuenta_default: e.target.value })
                    }
                    placeholder="Dejar vacío para auto-asignar"
                    className="w-full font-mono px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-600 font-medium mb-1">Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-600 font-medium mb-1">Teléfono</label>
                  <input
                    type="text"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-600 font-medium mb-1">Forma de Pago</label>
                  <select
                    value={formData.payment_method}
                    onChange={(e) => setFormData({ ...formData, payment_method: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                  >
                    <option value="Transferencia">Transferencia</option>
                    <option value="Domiciliación">Domiciliación</option>
                    <option value="Recibo">Recibo Bancario</option>
                    <option value="Tarjeta">Tarjeta</option>
                    <option value="Efectivo">Efectivo</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-600 font-medium mb-1">Plazo de Pago</label>
                  <select
                    value={formData.payment_terms_days}
                    onChange={(e) =>
                      setFormData({ ...formData, payment_terms_days: e.target.value })
                    }
                    className="w-full px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                  >
                    <option value="Contado">Contado</option>
                    <option value="30 días">30 días</option>
                    <option value="60 días">60 días</option>
                    <option value="90 días">90 días</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-600 font-medium mb-1">IBAN Bancario</label>
                  <input
                    type="text"
                    value={formData.iban}
                    onChange={(e) => setFormData({ ...formData, iban: e.target.value })}
                    placeholder="ES00..."
                    className="w-full font-mono uppercase px-3 py-2 border rounded-lg focus:ring-1 focus:ring-indigo-500 outline-none"
                  />
                </div>
              </div>

              <div className="pt-4 border-t border-slate-200 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border rounded-lg text-slate-600 hover:bg-slate-50 font-medium"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold shadow-sm"
                >
                  {submitting ? 'Guardando...' : 'Guardar Contacto'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

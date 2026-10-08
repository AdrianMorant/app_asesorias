'use client';

import React from 'react';
import {
  X,
  BookOpen,
  Building2,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileSpreadsheet,
  Download,
  FolderTree,
  Sparkles,
} from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const ManualModal: React.FC<Props> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden my-auto">
        {/* Cabecera */}
        <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <BookOpen className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                Manual Operativo: Copiloto Contable con IA
              </h2>
              <p className="text-xs text-slate-400">Guía de uso rápido para el equipo de asesoría</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
            title="Cerrar manual (Esc)"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Contenido scrolleable */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-300">
          {/* 1. OBJETIVO */}
          <div className="bg-cyan-950/20 border border-cyan-800/30 rounded-xl p-4">
            <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              1. ¿Qué es este sistema y para qué sirve?
            </h3>
            <p className="text-slate-300 leading-relaxed">
              Plataforma diseñada para <strong className="text-white">eliminar el tecleo manual de facturas</strong>:
            </p>
            <ol className="list-decimal list-inside space-y-1 mt-2 text-slate-300">
              <li>Extrae los datos fiscales y aritméticos de los documentos (PDFs o imágenes).</li>
              <li>Valida la coherencia fiscal mediante un motor de semáforo.</li>
              <li>Genera automáticamente el asiento contable en partida doble adaptado a las subcuentas de cada empresa.</li>
              <li>Archiva el documento en la carpeta organizada del cliente.</li>
              <li>Permite exportar los asientos en bloque para importarlos en 2 segundos en A3 o Contasol.</li>
            </ol>
          </div>

          {/* 2. FLUJO EN 4 PASOS */}
          <div>
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-3">
              2. Flujo de Trabajo en 4 Pasos
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Paso 1 */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3.5 space-y-1.5">
                <div className="flex items-center gap-2 font-bold text-slate-100">
                  <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-300 text-[11px] flex items-center justify-center">1</span>
                  <Building2 className="w-4 h-4 text-cyan-400" />
                  Seleccionar la Empresa
                </div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  En el desplegable superior, selecciona la empresa cliente. Cada empresa tiene configurada su longitud de plan contable (8, 9 o 10 dígitos) y su histórico de proveedores.
                </p>
              </div>

              {/* Paso 2 */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3.5 space-y-1.5">
                <div className="flex items-center gap-2 font-bold text-slate-100">
                  <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-300 text-[11px] flex items-center justify-center">2</span>
                  <UploadCloud className="w-4 h-4 text-cyan-400" />
                  Cargar las Facturas
                </div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Arrastra uno o varios archivos (PDF, PNG, JPG) a la zona central. La IA leerá emisor, CIF, número, fecha, desgloses multi-IVA y retenciones IRPF.
                </p>
              </div>
            </div>

            {/* Paso 3: Semáforo detallado */}
            <div className="mt-3 bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-2 font-bold text-slate-100">
                <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-300 text-[11px] flex items-center justify-center">3</span>
                Triaje Semafórico (Revisión)
              </div>

              <div className="space-y-2">
                {/* Verde */}
                <div className="p-2.5 rounded-lg bg-emerald-950/25 border border-emerald-800/40 text-emerald-200">
                  <div className="font-bold flex items-center gap-1.5 text-[11px]">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    🟢 VERDE (Lista para contabilizar)
                  </div>
                  <p className="text-[11px] text-slate-300 mt-1">
                    El NIF es válido, los importes cuadran al céntimo y el proveedor ya está fichado con sus cuentas asignadas. Puedes aprobarla directamente o dejar que se auto-contabilice.
                  </p>
                </div>

                {/* Amarillo */}
                <div className="p-2.5 rounded-lg bg-amber-950/25 border border-amber-800/40 text-amber-200">
                  <div className="font-bold flex items-center gap-1.5 text-[11px]">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    🟡 AMARILLO (Revisión en 1 clic)
                  </div>
                  <p className="text-[11px] text-slate-300 mt-1">
                    <strong>Motivos:</strong> Proveedor nuevo o importe superior a 3.000 € (control Modelo 347). Haz clic en la factura para abrir la consola de triaje. Asigna o confirma la subcuenta de proveedor (<code className="text-amber-300">40000000X</code>) y la de gasto (<code className="text-amber-300">62900000X</code>) y pulsa <strong>Guardar y Aprobar</strong>. El sistema recordará estas cuentas para futuras facturas.
                  </p>
                </div>

                {/* Rojo */}
                <div className="p-2.5 rounded-lg bg-rose-950/25 border border-rose-800/40 text-rose-200">
                  <div className="font-bold flex items-center gap-1.5 text-[11px]">
                    <XCircle className="w-3.5 h-3.5 text-rose-400" />
                    🔴 ROJO (Bloqueo preventivo)
                  </div>
                  <p className="text-[11px] text-slate-300 mt-1">
                    <strong>Motivos:</strong> Factura duplicada, CIF no válido según la AEAT o descuadre matemático (<code className="text-rose-300">Base + IVA - IRPF != Total</code>). Entra en triaje para ver el error exacto señalado, corrige el dato y pulsa <strong>Guardar</strong>.
                  </p>
                </div>
              </div>
            </div>

            {/* Paso 4: Exportación */}
            <div className="mt-3 bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-2">
              <div className="flex items-center gap-2 font-bold text-slate-100">
                <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-300 text-[11px] flex items-center justify-center">4</span>
                Exportación al Software Contable
              </div>
              <p className="text-slate-400 text-[11px]">
                Una vez aprobadas las facturas, haz clic en el botón superior según el programa de tu puesto:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] pt-1">
                <div className="p-2.5 rounded-lg bg-blue-950/20 border border-blue-800/30">
                  <span className="font-bold text-blue-300 flex items-center gap-1.5">
                    <FileSpreadsheet className="w-3.5 h-3.5" />
                    Botón &quot;Contasol CSV&quot;
                  </span>
                  <p className="text-slate-400 mt-1">
                    Descarga el diario general para importar en Software DELSOL vía: <em>Diario &gt; Importaciones / Archivo de texto</em>.
                  </p>
                </div>
                <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-800/30">
                  <span className="font-bold text-emerald-300 flex items-center gap-1.5">
                    <Download className="w-3.5 h-3.5" />
                    Botón &quot;A3 SUENLACE&quot;
                  </span>
                  <p className="text-slate-400 mt-1">
                    Descarga el fichero estándar <code className="text-emerald-300">SUENLACE.DAT</code> para Wolters Kluwer vía: <em>Utilidades &gt; Enlace Contable / Importación de asientos</em>.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* 3. ARCHIVADO DIGITAL */}
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <FolderTree className="w-4 h-4 text-cyan-400" />
              3. ¿Dónde se guardan las facturas originales?
            </h3>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Al pulsar <strong className="text-white">Aprobar y Archivar</strong>, el sistema renombra el archivo y lo mueve automáticamente a la estructura organizada en servidor:
            </p>
            <div className="p-2.5 rounded-lg bg-black/40 border border-slate-800 font-mono text-[11px] text-cyan-300">
              storage / [CIF_EMPRESA] / [AÑO] / [TRIMESTRE] / recibidas /
            </div>
            <p className="text-[11px] text-slate-400">
              Nombre de archivo estandarizado: <code className="text-slate-200">AAAA-MM-DD_CIF_NumeroFactura.pdf</code>. No es necesario descargar ni renombrar archivos a mano.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-950 border-t border-slate-800 flex items-center justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white transition shadow"
          >
            Entendido, volver a la aplicación
          </button>
        </div>
      </div>
    </div>
  );
};

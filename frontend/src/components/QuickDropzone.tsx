'use client';

import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Scissors,
  X,
  FileCheck2,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { uploadInvoice } from '@/lib/api';
import { Invoice } from '@/types';

interface QuickDropzoneProps {
  companyId: string;
  onInvoiceUploaded: (newInvoice: Invoice) => void;
  onOpenSplitter?: (invoice: Invoice) => void;
  compact?: boolean;
}

interface QueuedFile {
  id: string;
  name: string;
  size: number;
  status: 'uploading' | 'extracting' | 'done' | 'error';
  progress: number;
  error?: string;
  invoice?: Invoice;
}

export const QuickDropzone: React.FC<QuickDropzoneProps> = ({
  companyId,
  onInvoiceUploaded,
  onOpenSplitter,
  compact = false,
}) => {
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [queue, setQueue] = useState<QueuedFile[]>([]);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const processFiles = async (files: FileList | File[]) => {
    if (!companyId) {
      setGlobalError('Por favor, selecciona o crea una empresa antes de subir facturas.');
      return;
    }
    setGlobalError(null);

    const fileList = Array.from(files);
    const newItems: QueuedFile[] = fileList.map((f, idx) => ({
      id: `${Date.now()}-${idx}-${f.name}`,
      name: f.name,
      size: f.size,
      status: 'uploading',
      progress: 25,
    }));

    setQueue((prev) => [...newItems, ...prev]);

    // Procesar cada archivo en paralelo o secuencia rápida
    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      const item = newItems[i];

      // Simular progreso de carga antes de llamada
      updateItemProgress(item.id, 50, 'extracting');

      try {
        const uploadedInvoice = await uploadInvoice(file, companyId);
        updateItemSuccess(item.id, uploadedInvoice);
        onInvoiceUploaded(uploadedInvoice);
      } catch (err: any) {
        updateItemError(item.id, err.message || `Error procesando ${file.name}`);
      }
    }
  };

  const updateItemProgress = (id: string, progress: number, status: QueuedFile['status']) => {
    setQueue((prev) =>
      prev.map((item) => (item.id === id ? { ...item, progress, status } : item))
    );
  };

  const updateItemSuccess = (id: string, invoice: Invoice) => {
    setQueue((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, progress: 100, status: 'done', invoice }
          : item
      )
    );
  };

  const updateItemError = (id: string, errorMessage: string) => {
    setQueue((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, status: 'error', error: errorMessage }
          : item
      )
    );
  };

  const removeQueueItem = (id: string) => {
    setQueue((prev) => prev.filter((item) => item.id !== id));
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await processFiles(e.dataTransfer.files);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await processFiles(e.target.files);
    }
  };

  const isUploadingAny = queue.some(
    (item) => item.status === 'uploading' || item.status === 'extracting'
  );

  return (
    <div className="w-full space-y-3">
      {/* Zona Drag and Drop con Efecto Halo y Animación */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploadingAny && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl text-center cursor-pointer transition-all duration-300 overflow-hidden ${
          compact ? 'p-5' : 'p-8'
        } ${
          isDragging
            ? 'border-cyan-400 bg-cyan-950/30 scale-[1.01] shadow-xl shadow-cyan-500/20 ring-4 ring-cyan-400/20'
            : 'border-slate-700/80 bg-slate-900/40 hover:bg-slate-900/80 hover:border-cyan-500/50 hover:shadow-lg hover:shadow-cyan-500/5'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,image/png,image/jpeg,image/jpg,image/webp"
          className="hidden"
          onChange={handleFileChange}
          disabled={isUploadingAny}
        />

        {/* Resplandor decorativo en dragover */}
        {isDragging && (
          <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 via-blue-500/10 to-emerald-500/10 animate-pulse pointer-events-none" />
        )}

        <div className="flex flex-col items-center justify-center space-y-3 relative z-10">
          <div
            className={`rounded-2xl flex items-center justify-center transition-all ${
              compact ? 'w-10 h-10' : 'w-14 h-14'
            } ${
              isDragging
                ? 'bg-cyan-500 text-slate-950 scale-110 shadow-lg shadow-cyan-500/30 animate-bounce'
                : 'bg-gradient-to-tr from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 text-cyan-400'
            }`}
          >
            {isUploadingAny ? (
              <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
            ) : (
              <UploadCloud className={compact ? 'w-5 h-5' : 'w-7 h-7'} />
            )}
          </div>

          <div>
            <h4 className="text-sm sm:text-base font-bold text-white tracking-tight">
              {isDragging ? (
                <span className="text-cyan-300">¡Suelta tus facturas aquí para ingesta inmediata!</span>
              ) : (
                <>
                  Arrastra tus facturas aquí o{' '}
                  <span className="text-cyan-400 underline hover:text-cyan-300 font-semibold">
                    explora archivos
                  </span>
                </>
              )}
            </h4>
            <p className="text-xs text-slate-400 mt-1">
              Admite <strong>PDF, PNG, JPG y JPEG</strong> (carga múltiple simultánea con visión Gemini)
            </p>
          </div>

          <div className="flex items-center gap-2 pt-1 text-[11px] text-slate-400">
            <span className="flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              Lectura OCR Multimodal
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              Detector Multifactura MF
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <FileCheck2 className="w-3.5 h-3.5 text-emerald-400" />
              Validación CIF AEAT
            </span>
          </div>
        </div>
      </div>

      {/* Error Global */}
      {globalError && (
        <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between gap-2 animate-in fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{globalError}</span>
          </div>
          <button
            onClick={() => setGlobalError(null)}
            className="text-rose-400 hover:text-rose-200"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Cola de Procesamiento y Feedback de Carga */}
      {queue.length > 0 && (
        <div className="space-y-2 pt-2">
          <div className="flex items-center justify-between text-xs text-slate-400 px-1">
            <span className="font-semibold text-slate-300">
              Actividad de Ingesta Reciente ({queue.length})
            </span>
            <button
              onClick={() => setQueue([])}
              className="text-[11px] text-slate-400 hover:text-white underline"
            >
              Limpiar cola
            </button>
          </div>

          <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
            {queue.map((item) => (
              <div
                key={item.id}
                className={`p-3 rounded-xl border text-xs flex flex-col gap-2 transition-all ${
                  item.status === 'done'
                    ? 'bg-slate-850/80 border-slate-750'
                    : item.status === 'error'
                    ? 'bg-rose-950/30 border-rose-500/40'
                    : 'bg-slate-900 border-cyan-500/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="w-4 h-4 text-cyan-400 shrink-0" />
                    <span className="font-semibold text-white truncate max-w-[200px] sm:max-w-xs">
                      {item.name}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      ({formatFileSize(item.size)})
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {item.status === 'uploading' && (
                      <span className="text-cyan-400 font-medium text-[11px] flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Subiendo...
                      </span>
                    )}

                    {item.status === 'extracting' && (
                      <span className="text-amber-400 font-medium text-[11px] flex items-center gap-1">
                        <Sparkles className="w-3 h-3 animate-spin" />
                        Analizando IA...
                      </span>
                    )}

                    {item.status === 'done' && (
                      <span className="text-emerald-400 font-semibold text-[11px] flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        Procesada
                      </span>
                    )}

                    {item.status === 'error' && (
                      <span className="text-rose-400 font-semibold text-[11px] flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
                        Error
                      </span>
                    )}

                    <button
                      onClick={() => removeQueueItem(item.id)}
                      className="p-1 text-slate-400 hover:text-white rounded"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Barra de progreso visual si está activo */}
                {(item.status === 'uploading' || item.status === 'extracting') && (
                  <div className="w-full bg-slate-800 h-1 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-cyan-400 transition-all duration-300"
                      style={{ width: `${item.progress}%` }}
                    />
                  </div>
                )}

                {/* Mensaje de error si falló */}
                {item.status === 'error' && item.error && (
                  <p className="text-[11px] text-rose-300 pl-6">
                    {item.error}
                  </p>
                )}

                {/* Alerta interactiva si se detecta multifactura */}
                {item.status === 'done' && item.invoice && item.invoice.es_multifactura && (
                  <div className="mt-1 p-2 rounded-lg bg-indigo-950/60 border border-indigo-500/30 text-[11px] text-indigo-200 flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 font-medium">
                      <Scissors className="w-3.5 h-3.5 text-indigo-400" />
                      Documento compuesto multifactura detectado.
                    </span>
                    {onOpenSplitter && (
                      <button
                        onClick={() => onOpenSplitter(item.invoice!)}
                        className="px-2 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-[10px] flex items-center gap-1 transition-colors"
                      >
                        <span>Abrir Maquetador MF</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

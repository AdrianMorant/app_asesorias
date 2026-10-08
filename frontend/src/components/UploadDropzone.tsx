'use client';

import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { uploadInvoice } from '@/lib/api';
import { Invoice } from '@/types';

interface Props {
  companyId: string;
  onInvoiceUploaded: (newInvoice: Invoice) => void;
}

export const UploadDropzone: React.FC<Props> = ({ companyId, onInvoiceUploaded }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [currentFile, setCurrentFile] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFiles = async (files: FileList | File[]) => {
    if (!companyId) {
      setError('Por favor, selecciona o crea una empresa antes de subir facturas.');
      return;
    }
    setError(null);
    setUploading(true);

    const fileList = Array.from(files);
    for (const file of fileList) {
      try {
        setCurrentFile(file.name);
        const result = await uploadInvoice(file, companyId);
        onInvoiceUploaded(result);
      } catch (err: any) {
        setError(err.message || `Error procesando ${file.name}`);
      }
    }

    setUploading(false);
    setCurrentFile(null);
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

  return (
    <div className="w-full">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-300 ${
          isDragging
            ? 'border-cyan-400 bg-cyan-950/20 scale-[1.01]'
            : 'border-slate-700/80 bg-slate-900/40 hover:bg-slate-900/80 hover:border-slate-600'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,image/png,image/jpeg,image/jpg,image/webp"
          className="hidden"
          onChange={handleFileChange}
          disabled={uploading}
        />

        <div className="flex flex-col items-center justify-center space-y-3">
          {uploading ? (
            <>
              <div className="w-14 h-14 rounded-full bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center animate-spin">
                <Loader2 className="w-7 h-7 text-cyan-400" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white">
                  Analizando documento con LLM Multimodal...
                </h4>
                <p className="text-xs text-cyan-400 font-mono mt-1">
                  {currentFile}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Extrayendo datos fiscales, validando NIF/CIF y evaluando reglas de semáforo...
                </p>
              </div>
            </>
          ) : (
            <>
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 flex items-center justify-center group-hover:scale-105 transition-transform">
                <UploadCloud className="w-7 h-7 text-cyan-400" />
              </div>
              <div>
                <h4 className="text-base font-semibold text-white">
                  Arrastra tus facturas aquí o <span className="text-cyan-400 hover:underline">explora archivos</span>
                </h4>
                <p className="text-xs text-slate-400 mt-1">
                  Formatos compatibles: PDF, PNG, JPG, JPEG (Extracción inteligente automática con Gemini / GPT-4o)
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-3 p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};

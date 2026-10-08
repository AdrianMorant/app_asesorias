'use client';

import React, { useState } from 'react';
import {
  ZoomIn,
  ZoomOut,
  RotateCw,
  Maximize2,
  ExternalLink,
  FileText,
  RefreshCw,
} from 'lucide-react';

interface Props {
  fileUrl: string;
  fileName: string;
}

export const PDFViewer: React.FC<Props> = ({ fileUrl, fileName }) => {
  const [zoom, setZoom] = useState<number>(100);
  const [rotation, setRotation] = useState<number>(0);
  const [isImage, setIsImage] = useState<boolean>(false);

  // Comprobar extensión
  React.useEffect(() => {
    const ext = fileName.toLowerCase().split('.').pop();
    setIsImage(['jpg', 'jpeg', 'png', 'webp', 'gif'].includes(ext || ''));
  }, [fileName]);

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 20, 200));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 20, 60));
  const handleRotate = () => setRotation((prev) => (prev + 90) % 360);
  const handleReset = () => {
    setZoom(100);
    setRotation(0);
  };

  return (
    <div className="flex flex-col h-full bg-slate-950/80 rounded-xl border border-slate-800 overflow-hidden shadow-2xl">
      {/* Barra de herramientas superior */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 backdrop-blur-md">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-4 h-4 text-cyan-400 shrink-0" />
          <span className="text-xs font-medium text-slate-300 truncate max-w-[220px]" title={fileName}>
            {fileName || 'Documento no cargado'}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleZoomOut}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Reducir zoom"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <span className="text-[11px] font-mono text-slate-400 w-10 text-center select-none">
            {zoom}%
          </span>
          <button
            type="button"
            onClick={handleZoomIn}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Aumentar zoom"
          >
            <ZoomIn className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-slate-800 mx-1" />

          <button
            type="button"
            onClick={handleRotate}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Rotar 90°"
          >
            <RotateCw className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={handleReset}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Restablecer vista"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-400 hover:bg-slate-800 transition-colors ml-1"
            title="Abrir en pestaña nueva"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* Área del visor del documento */}
      <div className="flex-1 overflow-auto bg-slate-900/40 relative flex items-center justify-center p-4">
        {!fileUrl ? (
          <div className="text-center p-8 text-slate-500">
            <FileText className="w-12 h-12 mx-auto mb-2 opacity-40 text-slate-600" />
            <p className="text-sm">No hay documento asociado para visualizar</p>
          </div>
        ) : isImage ? (
          <div
            className="transition-transform duration-200 ease-out origin-center"
            style={{
              transform: `scale(${zoom / 100}) rotate(${rotation}deg)`,
            }}
          >
            <img
              src={fileUrl}
              alt={fileName}
              className="max-w-full max-h-[80vh] object-contain rounded shadow-lg border border-slate-700/50"
            />
          </div>
        ) : (
          <div
            className="w-full h-full min-h-[500px] transition-transform duration-200 origin-top"
            style={{
              transform: `scale(${zoom / 100}) rotate(${rotation}deg)`,
              transformOrigin: 'top center',
            }}
          >
            <iframe
              src={`${fileUrl}#toolbar=0&navpanes=0`}
              title="Visor PDF"
              className="w-full h-full min-h-[650px] rounded border border-slate-800 bg-white"
            />
          </div>
        )}
      </div>
    </div>
  );
};

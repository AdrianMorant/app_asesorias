'use client';

import React from 'react';
import { QuickDropzone } from './QuickDropzone';
import { Invoice } from '@/types';

interface Props {
  companyId: string;
  onInvoiceUploaded: (newInvoice: Invoice) => void;
  onOpenSplitter?: (invoice: Invoice) => void;
  compact?: boolean;
}

export const UploadDropzone: React.FC<Props> = (props) => {
  return <QuickDropzone {...props} />;
};

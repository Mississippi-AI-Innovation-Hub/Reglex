import { useState, useCallback } from 'react';
import axios from 'axios';

interface PDFState {
  url: string | null;
  page: number;
  docName: string;
  state: string;
  agencyType: string;
  isLoading: boolean;
  error: string | null;
  width: number;
}

export function usePDF(docsEndpoint: string, apiKey?: string) {
  const [pdfState, setPdfState] = useState<PDFState>({
    url: null,
    page: 1,
    docName: '',
    state: '',
    agencyType: '',
    isLoading: false,
    error: null,
    width: 900,
  });

  const openPage = useCallback(async (
    document: string,
    page: number,
    state?: string,
    agencyType?: string,
  ) => {
    setPdfState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      url: null,
      docName: document,
      state: state || '',
      agencyType: agencyType || '',
      page,
    }));

    if (!docsEndpoint) {
      setPdfState(prev => ({
        ...prev,
        error: 'Docs endpoint not configured.',
        isLoading: false,
      }));
      return;
    }

    try {
      const response = await axios.post(
        docsEndpoint,
        {
          filename: document,
          ...(state ? { state } : {}),
          ...(agencyType ? { agency_type: agencyType } : {}),
        },
        {
          headers: {
            'Content-Type': 'application/json',
            ...(apiKey ? { 'x-api-key': apiKey } : {}),
          },
          timeout: 30000,
        }
      );

      const data = response.data;
      const url = typeof data?.body === 'string'
        ? JSON.parse(data.body).url
        : data?.url;

      if (!url) throw new Error('No URL returned from docs API');

      setPdfState(prev => ({ ...prev, url, isLoading: false }));
    } catch (err) {
      setPdfState(prev => ({
        ...prev,
        error: err instanceof Error ? err.message : 'Failed to fetch PDF',
        isLoading: false,
      }));
    }
  }, [docsEndpoint, apiKey]);

  const close = useCallback(() => {
    setPdfState(prev => ({ ...prev, docName: '', url: null, error: null }));
  }, []);

  const setWidth = useCallback((width: number) => {
    setPdfState(prev => {
      if (width > 0 && width !== prev.width) {
        return { ...prev, width };
      }
      return prev;
    });
  }, []);

  return { ...pdfState, openPage, close, setWidth };
}

/**
 * Standalone page for viewing a single PDF document from S3.
 *
 * URL format: /docs/:filename?page=5&state=TX&agency_type=medical
 *
 * This page provides a full-screen PDF experience with page navigation,
 * zoom, and a "back to chat" link. Meant for deeper inspection when the
 * inline preview isn't enough.
 */

import { useEffect, useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { Document, Page, pdfjs } from 'react-pdf';
import { ArrowLeft, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Download, X } from 'lucide-react';
import axios from 'axios';
import { formatCitationLabel } from '../utils/citationFormat';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const DOCS_ENDPOINT = import.meta.env.VITE_DOCS_ENDPOINT || '';
const DOCS_API_KEY = import.meta.env.VITE_DOCS_API_KEY || '';

export default function DocsPage() {
  const { filename } = useParams<{ filename: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialPage = parseInt(searchParams.get('page') || '1', 10);
  const state = searchParams.get('state') || '';
  const agencyType = searchParams.get('agency_type') || '';

  const [url, setUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(initialPage);
  const [numPages, setNumPages] = useState(0);
  const [scale, setScale] = useState(1.2);

  const friendlyLabel = filename ? formatCitationLabel(filename, state, agencyType) : 'Document';

  // Fetch presigned URL on mount or when filename/state/agency changes
  useEffect(() => {
    if (!filename) return;
    let cancelled = false;

    const fetchUrl = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const resp = await axios.post(
          DOCS_ENDPOINT,
          {
            filename,
            ...(state ? { state } : {}),
            ...(agencyType ? { agency_type: agencyType } : {}),
          },
          {
            headers: {
              'Content-Type': 'application/json',
              ...(DOCS_API_KEY ? { 'x-api-key': DOCS_API_KEY } : {}),
            },
            timeout: 30000,
          },
        );
        if (cancelled) return;
        const data = resp.data;
        const u = typeof data?.body === 'string' ? JSON.parse(data.body).url : data?.url;
        if (!u) throw new Error('No URL returned');
        setUrl(u);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load document');
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    fetchUrl();
    return () => {
      cancelled = true;
    };
  }, [filename, state, agencyType]);

  // Sync page to URL
  useEffect(() => {
    const p = searchParams.get('page');
    if (p !== String(page)) {
      const newParams = new URLSearchParams(searchParams);
      newParams.set('page', String(page));
      setSearchParams(newParams, { replace: true });
    }
  }, [page, searchParams, setSearchParams]);

  const goPrev = () => setPage((p) => Math.max(1, p - 1));
  const goNext = () => setPage((p) => Math.min(numPages || p + 1, p + 1));

  return (
    <div className="min-h-screen bg-black text-zinc-200 flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-3 bg-zinc-950 sticky top-0 z-10">
        <div className="flex items-center gap-4 min-w-0">
          <Link
            to="/"
            className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-zinc-400 hover:text-white transition-colors"
          >
            <ArrowLeft size={14} />
            Back to chat
          </Link>
          <span className="w-px h-4 bg-zinc-700" />
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-medium text-white truncate" title={filename}>
              {friendlyLabel}
            </span>
            <span className="text-[10px] font-mono text-zinc-500 truncate">{filename}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {numPages > 0 && (
            <>
              <button
                type="button"
                onClick={goPrev}
                disabled={page <= 1}
                className="p-1.5 rounded border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-600 disabled:opacity-30 disabled:cursor-not-allowed"
                aria-label="Previous page"
              >
                <ChevronLeft size={14} />
              </button>
              <span className="text-xs font-mono text-zinc-400 min-w-[60px] text-center">
                {page} / {numPages}
              </span>
              <button
                type="button"
                onClick={goNext}
                disabled={page >= numPages}
                className="p-1.5 rounded border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-600 disabled:opacity-30 disabled:cursor-not-allowed"
                aria-label="Next page"
              >
                <ChevronRight size={14} />
              </button>
              <span className="w-px h-4 bg-zinc-700" />
              <button
                type="button"
                onClick={() => setScale((s) => Math.max(0.5, s - 0.2))}
                className="p-1.5 rounded border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-600"
                aria-label="Zoom out"
              >
                <ZoomOut size={14} />
              </button>
              <span className="text-[10px] font-mono text-zinc-500 min-w-[36px] text-center">
                {Math.round(scale * 100)}%
              </span>
              <button
                type="button"
                onClick={() => setScale((s) => Math.min(2.5, s + 0.2))}
                className="p-1.5 rounded border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-600"
                aria-label="Zoom in"
              >
                <ZoomIn size={14} />
              </button>
              {url && (
                <a
                  href={url}
                  download={filename}
                  className="p-1.5 rounded border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-600"
                  aria-label="Download PDF"
                >
                  <Download size={14} />
                </a>
              )}
            </>
          )}
        </div>
      </header>

      {/* PDF Viewer */}
      <main className="flex-1 overflow-auto flex justify-center p-6">
        {isLoading && (
          <div className="flex items-center gap-3 text-zinc-500 mt-12">
            <div className="w-2 h-2 bg-zinc-600 rounded-full animate-pulse" />
            <span className="text-xs font-mono uppercase tracking-wider">Loading document...</span>
          </div>
        )}

        {error && (
          <div className="mt-12 p-6 border border-red-900/30 bg-red-900/10 rounded max-w-lg">
            <div className="flex items-center gap-2 mb-2">
              <X size={16} className="text-red-400" />
              <span className="text-sm font-medium text-red-200">Failed to load document</span>
            </div>
            <p className="text-xs text-zinc-400 font-mono">{error}</p>
            <Link
              to="/"
              className="mt-4 inline-block text-xs font-mono text-zinc-400 hover:text-white underline"
            >
              Return to chat
            </Link>
          </div>
        )}

        {url && !error && (
          <Document
            file={url}
            onLoadSuccess={({ numPages: n }) => setNumPages(n)}
            onLoadError={(e) => setError(e.message)}
            loading={
              <div className="flex items-center gap-2 text-zinc-500 text-xs font-mono">
                <div className="w-2 h-2 bg-zinc-600 rounded-full animate-pulse" />
                Rendering...
              </div>
            }
          >
            <Page
              pageNumber={page}
              scale={scale}
              renderTextLayer
              renderAnnotationLayer
              className="shadow-xl"
            />
          </Document>
        )}
      </main>
    </div>
  );
}

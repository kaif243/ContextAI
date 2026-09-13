import { useCallback, useEffect, useMemo, useState } from 'react';
import { listFiles, searchFiles, selectFileNative } from '@/services/files';

interface FileRow {
  id: number;
  path: string;
  name: string;
  file_type: string;
  extension: string | null;
  size_bytes: number;
  modified_at: string | null;
  classification: string | null;
  classification_confidence: number | null;
  extraction_status: string;
  is_indexed: boolean;
  indexed_at: string | null;
}

type LoadState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string };

export default function Files() {
  const [items, setItems] = useState<FileRow[]>([]);
  const [total, setTotal] = useState(0);
  const [load, setLoad] = useState<LoadState>({ status: 'idle' });
  const [query, setQuery] = useState('');
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const refresh = useCallback(async (q?: string) => {
    setLoad({ status: 'loading' });
    try {
      const resp = (q && q.trim())
        ? await searchFiles({ query: q.trim(), limit: 50 })
        : await listFiles({ limit: 50 });
      const rows = (resp.items || resp.results || []) as FileRow[];
      setItems(rows);
      setTotal(resp.total || rows.length);
      setLoad({ status: 'idle' });
    } catch (e: any) {
      setLoad({ status: 'error', message: (e as Error).message || 'Failed to load files' });
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      refresh(query);
    },
    [query, refresh],
  );

  const handleFileSelect = useCallback(async () => {
    try {
      const native = await selectFileNative().catch(() => null);
      if (native && native.file) {
        await refresh(query);
      } else {
        await refresh(query);
      }
    } catch (e: any) {
      setLoad({ status: 'error', message: (e as Error).message || 'File selection failed' });
    }
  }, [query, refresh]);

  const statusColor = (status: string) => {
    switch (status) {
      case 'ok': return 'text-emerald-600 bg-emerald-50';
      case 'pending': return 'text-amber-600 bg-amber-50';
      case 'unsupported': return 'text-rose-600 bg-rose-50';
      case 'failed': return 'text-red-600 bg-red-50';
      case 'empty': return 'text-slate-500 bg-slate-50';
      default: return 'text-surface-500 bg-surface-50';
    }
  };

  const selectedFile = useMemo(
    () => items.find((r) => r.path === selectedPath) || null,
    [items, selectedPath],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Files</h1>
          <p className="text-surface-500 mt-1">User-selected file indexing, extraction, and search ({total})</p>
        </div>
        <button
          onClick={handleFileSelect}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700 transition text-sm font-medium"
        >
          Select File
        </button>
      </div>
      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search indexed files..."
          className="w-full px-3 py-2 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none"
        />
        <button type="submit" className="px-4 py-2 rounded-lg bg-surface-900 text-white text-sm">Search</button>
      </form>
      {load.status === 'loading' && <div className="text-sm text-surface-500">Loading...</div>}
      {load.status === 'error' && <div className="text-sm text-red-600">{load.message}</div>}
      <div className="bg-white rounded-xl border border-surface-200 overflow-hidden">
        {items.length === 0 && load.status !== 'loading' ? (
          <div className="p-8 text-center text-surface-400 text-sm">No indexed files. Click Select File.</div>
        ) : (
          <div className="divide-y divide-surface-100">
            {items.map((file) => (
              <button
                key={file.id}
                onClick={() => setSelectedPath(file.path)}
                className={"w-full text-left px-4 py-3 hover:bg-surface-50 text-sm " + (selectedPath === file.path ? "bg-primary-50" : "")}
              >
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{file.name}</div>
                    <div className="text-xs text-surface-400 truncate">{file.path}</div>
                  </div>
                  <span className="w-20 text-xs text-surface-600">{file.file_type}</span>
                  <span className={"w-24 text-xs px-2 py-0.5 rounded-full " + statusColor(file.extraction_status)}>{file.extraction_status}</span>
                  <span className="w-32 text-xs text-surface-500 truncate">{file.classification || '�'}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
      {selectedFile && (
        <div className="bg-white rounded-xl border border-surface-200 p-5 space-y-3">
          <h2 className="text-base font-semibold">File Details</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <Detail label="Path" value={selectedFile.path} />
            <Detail label="Name" value={selectedFile.name} />
            <Detail label="Type" value={selectedFile.file_type} />
            <Detail label="Status" value={selectedFile.extraction_status} />
            <Detail label="Size" value={String(selectedFile.size_bytes)} />
            <Detail label="Classified" value={selectedFile.classification || '�'} />
          </div>
        </div>
      )}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-50 rounded-lg px-3 py-2.5">
      <div className="text-xs text-surface-400">{label}</div>
      <div className="text-sm font-medium truncate">{value}</div>
    </div>
  );
}

// Screen Intelligence page - Phase 2
//
// Wires together the new screen-capture pipeline:
//
//   1. The user clicks "Capture now" (or hits Ctrl+Shift+S, which the
//      Rust side fires as a `screen-capture-requested` event). We call
//      `captureScreenNow` (the Tauri command) to grab the primary
//      monitor locally.
//   2. The returned PNG bytes are POSTed to the backend, which runs
//      OCR, classification, and entity extraction server-side and
//      returns the screenshot id.
//   3. The list of recent captures is refreshed and the new item is
//      auto-selected. The right panel shows OCR text, the activity
//      label, and any extracted entities.
//   4. The user can also ask free-form questions about the selected
//      screenshot; the answer (or error) is shown below the OCR.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { icons } from '@/utils/icons';
import { useAppStore } from '@/store/appStore';
import {
  askScreen,
  captureScreenBackend,
  captureScreenNow,
  deleteScreen,
  getClassifierInfo,
  getOCRInfo,
  getScreen,
  listScreens,
  listScreenAnalyses,
  onScreenCaptureRequested,
  summariseScreen,
  updateScreen,
} from '@/services/screen';
import type {
  ScreenAnalysis,
  ScreenClassifierInfo,
  ScreenOCRInfo,
  ScreenScreenshot,
} from '@/types';

const RECENT_LIMIT = 12;

interface CaptureState {
  status: 'idle' | 'capturing' | 'submitting' | 'error';
  message?: string;
}

export default function Screen() {
  const addToast = useAppStore((s) => s.addToast);
  const backendConnected = useAppStore((s) => s.backendConnected);

  const [screens, setScreens] = useState<ScreenScreenshot[]>([]);
  const [selectedId, setSelectedId] = useState<number | string | null>(null);
  const [selected, setSelected] = useState<ScreenScreenshot | null>(null);
  const [analyses, setAnalyses] = useState<ScreenAnalysis[]>([]);
  const [ocrInfo, setOcrInfo] = useState<ScreenOCRInfo | null>(null);
  const [classifierInfo, setClassifierInfo] = useState<ScreenClassifierInfo | null>(null);
  const [capture, setCapture] = useState<CaptureState>({ status: 'idle' });
  const [loadingList, setLoadingList] = useState(false);
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [search, setSearch] = useState('');

  // -------------------------------------------------------------------------
  // Loaders
  // -------------------------------------------------------------------------

  const refreshList = useCallback(async () => {
    setLoadingList(true);
    try {
      const resp = await listScreens({ limit: RECENT_LIMIT });
      setScreens(resp.items);
      if (resp.items.length > 0 && !selectedId) {
        setSelectedId(resp.items[0].id);
      }
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Could not load captures',
        message: e instanceof Error ? e.message : 'Unknown error',
      });
    } finally {
      setLoadingList(false);
    }
  }, [addToast, selectedId]);

  const loadDetails = useCallback(async (id: number | string) => {
    try {
      const [detail, history] = await Promise.all([
        getScreen(id),
        listScreenAnalyses(id).catch(() => [] as ScreenAnalysis[]),
      ]);
      setSelected(detail);
      setAnalyses(history);
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Could not load screenshot',
        message: e instanceof Error ? e.message : 'Unknown error',
      });
    }
  }, [addToast]);

  useEffect(() => {
    refreshList();
    getOCRInfo().then(setOcrInfo).catch(() => undefined);
    getClassifierInfo().then(setClassifierInfo).catch(() => undefined);
  }, [refreshList]);

  useEffect(() => {
    if (selectedId !== null) {
      loadDetails(selectedId);
    } else {
      setSelected(null);
      setAnalyses([]);
    }
  }, [selectedId, loadDetails]);

  // -------------------------------------------------------------------------
  // Capture flow
  // -------------------------------------------------------------------------

  const performCapture = useCallback(async () => {
    setCapture({ status: 'capturing' });
    try {
      const local = await captureScreenNow();
      if (!local.success) {
        const msg = local.error || 'Local capture failed';
        setCapture({ status: 'error', message: msg });
        addToast({ type: 'error', title: 'Capture failed', message: msg });
        return;
      }
      setCapture({ status: 'submitting' });
      const submitted = await captureScreenBackend({
        image_base64: local.image_base64 ?? undefined,
        image_path: local.image_path ?? undefined,
        width: local.width,
        height: local.height,
        run_ocr: true,
        save_to_disk: true,
      });
      if (!submitted.success) {
        const msg = submitted.error || 'Backend did not accept the capture';
        setCapture({ status: 'error', message: msg });
        addToast({ type: 'error', title: 'Capture failed', message: msg });
        return;
      }
      setCapture({ status: 'idle' });
      addToast({
        type: 'success',
        title: 'Screen captured',
        message: `Saved ${submitted.width}x${submitted.height} to ${submitted.image_path}`,
      });
      if (submitted.screenshot_id) {
        setSelectedId(submitted.screenshot_id);
      }
      await refreshList();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      setCapture({ status: 'error', message: msg });
      addToast({ type: 'error', title: 'Capture failed', message: msg });
    }
  }, [addToast, refreshList]);

  // Ctrl+Shift+S is wired in the Rust handler; it emits a
  // `screen-capture-requested` event we listen to here.
  useEffect(() => {
    let cleanup: (() => void) | null = null;
    onScreenCaptureRequested(() => {
      void performCapture();
    }).then((un) => {
      cleanup = un;
    });
    return () => {
      if (cleanup) cleanup();
    };
  }, [performCapture]);

  // -------------------------------------------------------------------------
  // Q&A and summarisation
  // -------------------------------------------------------------------------

  const handleAsk = useCallback(async () => {
    if (!selected || !question.trim()) return;
    setAsking(true);
    try {
      const resp = await askScreen(selected.id, question.trim());
      setAnalyses((prev) => [resp, ...prev]);
      setQuestion('');
      if (resp.is_error) {
        addToast({
          type: 'warning',
          title: 'Q&A returned an error',
          message: resp.error_message || 'The LLM did not return an answer.',
        });
      }
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Question failed',
        message: e instanceof Error ? e.message : 'Unknown error',
      });
    } finally {
      setAsking(false);
    }
  }, [addToast, question, selected]);

  const handleSummarise = useCallback(async () => {
    if (!selected) return;
    setAsking(true);
    try {
      const resp = await summariseScreen(selected.id);
      setAnalyses((prev) => [resp, ...prev]);
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Summarise failed',
        message: e instanceof Error ? e.message : 'Unknown error',
      });
    } finally {
      setAsking(false);
    }
  }, [addToast, selected]);

  // -------------------------------------------------------------------------
  // Selected-screen actions
  // -------------------------------------------------------------------------

  const handleArchive = useCallback(async () => {
    if (!selected) return;
    try {
      const next = await updateScreen(selected.id, { is_archived: !selected.is_archived });
      setSelected(next);
      setScreens((prev) => prev.map((s) => (s.id === next.id ? next : s)));
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Could not update',
        message: e instanceof Error ? e.message : 'Unknown error',
      });
    }
  }, [addToast, selected]);

  const handleDelete = useCallback(async () => {
    if (!selected) return;
    if (!window.confirm('Delete this screenshot permanently?')) return;
    try {
      await deleteScreen(selected.id);
      addToast({ type: 'success', title: 'Screenshot deleted' });
      setSelectedId(null);
      setSelected(null);
      await refreshList();
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Delete failed',
        message: e instanceof Error ? e.message : 'Unknown error',
      });
    }
  }, [addToast, refreshList, selected]);

  // -------------------------------------------------------------------------
  // Filtering
  // -------------------------------------------------------------------------

  const filteredScreens = useMemo(() => {
    if (!search.trim()) return screens;
    const q = search.toLowerCase();
    return screens.filter(
      (s) =>
        (s.file_name || '').toLowerCase().includes(q) ||
        (s.classification || '').toLowerCase().includes(q) ||
        (s.source_app || '').toLowerCase().includes(q) ||
        (s.window_title || '').toLowerCase().includes(q),
    );
  }, [screens, search]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const capturing = capture.status !== 'idle';

  return (
    <div className="space-y-6">
      <Header
        onCapture={performCapture}
        capturing={capturing}
        captureStatus={capture.status}
        captureError={capture.message}
        backendConnected={backendConnected}
        ocrInfo={ocrInfo}
        classifierInfo={classifierInfo}
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <RecentCapturesPanel
          items={filteredScreens}
          loading={loadingList}
          search={search}
          onSearchChange={setSearch}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onRefresh={refreshList}
        />

        <DetailsPanel
          selected={selected}
          analyses={analyses}
          question={question}
          onQuestionChange={setQuestion}
          onAsk={handleAsk}
          onSummarise={handleSummarise}
          onArchive={handleArchive}
          onDelete={handleDelete}
          asking={asking}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface HeaderProps {
  onCapture: () => void;
  capturing: boolean;
  captureStatus: CaptureState['status'];
  captureError?: string;
  backendConnected: boolean;
  ocrInfo: ScreenOCRInfo | null;
  classifierInfo: ScreenClassifierInfo | null;
}

function Header({
  onCapture,
  capturing,
  captureStatus,
  captureError,
  backendConnected,
  ocrInfo,
  classifierInfo,
}: HeaderProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Screen Intelligence</h1>
          <p className="text-surface-500 mt-1">
            Capture, OCR, classify, and ask questions about anything on your screen.
          </p>
        </div>
        <button
          type="button"
          onClick={onCapture}
          disabled={capturing}
          className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-primary-700 disabled:opacity-60"
        >
          {capturing ? (
            <icons.Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <icons.Camera className="h-4 w-4" />
          )}
          {capturing
            ? captureStatus === 'submitting'
              ? 'Analysing…'
              : 'Capturing…'
            : 'Capture now (Ctrl+Shift+S)'}
        </button>
      </div>

      {captureError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {captureError}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatusPill
          label="Backend"
          ok={backendConnected}
          okText="Connected"
          badText="Unreachable"
        />
        <StatusPill
          label={`OCR: ${ocrInfo?.provider ?? '…'}`}
          ok={!!ocrInfo?.available}
          okText={ocrInfo?.is_ml ? 'ML engine ready' : 'Engine ready (non-ML)'}
          badText="Unavailable"
        />
        <StatusPill
          label={`Classifier: ${classifierInfo?.name ?? '…'}`}
          ok={!!classifierInfo}
          okText={`${classifierInfo?.label_count ?? 0} labels`}
          badText="Unavailable"
        />
      </div>
    </div>
  );
}

function StatusPill({
  label,
  ok,
  okText,
  badText,
}: {
  label: string;
  ok: boolean;
  okText: string;
  badText: string;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-surface-200 bg-white px-3 py-2 text-sm">
      <span className="font-medium text-surface-700">{label}</span>
      <span
        className={
          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ' +
          (ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700')
        }
      >
        {ok ? (
          <icons.CheckCircle className="h-3.5 w-3.5" />
        ) : (
          <icons.XCircle className="h-3.5 w-3.5" />
        )}
        {ok ? okText : badText}
      </span>
    </div>
  );
}

interface RecentCapturesPanelProps {
  items: ScreenScreenshot[];
  loading: boolean;
  search: string;
  onSearchChange: (s: string) => void;
  selectedId: number | string | null;
  onSelect: (id: number | string) => void;
  onRefresh: () => void;
}

function RecentCapturesPanel({
  items,
  loading,
  search,
  onSearchChange,
  selectedId,
  onSelect,
  onRefresh,
}: RecentCapturesPanelProps) {
  return (
    <div className="lg:col-span-4 rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center justify-between border-b border-surface-200 p-4">
        <h2 className="text-sm font-semibold text-surface-900">Recent captures</h2>
        <button
          type="button"
          onClick={onRefresh}
          className="text-surface-500 hover:text-surface-700"
          aria-label="Refresh"
        >
          <icons.RefreshCw className={'h-4 w-4 ' + (loading ? 'animate-spin' : '')} />
        </button>
      </div>
      <div className="border-b border-surface-200 p-3">
        <div className="relative">
          <icons.Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by app, file, or label…"
            className="w-full rounded-md border border-surface-200 bg-surface-50 py-1.5 pl-8 pr-3 text-sm focus:border-primary-500 focus:outline-none"
          />
        </div>
      </div>
      <ul className="max-h-[60vh] divide-y divide-surface-100 overflow-y-auto">
        {loading && items.length === 0 && (
          <li className="flex items-center gap-2 p-4 text-sm text-surface-500">
            <icons.Loader2 className="h-4 w-4 animate-spin" />
            Loading captures…
          </li>
        )}
        {!loading && items.length === 0 && (
          <li className="p-4 text-sm text-surface-500">
            No captures yet. Press{' '}
            <kbd className="rounded border border-surface-300 bg-surface-50 px-1.5 py-0.5 text-xs">
              Ctrl+Shift+S
            </kbd>{' '}
            to start.
          </li>
        )}
        {items.map((item) => (
          <li key={String(item.id)}>
            <button
              type="button"
              onClick={() => onSelect(item.id)}
              className={
                'flex w-full flex-col items-start gap-1 p-3 text-left text-sm transition ' +
                (selectedId === item.id
                  ? 'bg-primary-50'
                  : 'hover:bg-surface-50')
              }
            >
              <div className="flex w-full items-center justify-between">
                <span className="truncate font-medium text-surface-900">
                  {item.file_name}
                </span>
                {item.is_archived && (
                  <icons.Archive className="h-3.5 w-3.5 text-surface-400" />
                )}
              </div>
              <div className="flex w-full items-center justify-between text-xs text-surface-500">
                <span>
                  {item.width}×{item.height} ·{' '}
                  {formatBytes(item.file_size_bytes)}
                </span>
                <span>{formatRelative(item.created_at)}</span>
              </div>
              {item.classification && (
                <div className="flex items-center gap-1 text-xs text-primary-700">
                  <icons.Tag className="h-3 w-3" />
                  {item.classification}
                  {item.classification_confidence != null && (
                    <span className="text-surface-400">
                      · {Math.round(item.classification_confidence * 100)}%
                    </span>
                  )}
                </div>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface DetailsPanelProps {
  selected: ScreenScreenshot | null;
  analyses: ScreenAnalysis[];
  question: string;
  onQuestionChange: (s: string) => void;
  onAsk: () => void;
  onSummarise: () => void;
  onArchive: () => void;
  onDelete: () => void;
  asking: boolean;
}

function DetailsPanel({
  selected,
  analyses,
  question,
  onQuestionChange,
  onAsk,
  onSummarise,
  onArchive,
  onDelete,
  asking,
}: DetailsPanelProps) {
  if (!selected) {
    return (
      <div className="lg:col-span-8 flex h-64 items-center justify-center rounded-lg border border-dashed border-surface-300 bg-white text-sm text-surface-500">
        Select a capture to see its OCR text, classification, and Q&A.
      </div>
    );
  }

  return (
    <div className="lg:col-span-8 space-y-4">
      <div className="rounded-lg border border-surface-200 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-200 p-4">
          <div>
            <h2 className="text-base font-semibold text-surface-900">
              {selected.file_name}
            </h2>
            <p className="text-xs text-surface-500">
              {selected.width}×{selected.height} · {formatBytes(selected.file_size_bytes)} ·{' '}
              {new Date(selected.created_at).toLocaleString()}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onArchive}
              className="inline-flex items-center gap-1 rounded-md border border-surface-200 px-2.5 py-1.5 text-xs font-medium text-surface-700 hover:bg-surface-50"
            >
              <icons.Archive className="h-3.5 w-3.5" />
              {selected.is_archived ? 'Unarchive' : 'Archive'}
            </button>
            <button
              type="button"
              onClick={onDelete}
              className="inline-flex items-center gap-1 rounded-md border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50"
            >
              <icons.Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-3">
          <Metadata label="Source app" value={selected.source_app || '—'} />
          <Metadata label="Window title" value={selected.window_title || '—'} />
          <Metadata
            label="File path"
            value={selected.file_path}
            mono
          />
        </div>
      </div>

      <div className="rounded-lg border border-surface-200 bg-white">
        <div className="flex items-center gap-2 border-b border-surface-200 p-4">
          <icons.Activity className="h-4 w-4 text-primary-500" />
          <h3 className="text-sm font-semibold text-surface-900">Activity classification</h3>
        </div>
        <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2">
          <div>
            <div className="text-xs uppercase tracking-wide text-surface-500">Label</div>
            <div className="mt-1 text-lg font-semibold text-surface-900">
              {selected.classification || 'unknown'}
            </div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-surface-500">Confidence</div>
            <div className="mt-1 text-lg font-semibold text-surface-900">
              {selected.classification_confidence != null
                ? `${Math.round(selected.classification_confidence * 100)}%`
                : '—'}
            </div>
            {selected.classifier_version && (
              <div className="mt-1 text-xs text-surface-400">
                model: {selected.classifier_version}
              </div>
            )}
          </div>
          {selected.extracted_entities && (
            <div className="md:col-span-2">
              <div className="text-xs uppercase tracking-wide text-surface-500">
                Extracted entities
              </div>
              <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                <EntityList title="Dates" items={selected.extracted_entities.dates} />
                <EntityList title="Times" items={selected.extracted_entities.times} />
                <EntityList title="URLs" items={selected.extracted_entities.urls} />
                <EntityList title="Emails" items={selected.extracted_entities.emails} />
                <EntityList
                  title="Amounts"
                  items={selected.extracted_entities.amounts}
                />
                <EntityList title="Phone numbers" items={selected.extracted_entities.phone_numbers} />
                <EntityList title="Names" items={selected.extracted_entities.names} />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-surface-200 bg-white">
        <div className="flex items-center justify-between gap-2 border-b border-surface-200 p-4">
          <div className="flex items-center gap-2">
            <icons.FileText className="h-4 w-4 text-primary-500" />
            <h3 className="text-sm font-semibold text-surface-900">OCR text</h3>
          </div>
          {selected.ocr && (
            <span className="text-xs text-surface-500">
              engine: {selected.ocr.engine} · {selected.ocr.word_count} words
            </span>
          )}
        </div>
        <div className="p-4">
          {selected.ocr && selected.ocr.text ? (
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md border border-surface-100 bg-surface-50 p-3 text-xs text-surface-800">
              {selected.ocr.text}
            </pre>
          ) : (
            <p className="text-sm text-surface-500">No text detected on this capture.</p>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-surface-200 bg-white">
        <div className="flex items-center gap-2 border-b border-surface-200 p-4">
          <icons.MessageSquare className="h-4 w-4 text-primary-500" />
          <h3 className="text-sm font-semibold text-surface-900">Screen Q&amp;A</h3>
        </div>
        <div className="space-y-3 p-4">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => onQuestionChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  onAsk();
                }
              }}
              placeholder="Ask anything about this screen…"
              className="flex-1 rounded-md border border-surface-200 bg-surface-50 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={onAsk}
              disabled={asking || !question.trim()}
              className="inline-flex items-center gap-1 rounded-md bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-60"
            >
              {asking ? (
                <icons.Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <icons.Send className="h-4 w-4" />
              )}
              Ask
            </button>
            <button
              type="button"
              onClick={onSummarise}
              disabled={asking}
              className="inline-flex items-center gap-1 rounded-md border border-surface-200 px-3 py-2 text-sm font-medium text-surface-700 hover:bg-surface-50 disabled:opacity-60"
            >
              <icons.Sparkles className="h-4 w-4" />
              Summarise
            </button>
          </div>

          {analyses.length === 0 ? (
            <p className="text-sm text-surface-500">No analyses yet. Ask a question or click Summarise.</p>
          ) : (
            <ul className="space-y-3">
              {analyses.map((a) => (
                <li
                  key={a.id}
                  className={
                    'rounded-md border p-3 text-sm ' +
                    (a.is_error
                      ? 'border-red-200 bg-red-50 text-red-800'
                      : 'border-surface-200 bg-surface-50 text-surface-800')
                  }
                >
                  <div className="flex items-center justify-between text-xs text-surface-500">
                    <span>
                      {a.analysis_type === 'qa' ? 'Q&A' : 'Summary'}
                      {a.question ? ` · ${a.question}` : ''}
                    </span>
                    <span>
                      {a.model_used || 'mock-llm'}
                      {a.processing_ms != null ? ` · ${a.processing_ms} ms` : ''}
                    </span>
                  </div>
                  <p className="mt-1 whitespace-pre-wrap text-sm">
                    {a.is_error ? a.error_message || a.answer : a.answer}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function Metadata({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-surface-500">{label}</div>
      <div
        className={
          'mt-1 break-all text-sm text-surface-800 ' + (mono ? 'font-mono text-xs' : '')
        }
      >
        {value}
      </div>
    </div>
  );
}

function EntityList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-md border border-surface-100 bg-surface-50 p-2">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-surface-500">
        {title} ({items?.length ?? 0})
      </div>
      {items && items.length > 0 ? (
        <ul className="mt-1 space-y-0.5 text-xs text-surface-700">
          {items.slice(0, 8).map((it, i) => (
            <li key={i} className="truncate">
              · {it}
            </li>
          ))}
          {items.length > 8 && (
            <li className="text-surface-400">…and {items.length - 8} more</li>
          )}
        </ul>
      ) : (
        <div className="mt-1 text-xs text-surface-400">none</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBytes(n: number): string {
  if (!n) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let v = n;
  let u = 0;
  while (v >= 1024 && u < units.length - 1) {
    v /= 1024;
    u++;
  }
  return `${v.toFixed(v < 10 && u > 0 ? 1 : 0)} ${units[u]}`;
}

function formatRelative(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '';
  const diff = Date.now() - t;
  const m = Math.round(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

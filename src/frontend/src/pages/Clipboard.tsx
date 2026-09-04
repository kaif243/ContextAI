// Clipboard page - Phase 3
//
// Wires together the new clipboard-intelligence surface:
//   1. List history from the backend (paginated, with classification +
//      sensitivity filters).
//   2. "Capture now" reads the OS clipboard via the Tauri command and
//      POSTs it to the backend for classification + storage.
//   3. Each row supports pin / delete / explain / summarise / copy.
//   4. The "Clear" action hits the backend and respects the
//      `keep_pinned` setting. Sensitive items are redacted in the UI.
//
// Sensitive items never display the raw content. The backend always
// returns ``content: ''`` for sensitive rows; the UI shows the
// redacted preview and a list of matched rule names instead.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { icons } from '@/utils/icons';
import { useAppStore } from '@/store/appStore';
import {
  captureClipboardBackend,
  captureClipboardNow,
  clearClipboardHistory,
  deleteClipboardItem,
  explainClipboardItem,
  listClipboard,
  pinClipboardItem,
  purgeExpiredClipboard,
  reanalyseClipboardItem,
  summariseClipboardItem,
} from '@/services/clipboard';
import type {
  ClipboardItem,
  ClipboardLLMResponse,
  Settings,
} from '@/types';

const RECENT_LIMIT = 50;

type LoadState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string };

export default function ClipboardPage() {
  const addToast = useAppStore((s) => s.addToast);
  const [items, setItems] = useState<ClipboardItem[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<LoadState>({ status: 'idle' });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [includeSensitive, setIncludeSensitive] = useState(true);
  const [actionPending, setActionPending] = useState<string | null>(null);
  const [llmResult, setLlmResult] = useState<ClipboardLLMResponse | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);

  const selected = useMemo(
    () => items.find((it) => it.id === selectedId) ?? null,
    [items, selectedId],
  );

  const refresh = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const resp = await listClipboard({
        limit: RECENT_LIMIT,
        offset: 0,
        include_sensitive: includeSensitive,
      });
      setItems(resp.items);
      setTotal(resp.total);
      setState({ status: 'idle' });
    } catch (e) {
      setState({ status: 'error', message: (e as Error).message });
    }
  }, [includeSensitive]);

  // Fetch settings so we can show monitoring + sensitive toggles in the
  // header. The page is read-only w.r.t. settings; updates go through
  // the Settings page.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { api } = await import('@/services/api');
        const s = await api.getSettings();
        if (!cancelled) setSettings(s);
      } catch {
        // Backend offline — leave settings null.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const filtered = useMemo(() => {
    if (!filter.trim()) return items;
    const needle = filter.toLowerCase();
    return items.filter(
      (it) =>
        it.preview.toLowerCase().includes(needle) ||
        it.content_type.toLowerCase().includes(needle) ||
        (it.classification ?? '').toLowerCase().includes(needle),
    );
  }, [items, filter]);

  const handleCaptureNow = useCallback(async () => {
    setActionPending('capture');
    try {
      const resp = await captureClipboardNow();
      if (resp.stored) {
        addToast({ type: 'success', title: 'Captured', message: resp.reason });
      } else if (resp.is_sensitive) {
        addToast({
          type: 'warning',
          title: 'Sensitive content dropped',
          message: 'Secret material was detected and not stored.',
        });
      } else {
        addToast({ type: 'info', title: 'Not stored', message: resp.reason });
      }
      await refresh();
    } catch (e) {
      addToast({ type: 'error', title: 'Capture failed', message: (e as Error).message });
    } finally {
      setActionPending(null);
    }
  }, [addToast, refresh]);

  const handleSubmitManual = useCallback(
    async (text: string) => {
      try {
        const resp = await captureClipboardBackend({ content: text });
        if (resp.stored) {
          addToast({ type: 'success', title: 'Saved', message: resp.reason });
        } else if (resp.is_sensitive) {
          addToast({
            type: 'warning',
            title: 'Sensitive content dropped',
            message: 'Secret material was detected and not stored.',
          });
        } else {
          addToast({ type: 'info', title: 'Not stored', message: resp.reason });
        }
        await refresh();
      } catch (e) {
        addToast({
          type: 'error',
          title: 'Submit failed',
          message: (e as Error).message,
        });
      }
    },
    [addToast, refresh],
  );

  const handlePin = useCallback(
    async (item: ClipboardItem) => {
      setActionPending(`pin-${item.id}`);
      try {
        await pinClipboardItem(item.id, !item.is_pinned);
        await refresh();
      } catch (e) {
        addToast({ type: 'error', title: 'Pin failed', message: (e as Error).message });
      } finally {
        setActionPending(null);
      }
    },
    [addToast, refresh],
  );

  const handleDelete = useCallback(
    async (item: ClipboardItem) => {
      setActionPending(`delete-${item.id}`);
      try {
        await deleteClipboardItem(item.id);
        if (selectedId === item.id) setSelectedId(null);
        await refresh();
        addToast({ type: 'success', title: 'Deleted' });
      } catch (e) {
        addToast({ type: 'error', title: 'Delete failed', message: (e as Error).message });
      } finally {
        setActionPending(null);
      }
    },
    [addToast, refresh, selectedId],
  );

  const handleClear = useCallback(async () => {
    if (!window.confirm('Clear clipboard history? Pinned items are kept.')) return;
    try {
      const resp = await clearClipboardHistory(true);
      addToast({
        type: 'success',
        title: 'Cleared',
        message: `${resp.affected} item(s) removed`,
      });
      setSelectedId(null);
      await refresh();
    } catch (e) {
      addToast({ type: 'error', title: 'Clear failed', message: (e as Error).message });
    }
  }, [addToast, refresh]);

  const handlePurge = useCallback(async () => {
    try {
      const resp = await purgeExpiredClipboard();
      addToast({
        type: 'success',
        title: 'Purged',
        message: `${resp.affected} expired item(s) removed`,
      });
      await refresh();
    } catch (e) {
      addToast({ type: 'error', title: 'Purge failed', message: (e as Error).message });
    }
  }, [addToast, refresh]);

  const handleReanalyse = useCallback(
    async (item: ClipboardItem) => {
      setActionPending(`reanalyse-${item.id}`);
      try {
        await reanalyseClipboardItem(item.id);
        await refresh();
      } catch (e) {
        addToast({
          type: 'error',
          title: 'Reanalyse failed',
          message: (e as Error).message,
        });
      } finally {
        setActionPending(null);
      }
    },
    [addToast, refresh],
  );

  const handleExplain = useCallback(
    async (item: ClipboardItem) => {
      setActionPending(`explain-${item.id}`);
      setLlmResult(null);
      try {
        const r = await explainClipboardItem(item.id);
        setLlmResult(r);
      } catch (e) {
        addToast({ type: 'error', title: 'Explain failed', message: (e as Error).message });
      } finally {
        setActionPending(null);
      }
    },
    [addToast],
  );

  const handleSummarise = useCallback(
    async (item: ClipboardItem) => {
      setActionPending(`summarise-${item.id}`);
      setLlmResult(null);
      try {
        const r = await summariseClipboardItem(item.id);
        setLlmResult(r);
      } catch (e) {
        addToast({
          type: 'error',
          title: 'Summarise failed',
          message: (e as Error).message,
        });
      } finally {
        setActionPending(null);
      }
    },
    [addToast],
  );

  return (
    <div className="space-y-6">
      <Header
        total={total}
        monitoring={settings?.clipboard_monitoring ?? null}
        historyEnabled={settings ? true : null}
        onCapture={handleCaptureNow}
        onClear={handleClear}
        onPurge={handlePurge}
        capturePending={actionPending === 'capture'}
      />

      <div className="flex flex-wrap items-center gap-3">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by text or type…"
          className="flex-1 min-w-[200px] px-3 py-2 rounded-md border border-surface-200 bg-white text-sm"
        />
        <label className="inline-flex items-center gap-2 text-sm text-surface-700">
          <input
            type="checkbox"
            checked={includeSensitive}
            onChange={(e) => setIncludeSensitive(e.target.checked)}
            className="rounded border-surface-300"
          />
          Show sensitive items
        </label>
        <ManualEntry onSubmit={handleSubmitManual} />
      </div>

      {state.status === 'error' && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-md p-3 text-sm">
          Failed to load: {state.message}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-lg border border-surface-200 divide-y divide-surface-100">
          {filtered.length === 0 ? (
            <EmptyState loading={state.status === 'loading'} />
          ) : (
            filtered.map((item) => (
              <ClipboardRow
                key={item.id}
                item={item}
                selected={selectedId === item.id}
                onSelect={() => setSelectedId(item.id)}
                onPin={() => handlePin(item)}
                onDelete={() => handleDelete(item)}
                onReanalyse={() => handleReanalyse(item)}
                onExplain={() => handleExplain(item)}
                onSummarise={() => handleSummarise(item)}
                busy={actionPending?.includes(item.id) ?? false}
              />
            ))
          )}
        </div>
        <DetailPanel item={selected} llmResult={llmResult} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function Header({
  total,
  monitoring,
  historyEnabled,
  onCapture,
  onClear,
  onPurge,
  capturePending,
}: {
  total: number;
  monitoring: boolean | null;
  historyEnabled: boolean | null;
  onCapture: () => void;
  onClear: () => void;
  onPurge: () => void;
  capturePending: boolean;
}) {
  return (
    <div className="bg-white rounded-lg border border-surface-200 p-4 flex flex-wrap items-center gap-3 justify-between">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">Clipboard</h1>
        <p className="text-surface-500 text-sm mt-0.5">
          {total} item{total === 1 ? '' : 's'} in history
          {monitoring !== null && (
            <>
              {' '}· monitoring:{' '}
              <span
                className={
                  monitoring ? 'text-green-700 font-medium' : 'text-surface-500'
                }
              >
                {monitoring ? 'on' : 'off'}
              </span>
            </>
          )}
          {historyEnabled !== null && (
            <>
              {' '}· history:{' '}
              <span className="font-medium">
                {historyEnabled ? 'on' : 'off'}
              </span>
            </>
          )}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={onCapture}
          disabled={capturePending}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50"
        >
          <icons.Plus className="h-4 w-4" />
          Capture now
        </button>
        <button
          onClick={onPurge}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md border border-surface-200 text-sm hover:bg-surface-50"
        >
          <icons.Trash2 className="h-4 w-4" />
          Purge expired
        </button>
        <button
          onClick={onClear}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md border border-red-200 text-red-700 text-sm hover:bg-red-50"
        >
          <icons.Trash2 className="h-4 w-4" />
          Clear history
        </button>
      </div>
    </div>
  );
}

function ClipboardRow({
  item,
  selected,
  onSelect,
  onPin,
  onDelete,
  onReanalyse,
  onExplain,
  onSummarise,
  busy,
}: {
  item: ClipboardItem;
  selected: boolean;
  onSelect: () => void;
  onPin: () => void;
  onDelete: () => void;
  onReanalyse: () => void;
  onExplain: () => void;
  onSummarise: () => void;
  busy: boolean;
}) {
  const preview = item.is_sensitive ? item.redacted_content || '[redacted]' : item.preview;
  return (
    <div
      onClick={onSelect}
      className={`p-3 cursor-pointer ${
        selected ? 'bg-primary-50' : 'hover:bg-surface-50'
      }`}
    >
      <div className="flex items-center gap-2 text-xs text-surface-500">
        <span className="font-mono px-1.5 py-0.5 rounded bg-surface-100 text-surface-700">
          {item.content_type}
        </span>
        {item.classification && item.classification !== item.content_type && (
          <span className="font-mono px-1.5 py-0.5 rounded bg-surface-100">
            {item.classification}
          </span>
        )}
        {item.is_sensitive && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-100 text-red-800">
            <icons.Lock className="h-3 w-3" />
            sensitive
          </span>
        )}
        {item.is_pinned && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">
            <icons.Star className="h-3 w-3" />
            pinned
          </span>
        )}
        <span className="ml-auto">
          {item.timestamp ? new Date(item.timestamp).toLocaleString() : ''}
        </span>
      </div>
      <div className="mt-1.5 font-mono text-sm text-surface-900 whitespace-pre-wrap break-words line-clamp-3">
        {preview || <em className="text-surface-400">[empty]</em>}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <RowAction
          onClick={(e) => {
            e.stopPropagation();
            onPin();
          }}
          icon={item.is_pinned ? icons.Pin : icons.Pin}
          label={item.is_pinned ? 'Unpin' : 'Pin'}
          disabled={busy}
        />
        <RowAction
          onClick={(e) => {
            e.stopPropagation();
            onReanalyse();
          }}
          icon={icons.RefreshCw}
          label="Re-classify"
          disabled={busy}
        />
        <RowAction
          onClick={(e) => {
            e.stopPropagation();
            onExplain();
          }}
          icon={icons.Brain}
          label="Explain"
          disabled={busy}
        />
        <RowAction
          onClick={(e) => {
            e.stopPropagation();
            onSummarise();
          }}
          icon={icons.FileText}
          label="Summarise"
          disabled={busy}
        />
        <RowAction
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          icon={icons.Trash2}
          label="Delete"
          tone="danger"
          disabled={busy}
        />
      </div>
    </div>
  );
}

function RowAction({
  onClick,
  icon: Icon,
  label,
  tone = 'default',
  disabled,
}: {
  onClick: (e: React.MouseEvent) => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  tone?: 'default' | 'danger';
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border ${
        tone === 'danger'
          ? 'border-red-200 text-red-700 hover:bg-red-50'
          : 'border-surface-200 text-surface-700 hover:bg-surface-50'
      } disabled:opacity-50`}
    >
      <Icon className="h-3 w-3" />
      {label}
    </button>
  );
}

function DetailPanel({
  item,
  llmResult,
}: {
  item: ClipboardItem | null;
  llmResult: ClipboardLLMResponse | null;
}) {
  if (!item) {
    return (
      <div className="bg-surface-50 rounded-lg border border-surface-200 p-6 text-center text-sm text-surface-500">
        Select an item to see details.
      </div>
    );
  }
  return (
    <div className="bg-white rounded-lg border border-surface-200 p-4 space-y-3">
      <h2 className="text-sm font-semibold text-surface-700">Details</h2>
      <DetailRow label="ID" value={item.id} mono />
      <DetailRow label="Type" value={item.content_type} />
      <DetailRow
        label="Classification"
        value={item.classification ?? '—'}
        sub={item.classifier_version ? `version ${item.classifier_version}` : undefined}
      />
      {item.classification_confidence !== null && (
        <DetailRow
          label="Confidence"
          value={item.classification_confidence.toFixed(2)}
        />
      )}
      <DetailRow
        label="Source"
        value={item.source_app ?? 'unknown'}
      />
      <DetailRow label="Chars / words" value={`${item.char_count} / ${item.word_count}`} />
      {item.timestamp && (
        <DetailRow label="Captured" value={new Date(item.timestamp).toLocaleString()} />
      )}
      {item.expires_at && (
        <DetailRow label="Expires" value={new Date(item.expires_at).toLocaleString()} />
      )}
      {item.is_sensitive && (
        <div className="rounded-md bg-red-50 border border-red-200 p-2">
          <p className="text-xs font-semibold text-red-800">Sensitive</p>
          {item.sensitive_reasons.length > 0 && (
            <ul className="mt-1 text-xs text-red-700 list-disc list-inside">
              {item.sensitive_reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
          {item.redacted_content && (
            <pre className="mt-2 text-xs text-red-900 whitespace-pre-wrap break-words font-mono">
              {item.redacted_content}
            </pre>
          )}
        </div>
      )}
      {llmResult && (
        <div
          className={`rounded-md p-2 ${
            llmResult.is_error
              ? 'bg-red-50 border border-red-200'
              : 'bg-primary-50 border border-primary-200'
          }`}
        >
          <p className="text-xs font-semibold text-surface-800">
            {llmResult.action === 'explain' ? 'Explanation' : 'Summary'}
            {llmResult.model_used ? ` · ${llmResult.model_used}` : ''}
          </p>
          <p className="mt-1 text-sm text-surface-900 whitespace-pre-wrap">
            {llmResult.answer}
          </p>
          {llmResult.processing_ms !== null && (
            <p className="mt-1 text-[10px] text-surface-500">
              {llmResult.processing_ms} ms
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function DetailRow({
  label,
  value,
  sub,
  mono,
}: {
  label: string;
  value: string;
  sub?: string;
  mono?: boolean;
}) {
  return (
    <div className="text-xs">
      <div className="text-surface-500">{label}</div>
      <div
        className={`text-surface-900 ${mono ? 'font-mono' : ''} break-words`}
      >
        {value}
      </div>
      {sub && <div className="text-surface-400 text-[10px]">{sub}</div>}
    </div>
  );
}

function EmptyState({ loading }: { loading: boolean }) {
  if (loading) {
    return (
      <div className="p-6 text-center text-sm text-surface-500">Loading…</div>
    );
  }
  return (
    <div className="p-8 text-center text-surface-500">
      <icons.Clipboard className="h-10 w-10 mx-auto mb-2 text-surface-300" />
      No clipboard history yet. Copy something or use “Capture now”.
    </div>
  );
}

function ManualEntry({ onSubmit }: { onSubmit: (text: string) => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-3 py-1.5 rounded-md border border-surface-200 text-sm hover:bg-surface-50"
      >
        Add manually…
      </button>
    );
  }
  return (
    <div className="w-full flex flex-col gap-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste content to add to history"
        rows={3}
        className="w-full px-3 py-2 rounded-md border border-surface-200 bg-white text-sm font-mono"
      />
      <div className="flex gap-2 justify-end">
        <button
          onClick={() => {
            setOpen(false);
            setText('');
          }}
          className="px-3 py-1.5 rounded-md border border-surface-200 text-sm"
        >
          Cancel
        </button>
        <button
          onClick={() => {
            if (text.trim()) {
              onSubmit(text);
              setText('');
              setOpen(false);
            }
          }}
          className="px-3 py-1.5 rounded-md bg-primary-600 text-white text-sm font-medium disabled:opacity-50"
          disabled={!text.trim()}
        >
          Save
        </button>
      </div>
    </div>
  );
}

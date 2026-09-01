// Toast notification component

import { useAppStore } from '@/store/appStore';
import { icons } from '@/utils/icons';
import { cn } from '@/utils/cn';
import type { Toast as ToastType } from '@/types';

function ToastItem({ toast }: { toast: ToastType }) {
  const removeToast = useAppStore((state) => state.removeToast);

  const variantStyles = {
    success: 'bg-green-50 border-green-200 text-green-900',
    error: 'bg-red-50 border-red-200 text-red-900',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-900',
    info: 'bg-blue-50 border-blue-200 text-blue-900',
  };

  const variantIcons = {
    success: icons.CheckCircle,
    error: icons.XCircle,
    warning: icons.AlertTriangle,
    info: icons.Info,
  };

  const Icon = variantIcons[toast.type];

  return (
    <div
      className={cn(
        'flex items-start gap-3 p-4 rounded-lg border shadow-elevated animate-in slide-in-from-right-full',
        variantStyles[toast.type]
      )}
      role="alert"
    >
      <Icon className="h-5 w-5 flex-shrink-0 mt-0.5" aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <h4 className="font-medium text-sm">{toast.title}</h4>
        {toast.message && (
          <p className="mt-1 text-sm opacity-90">{toast.message}</p>
        )}
      </div>
      <button
        onClick={() => removeToast(toast.id)}
        className="flex-shrink-0 p-1 rounded hover:bg-black/5 transition-colors"
        aria-label="Dismiss notification"
      >
        <icons.X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

export function Toaster() {
  const toasts = useAppStore((state) => state.toasts);

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm"
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}

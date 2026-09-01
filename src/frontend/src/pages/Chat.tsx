// Chat page - Phase 1 placeholder

import { useState } from 'react';
import { icons } from '@/utils/icons';
import { useAppStore } from '@/store/appStore';

export default function Chat() {
  const [message, setMessage] = useState('');
  const { backendConnected } = useAppStore();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-1 min-h-0">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-surface-900">Chat</h1>
            <p className="text-sm text-surface-500">
              {backendConnected ? 'Connected to backend' : 'Backend disconnected'}
            </p>
          </div>
        </div>

        {/* Placeholder content */}
        <div className="bg-surface-50 rounded-lg border border-surface-200 p-8 text-center">
          <icons.MessageSquare className="h-12 w-12 mx-auto text-surface-300 mb-4" />
          <h2 className="text-lg font-medium text-surface-700 mb-2">
            Chat Coming in Phase 2
          </h2>
          <p className="text-sm text-surface-500 max-w-md mx-auto">
            The agentic AI chat interface will be implemented in Phase 7. For now, you can explore
            the other features of ContextAI.
          </p>
        </div>
      </div>

      {/* Input area - disabled for Phase 1 */}
      <div className="mt-4">
        <div className="relative">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Chat will be available in Phase 7..."
            disabled
            className="w-full h-24 px-4 py-3 rounded-lg border border-surface-200 bg-surface-50 text-surface-400 resize-none"
          />
          <button
            disabled
            className="absolute bottom-3 right-3 p-2 rounded-lg bg-primary-100 text-primary-400 cursor-not-allowed"
          >
            <icons.Send className="h-5 w-5" />
          </button>
        </div>
        <p className="mt-2 text-xs text-surface-400 text-center">
          Phase 7: Agentic AI - Full chat with agent orchestration
        </p>
      </div>
    </div>
  );
}

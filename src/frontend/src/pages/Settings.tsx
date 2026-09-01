// Settings page - Phase 1 partial implementation

import { useState, useEffect } from 'react';
import { useAppStore } from '@/store/appStore';
import { icons } from '@/utils/icons';
import type { Settings } from '@/types';

export default function SettingsPage() {
  const { settings, loadSettings, updateSettings, backendConnected } = useAppStore();
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('general');

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleSave = async (newSettings: Partial<Settings>) => {
    setIsSaving(true);
    try {
      await updateSettings(newSettings);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">Settings</h1>
        <p className="text-surface-500 mt-1">
          Configure ContextAI to your preferences
        </p>
      </div>

      {/* Connection Status */}
      <div className={`rounded-lg border p-4 ${
        backendConnected ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
      }`}>
        <div className="flex items-center gap-3">
          {backendConnected ? (
            <icons.CheckCircle className="h-5 w-5 text-green-600" />
          ) : (
            <icons.XCircle className="h-5 w-5 text-red-600" />
          )}
          <span className={backendConnected ? 'text-green-700' : 'text-red-700'}>
            {backendConnected ? 'Backend connected' : 'Backend disconnected'}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-surface-200">
        <nav className="flex gap-4">
          {[
            { id: 'general', label: 'General', icon: icons.Settings },
            { id: 'hotkey', label: 'Hotkey', icon: icons.Keyboard },
            { id: 'privacy', label: 'Privacy', icon: icons.Shield },
            { id: 'llm', label: 'LLM', icon: icons.Cpu },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 -mb-px transition-colors ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-surface-500 hover:text-surface-700'
              }`}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div className="bg-white rounded-lg border border-surface-200 p-6">
        {activeTab === 'general' && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-surface-900">General Settings</h2>

            <SettingToggle
              label="Auto-start"
              description="Start ContextAI when you log in"
              checked={settings?.auto_start || false}
              onChange={(checked) => handleSave({ auto_start: checked })}
            />

            <SettingToggle
              label="Minimize to tray"
              description="Hide to system tray instead of closing"
              checked={settings?.minimize_to_tray ?? true}
              onChange={(checked) => handleSave({ minimize_to_tray: checked })}
            />

            <SettingSelect
              label="Log level"
              description="Amount of detail in logs"
              value={settings?.log_level || 'INFO'}
              options={[
                { value: 'DEBUG', label: 'Debug' },
                { value: 'INFO', label: 'Info' },
                { value: 'WARNING', label: 'Warning' },
                { value: 'ERROR', label: 'Error' },
              ]}
              onChange={(value) => handleSave({ log_level: value })}
            />
          </div>
        )}

        {activeTab === 'hotkey' && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-surface-900">Hotkey Settings</h2>

            <div>
              <label className="block text-sm font-medium text-surface-700 mb-2">
                Global Hotkey
              </label>
              <div className="flex items-center gap-2">
                <kbd className="px-3 py-2 bg-surface-100 border border-surface-300 rounded font-mono text-sm">
                  {settings?.hotkey || 'Ctrl+Space'}
                </kbd>
                <span className="text-sm text-surface-500">to toggle ContextAI window</span>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'privacy' && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-surface-900">Privacy Settings</h2>

            <SettingToggle
              label="Privacy mode"
              description="Disable all context monitoring"
              checked={settings?.privacy_mode || false}
              onChange={(checked) => handleSave({ privacy_mode: checked })}
            />

            <SettingToggle
              label="Clipboard monitoring"
              description="Track clipboard history"
              checked={settings?.clipboard_monitoring ?? true}
              onChange={(checked) => handleSave({ clipboard_monitoring: checked })}
            />

            <SettingToggle
              label="Screen monitoring"
              description="Allow screen capture and analysis"
              checked={settings?.screen_monitoring || false}
              onChange={(checked) => handleSave({ screen_monitoring: checked })}
            />

            <SettingToggle
              label="File indexing"
              description="Index files for search"
              checked={settings?.file_indexing_enabled || false}
              onChange={(checked) => handleSave({ file_indexing_enabled: checked })}
            />
          </div>
        )}

        {activeTab === 'llm' && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-surface-900">LLM Settings</h2>

            <SettingSelect
              label="Provider"
              description="LLM provider to use"
              value={settings?.llm_provider || 'ollama'}
              options={[
                { value: 'ollama', label: 'Ollama (Local)' },
                { value: 'openai', label: 'OpenAI' },
                { value: 'anthropic', label: 'Anthropic' },
                { value: 'gemini', label: 'Google Gemini' },
              ]}
              onChange={(value) => handleSave({ llm_provider: value })}
            />

            <div>
              <label className="block text-sm font-medium text-surface-700 mb-2">
                Model
              </label>
              <input
                type="text"
                value={settings?.llm_model || 'llama3.1:8b'}
                onChange={(e) => handleSave({ llm_model: e.target.value })}
                className="w-full max-w-md px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="llama3.1:8b"
              />
              <p className="mt-1 text-xs text-surface-500">
                For Ollama, use format: model:tag (e.g., llama3.1:8b, mistral:7b)
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Save button */}
      {isSaving && (
        <div className="flex items-center gap-2 text-primary-600">
          <icons.Loader2 className="h-4 w-4 animate-spin" />
          <span>Saving...</span>
        </div>
      )}
    </div>
  );
}

function SettingToggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h3 className="font-medium text-surface-900">{label}</h3>
        <p className="text-sm text-surface-500">{description}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          checked ? 'bg-primary-500' : 'bg-surface-300'
        }`}
        role="switch"
        aria-checked={checked}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}

function SettingSelect({
  label,
  description,
  value,
  options,
  onChange,
}: {
  label: string;
  description: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-surface-700 mb-1">{label}</label>
      <p className="text-xs text-surface-500 mb-2">{description}</p>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full max-w-xs px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

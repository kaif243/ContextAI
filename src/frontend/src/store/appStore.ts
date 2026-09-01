import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { invoke } from '@tauri-apps/api/core';
import type { AppInfo, Settings, HealthResponse, Toast } from '@/types';

interface AppState {
  // App info
  appInfo: AppInfo | null;
  isInitialized: boolean;
  backendConnected: boolean;

  // Settings
  settings: Settings | null;

  // UI state
  sidebarOpen: boolean;
  activeModal: string | null;
  toasts: Toast[];

  // Actions
  initializeApp: () => Promise<void>;
  checkBackendHealth: () => Promise<void>;
  loadSettings: () => Promise<void>;
  updateSettings: (settings: Partial<Settings>) => Promise<void>;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  openModal: (modal: string) => void;
  closeModal: () => void;
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}

const DEFAULT_SETTINGS: Settings = {
  hotkey: 'Ctrl+Space',
  auto_start: false,
  minimize_to_tray: true,
  privacy_mode: false,
  clipboard_monitoring: true,
  screen_monitoring: false,
  file_indexing_enabled: false,
  llm_provider: 'ollama',
  llm_model: 'llama3.1:8b',
  log_level: 'INFO',
};

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      appInfo: null,
      isInitialized: false,
      backendConnected: false,
      settings: null,
      sidebarOpen: true,
      activeModal: null,
      toasts: [],

      initializeApp: async () => {
        try {
          // Load app info
          const appInfo = await invoke<AppInfo>('get_app_info');
          set({ appInfo });

          // Load settings
          const settings = await invoke<Settings>('get_settings');
          set({ settings });

          // Check backend health
          await get().checkBackendHealth();

          set({ isInitialized: true });
        } catch (error) {
          console.error('Failed to initialize app:', error);
          get().addToast({
            type: 'error',
            title: 'Initialization Failed',
            message: 'Could not connect to backend. Some features may not work.',
            duration: 5000,
          });
          set({ isInitialized: true }); // Still mark as initialized to show UI
        }
      },

      checkBackendHealth: async () => {
        try {
          const health = await invoke<HealthResponse>('check_backend_health');
          set({ backendConnected: health.status === 'healthy' });
        } catch {
          set({ backendConnected: false });
        }
      },

      loadSettings: async () => {
        try {
          const settings = await invoke<Settings>('get_settings');
          set({ settings });
        } catch (error) {
          console.error('Failed to load settings:', error);
        }
      },

      updateSettings: async (newSettings) => {
        try {
          const current = get().settings || DEFAULT_SETTINGS;
          const updated = await invoke<Settings>('update_settings', {
            request: { ...current, ...newSettings },
          });
          set({ settings: updated });
          get().addToast({
            type: 'success',
            title: 'Settings Updated',
            message: 'Your changes have been saved.',
          });
        } catch (error) {
          console.error('Failed to update settings:', error);
          get().addToast({
            type: 'error',
            title: 'Update Failed',
            message: 'Could not save settings. Please try again.',
          });
        }
      },

      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),

      openModal: (modal) => set({ activeModal: modal }),
      closeModal: () => set({ activeModal: null }),

      addToast: (toast) => {
        const id = Math.random().toString(36).substring(2, 9);
        set((state) => ({
          toasts: [...state.toasts, { ...toast, id }],
        }));
        if (toast.duration !== 0) {
          setTimeout(() => {
            get().removeToast(id);
          }, toast.duration || 4000);
        }
      },

      removeToast: (id) => set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      })),
    }),
    {
      name: 'contextai-app-store',
      partialize: (state) => ({
        settings: state.settings,
        sidebarOpen: state.sidebarOpen,
      }),
    }
  )
);
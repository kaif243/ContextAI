import { Outlet } from 'react-router-dom';
import { useState, ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { Toaster } from './ui/Toaster';
import { useAppStore } from '@/store/appStore';
import { cn } from '@/utils/cn';

const navigation = [
  { id: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard', path: '/dashboard' },
  { id: 'chat', label: 'Chat', icon: 'MessageSquare', path: '/chat' },
  { id: 'files', label: 'Files', icon: 'FolderOpen', path: '/files' },
  { id: 'clipboard', label: 'Clipboard', icon: 'Clipboard', path: '/clipboard' },
  { id: 'screen', label: 'Screen', icon: 'Monitor', path: '/screen' },
  { id: 'memory', label: 'Memory', icon: 'Database', path: '/memory' },
  { id: 'ml-dashboard', label: 'ML Dashboard', icon: 'Brain', path: '/ml-dashboard' },
  { id: 'settings', label: 'Settings', icon: 'Settings', path: '/settings' },
];

interface LayoutProps {
  children?: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { sidebarOpen, toggleSidebar, backendConnected } = useAppStore();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-surface-50 flex">
      {/* Mobile sidebar overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setMobileSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <Sidebar
        navigation={navigation}
        isOpen={sidebarOpen}
        mobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />

      {/* Main content */}
      <div className={cn(
        'flex-1 flex flex-col min-w-0 transition-all duration-300',
        sidebarOpen ? 'lg:ml-64' : 'lg:ml-20'
      )}>
        <Header
          onMenuClick={() => {
            if (window.innerWidth < 1024) {
              setMobileSidebarOpen(true);
            } else {
              toggleSidebar();
            }
          }}
          backendConnected={backendConnected}
        />

        <main className="flex-1 p-4 lg:p-6 overflow-auto">
          {children || <Outlet />}
        </main>
      </div>

      <Toaster />
    </div>
  );
}
import { NavLink, useLocation } from 'react-router-dom';
import { useMemo } from 'react';
import { cn } from '@/utils/cn';
import { icons } from '@/utils/icons';
import type { NavigationItem } from '@/types';

interface SidebarProps {
  navigation: NavigationItem[];
  isOpen: boolean;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

export function Sidebar({ navigation, isOpen, mobileOpen, onMobileClose }: SidebarProps) {
  const location = useLocation();

  const navItems = useMemo(() => navigation.map((item) => ({
    ...item,
    Icon: icons[item.icon as keyof typeof icons] || icons.LayoutDashboard,
    isActive: location.pathname === item.path,
  })), [navigation, location.pathname]);

  if (!isOpen && !mobileOpen) {
    return (
      <aside
        className="fixed left-0 top-0 z-50 h-screen w-20 bg-white border-r border-surface-200 transition-all duration-300 lg:translate-x-0"
        aria-label="Navigation (collapsed)"
      >
        <nav className="flex h-full flex-col px-2 py-4 space-y-1" aria-label="Main navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              onClick={onMobileClose}
              className={cn(
                'relative flex h-10 w-10 items-center justify-center rounded-lg transition-colors',
                'hover:bg-surface-100',
                item.isActive && 'bg-primary-50 text-primary-600',
                !item.isActive && 'text-surface-500 hover:text-surface-700'
              )}
              aria-label={item.label}
              aria-current={item.isActive ? 'page' : undefined}
              title={item.label}
            >
              <item.Icon className="h-5 w-5" aria-hidden="true" />
              {item.badge && (
                <span className="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-xs font-medium text-white">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-surface-200">
          <NavLink
            to="/about"
            onClick={onMobileClose}
            className="flex h-10 w-10 items-center justify-center rounded-lg text-surface-500 hover:bg-surface-100 hover:text-surface-700 transition-colors"
            aria-label="About ContextAI"
            title="About ContextAI"
          >
            <icons.Info className="h-5 w-5" aria-hidden="true" />
          </NavLink>
        </div>
      </aside>
    );
  }

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-50 h-screen bg-white border-r border-surface-200 transition-all duration-300',
        'lg:translate-x-0',
        mobileOpen ? 'w-64 translate-x-0' : '-translate-x-full',
        isOpen && !mobileOpen ? 'w-64' : 'w-20'
      )}
      aria-label="Navigation"
    >
      <div className="flex h-full flex-col">
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-surface-200">
          <NavLink
            to="/dashboard"
            onClick={onMobileClose}
            className="flex items-center gap-2 font-semibold text-lg text-surface-900"
            aria-label="ContextAI Home"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-500 text-white">
              <icons.Cpu className="h-5 w-5" aria-hidden="true" />
            </div>
            <span className={cn('transition-opacity duration-200', isOpen || mobileOpen ? 'opacity-100' : 'opacity-0 w-0 overflow-hidden')}>
              ContextAI
            </span>
          </NavLink>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-2 py-4 space-y-1" aria-label="Main navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              onClick={onMobileClose}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors',
                'hover:bg-surface-100',
                item.isActive ? 'bg-primary-50 text-primary-600' : 'text-surface-600 hover:text-surface-900',
                !isOpen && !mobileOpen && 'justify-center px-0'
              )}
              aria-label={item.label}
              aria-current={item.isActive ? 'page' : undefined}
            >
              <item.Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
              <span className={cn(
                'font-medium transition-opacity duration-200',
                isOpen || mobileOpen ? 'opacity-100' : 'opacity-0 w-0 overflow-hidden'
              )}>
                {item.label}
              </span>
              {item.badge && (
                <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-xs font-medium text-white">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Bottom section */}
        <div className="border-t border-surface-200 p-4">
          <NavLink
            to="/settings"
            onClick={onMobileClose}
            className={cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-surface-600 hover:bg-surface-100 hover:text-surface-900 transition-colors',
              !isOpen && !mobileOpen && 'justify-center px-0'
            )}
            aria-label="Settings"
          >
            <icons.Settings className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
            <span className={cn(
              'font-medium transition-opacity duration-200',
              isOpen || mobileOpen ? 'opacity-100' : 'opacity-0 w-0 overflow-hidden'
            )}>
              Settings
            </span>
          </NavLink>

          <NavLink
            to="/about"
            onClick={onMobileClose}
            className={cn(
              'mt-2 flex items-center gap-3 px-3 py-2.5 rounded-lg text-surface-500 hover:bg-surface-100 hover:text-surface-700 transition-colors',
              !isOpen && !mobileOpen && 'justify-center px-0'
            )}
            aria-label="About ContextAI"
          >
            <icons.Info className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
            <span className={cn(
              'font-medium transition-opacity duration-200',
              isOpen || mobileOpen ? 'opacity-100' : 'opacity-0 w-0 overflow-hidden'
            )}>
              About
            </span>
          </NavLink>

          {/* Version info when expanded */}
          {(isOpen || mobileOpen) && (
            <div className="mt-4 pt-4 border-t border-surface-200 text-xs text-surface-400">
              <p>ContextAI v0.1.0</p>
              <p className="mt-1">Phase 1 - Foundation</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
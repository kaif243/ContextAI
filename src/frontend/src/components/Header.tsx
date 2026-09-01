import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/utils/cn';
import { icons } from '@/utils/icons';

interface HeaderProps {
  onMenuClick: () => void;
  backendConnected: boolean;
}

export function Header({ onMenuClick, backendConnected }: HeaderProps) {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (showSearch && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [showSearch]);

  const handleGlobalSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery('');
      setShowSearch(false);
    }
  };

  const handleQuickAction = (action: string) => {
    switch (action) {
      case 'screen':
        navigate('/screen');
        break;
      case 'clipboard':
        navigate('/clipboard');
        break;
      case 'files':
        navigate('/files');
        break;
      case 'chat':
        navigate('/chat');
        break;
      default:
        break;
    }
  };

  return (
    <header
      className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-surface-200 bg-white/80 backdrop-blur-sm px-4 lg:px-6"
      role="banner"
    >
      {/* Menu button */}
      <button
        onClick={onMenuClick}
        className="lg:hidden flex h-10 w-10 items-center justify-center rounded-lg text-surface-600 hover:bg-surface-100 transition-colors"
        aria-label="Open navigation menu"
        aria-expanded="false"
      >
        <icons.Menu className="h-5 w-5" aria-hidden="true" />
      </button>

      {/* Global Search */}
      <form onSubmit={handleGlobalSearch} className="relative flex-1 max-w-xl lg:max-w-2xl">
        <label htmlFor="global-search" className="sr-only">
          Global search
        </label>
        <div className="relative">
          <icons.Search
            className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-surface-400 pointer-events-none"
            aria-hidden="true"
          />
          <input
            ref={searchInputRef}
            id="global-search"
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setShowSearch(true)}
            onBlur={() => setTimeout(() => setShowSearch(false), 200)}
            placeholder="Search files, clipboard, memory... (Ctrl+K)"
            className={cn(
              'w-full h-10 pl-10 pr-4 rounded-lg bg-surface-100 border border-transparent',
              'text-surface-900 placeholder:text-surface-400',
              'focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 focus:bg-white',
              'transition-all duration-200'
            )}
            aria-label="Global search"
            aria-expanded={showSearch}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 transition-colors"
              aria-label="Clear search"
            >
              <icons.X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
        {showSearch && searchQuery && (
          <div className="absolute top-full left-0 right-0 mt-1 p-2 bg-white border border-surface-200 rounded-lg shadow-elevated">
            <p className="text-xs text-surface-500">
              Press Enter to search for "{searchQuery}"
            </p>
          </div>
        )}
      </form>

      {/* Quick Actions */}
      <div className="hidden lg:flex items-center gap-2">
        {[
          { id: 'screen', label: 'Screen', icon: icons.Monitor, shortcut: 'Ctrl+Shift+S' },
          { id: 'clipboard', label: 'Clipboard', icon: icons.Clipboard, shortcut: 'Ctrl+Shift+C' },
          { id: 'files', label: 'Files', icon: icons.FolderOpen, shortcut: 'Ctrl+Shift+F' },
          { id: 'chat', label: 'Chat', icon: icons.MessageSquare, shortcut: 'Ctrl+Space' },
        ].map((action) => (
          <button
            key={action.id}
            onClick={() => handleQuickAction(action.id)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-surface-600 hover:bg-surface-100 hover:text-surface-900 transition-colors"
            aria-label={`${action.label} (${action.shortcut})`}
          >
            <action.icon className="h-4 w-4" aria-hidden="true" />
            <span className="hidden sm:inline font-medium">{action.label}</span>
          </button>
        ))}
      </div>

      {/* Status Indicators */}
      <div className="flex items-center gap-3">
        {/* Backend Connection Status */}
        <div className="flex items-center gap-1.5" role="status" aria-live="polite">
          <span
            className={cn(
              'h-2 w-2 rounded-full',
              backendConnected ? 'bg-green-500' : 'bg-red-500'
            )}
            aria-hidden="true"
          />
          <span className="text-xs text-surface-500 hidden sm:inline">
            {backendConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>

        {/* Global Hotkey Hint */}
        <kbd className="hidden lg:inline-flex items-center gap-1 px-2 py-1 text-xs font-mono text-surface-500 bg-surface-100 rounded">
          <icons.Keyboard className="h-3 w-3" aria-hidden="true" />
          <span>Ctrl+Space</span>
        </kbd>
      </div>
    </header>
  );
}
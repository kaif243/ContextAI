// Dashboard page - Phase 1 placeholder

import { useAppStore } from '@/store/appStore';
import { icons } from '@/utils/icons';

export default function Dashboard() {
  const { backendConnected, appInfo } = useAppStore();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-surface-900">Welcome to ContextAI</h1>
        <p className="text-surface-500 mt-1">
          AI Desktop Intelligence & Automation Platform
        </p>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatusCard
          title="Backend Status"
          value={backendConnected ? 'Connected' : 'Disconnected'}
          icon={backendConnected ? icons.CheckCircle : icons.XCircle}
          color={backendConnected ? 'green' : 'red'}
        />
        <StatusCard
          title="Version"
          value={appInfo?.version || '0.1.0'}
          icon={icons.Tag}
          color="blue"
        />
        <StatusCard
          title="Phase"
          value="Phase 1"
          icon={icons.Cpu}
          color="purple"
        />
        <StatusCard
          title="Privacy Mode"
          value="Off"
          icon={icons.Shield}
          color="gray"
        />
      </div>

      {/* Phase 1 Progress */}
      <section className="bg-white rounded-lg border border-surface-200 p-6">
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Phase 1: Foundation</h2>
        <div className="space-y-3">
          <PhaseTask name="Tauri Desktop App" status="complete" />
          <PhaseTask name="React + TypeScript Frontend" status="complete" />
          <PhaseTask name="FastAPI Backend" status="complete" />
          <PhaseTask name="SQLite Database" status="complete" />
          <PhaseTask name="Alembic Migrations" status="complete" />
          <PhaseTask name="Configuration System" status="complete" />
          <PhaseTask name="Structured Logging" status="complete" />
          <PhaseTask name="System Tray" status="complete" />
          <PhaseTask name="Global Hotkey" status="complete" />
          <PhaseTask name="LLM Provider Abstraction" status="complete" />
        </div>
      </section>

      {/* Upcoming Features */}
      <section className="bg-white rounded-lg border border-surface-200 p-6">
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Upcoming Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FeatureCard
            title="Phase 2: Screen Intelligence"
            description="Global hotkey, screenshot capture, OCR, screen classification, and Q&A about screen content."
            icon={icons.Monitor}
          />
          <FeatureCard
            title="Phase 3: AI Clipboard"
            description="Intelligent clipboard history with content classification, semantic search, and privacy controls."
            icon={icons.Clipboard}
          />
          <FeatureCard
            title="Phase 4: File Intelligence"
            description="Folder indexing, metadata extraction, text extraction, and semantic file search."
            icon={icons.FolderOpen}
          />
          <FeatureCard
            title="Phase 5: ML System"
            description="5 ML models for classification, similarity, importance prediction, and anomaly detection."
            icon={icons.Brain}
          />
        </div>
      </section>

      {/* Quick Actions */}
      <section className="bg-white rounded-lg border border-surface-200 p-6">
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <QuickAction title="Capture Screen" icon={icons.Monitor} href="/screen" />
          <QuickAction title="Clipboard" icon={icons.Clipboard} href="/clipboard" />
          <QuickAction title="Files" icon={icons.FolderOpen} href="/files" />
          <QuickAction title="Memory" icon={icons.Database} href="/memory" />
        </div>
      </section>
    </div>
  );
}

function StatusCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  color: 'green' | 'red' | 'blue' | 'purple' | 'gray';
}) {
  const colorClasses = {
    green: 'bg-green-50 text-green-700 border-green-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    gray: 'bg-gray-50 text-gray-700 border-gray-200',
  };

  return (
    <div className={`rounded-lg border p-4 ${colorClasses[color]}`}>
      <div className="flex items-center gap-3">
        <Icon className="h-6 w-6" />
        <div>
          <p className="text-sm opacity-70">{title}</p>
          <p className="font-semibold">{value}</p>
        </div>
      </div>
    </div>
  );
}

function PhaseTask({ name, status }: { name: string; status: 'complete' | 'pending' }) {
  return (
    <div className="flex items-center gap-3">
      {status === 'complete' ? (
        <icons.CheckCircle className="h-5 w-5 text-green-500" />
      ) : (
        <icons.Circle className="h-5 w-5 text-gray-300" />
      )}
      <span className={status === 'complete' ? 'text-surface-700' : 'text-surface-400'}>
        {name}
      </span>
    </div>
  );
}

function FeatureCard({
  title,
  description,
  icon: Icon,
}: {
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="p-4 rounded-lg border border-surface-200 hover:border-primary-200 transition-colors">
      <div className="flex items-center gap-3 mb-2">
        <Icon className="h-5 w-5 text-primary-500" />
        <h3 className="font-medium text-surface-900">{title}</h3>
      </div>
      <p className="text-sm text-surface-500">{description}</p>
    </div>
  );
}

function QuickAction({
  title,
  icon: Icon,
  href,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
}) {
  return (
    <a
      href={href}
      className="flex flex-col items-center gap-2 p-4 rounded-lg border border-surface-200 hover:border-primary-200 hover:bg-primary-50/50 transition-all"
    >
      <Icon className="h-6 w-6 text-surface-600" />
      <span className="text-sm font-medium text-surface-700">{title}</span>
    </a>
  );
}

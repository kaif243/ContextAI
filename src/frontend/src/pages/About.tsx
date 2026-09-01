// About page

import { useAppStore } from '@/store/appStore';
import { icons } from '@/utils/icons';

export default function About() {
  const { appInfo, backendConnected } = useAppStore();

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">About ContextAI</h1>
        <p className="text-surface-500 mt-1">
          AI Desktop Intelligence & Automation Platform
        </p>
      </div>

      {/* App info */}
      <div className="bg-white rounded-lg border border-surface-200 p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-primary-500 text-white">
            <icons.Cpu className="h-8 w-8" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-surface-900">ContextAI</h2>
            <p className="text-surface-500">Version {appInfo?.version || '0.1.0'}</p>
          </div>
        </div>

        <p className="text-surface-600 leading-relaxed">
          ContextAI is an intelligent Windows desktop companion that understands your computer context
          and helps you complete everyday tasks through agentic AI, machine learning, and desktop automation.
        </p>
      </div>

      {/* System status */}
      <div className="bg-white rounded-lg border border-surface-200 p-6">
        <h3 className="text-lg font-semibold text-surface-900 mb-4">System Status</h3>
        <div className="space-y-3">
          <StatusRow
            label="Frontend"
            value="Running"
            status="green"
          />
          <StatusRow
            label="Backend"
            value={backendConnected ? 'Connected' : 'Disconnected'}
            status={backendConnected ? 'green' : 'red'}
          />
          <StatusRow
            label="Database"
            value="SQLite"
            status="green"
          />
          <StatusRow
            label="LLM Provider"
            value="Ollama (configurable)"
            status="yellow"
          />
        </div>
      </div>

      {/* Features */}
      <div className="bg-white rounded-lg border border-surface-200 p-6">
        <h3 className="text-lg font-semibold text-surface-900 mb-4">Development Phases</h3>
        <div className="space-y-3">
          <PhaseRow number={1} name="Foundation" status="complete" description="Tauri, React, FastAPI, SQLite, Config, Logging" />
          <PhaseRow number={2} name="Screen Intelligence" status="pending" description="Global hotkey, screenshot, OCR, classification" />
          <PhaseRow number={3} name="AI Clipboard" status="pending" description="Clipboard history, classification, search" />
          <PhaseRow number={4} name="File Intelligence" status="pending" description="File indexing, extraction, classification" />
          <PhaseRow number={5} name="ML System" status="pending" description="5 ML models, evaluation, dashboard" />
          <PhaseRow number={6} name="RAG + Memory" status="pending" description="Embeddings, vector search, memory" />
          <PhaseRow number={7} name="Agentic AI" status="pending" description="Agent orchestrator, planning, tools" />
        </div>
      </div>

      {/* Technology */}
      <div className="bg-white rounded-lg border border-surface-200 p-6">
        <h3 className="text-lg font-semibold text-surface-900 mb-4">Technology Stack</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <TechItem category="Desktop" tech="Tauri 2.x" />
          <TechItem category="Frontend" tech="React 18, TypeScript" />
          <TechItem category="Backend" tech="FastAPI, Python 3.11" />
          <TechItem category="Database" tech="SQLite, SQLAlchemy" />
          <TechItem category="Migrations" tech="Alembic" />
          <TechItem category="ML" tech="PyTorch, scikit-learn" />
          <TechItem category="OCR" tech="PaddleOCR" />
          <TechItem category="Vectors" tech="FAISS" />
          <TechItem category="LLM" tech="Ollama / OpenAI / Claude" />
        </div>
      </div>

      {/* License */}
      <div className="bg-surface-50 rounded-lg border border-surface-200 p-6 text-center">
        <p className="text-surface-600">
          MIT License
        </p>
        <p className="text-sm text-surface-500 mt-1">
          Built with Claude Code and Anthropic
        </p>
      </div>
    </div>
  );
}

function StatusRow({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status: 'green' | 'yellow' | 'red';
}) {
  const statusColors = {
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
  };

  return (
    <div className="flex items-center justify-between">
      <span className="text-surface-700">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${statusColors[status]}`} />
        <span className="text-surface-600">{value}</span>
      </div>
    </div>
  );
}

function PhaseRow({
  number,
  name,
  status,
  description,
}: {
  number: number;
  name: string;
  status: 'complete' | 'pending' | 'in_progress';
  description: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
        status === 'complete' ? 'bg-green-100 text-green-700' :
        status === 'in_progress' ? 'bg-yellow-100 text-yellow-700' :
        'bg-surface-200 text-surface-500'
      }`}>
        {status === 'complete' ? '✓' : number}
      </div>
      <div>
        <h4 className="font-medium text-surface-900">{name}</h4>
        <p className="text-sm text-surface-500">{description}</p>
      </div>
    </div>
  );
}

function TechItem({ category, tech }: { category: string; tech: string }) {
  return (
    <div>
      <p className="text-surface-500 text-xs">{category}</p>
      <p className="font-medium text-surface-900">{tech}</p>
    </div>
  );
}

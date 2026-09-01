// Screen page - Phase 1 placeholder

import { icons } from '@/utils/icons';

export default function Screen() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">Screen Intelligence</h1>
        <p className="text-surface-500 mt-1">
          Capture and analyze your screen
        </p>
      </div>

      {/* Phase indicator */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <div className="flex items-center gap-3">
          <icons.Brain className="h-5 w-5 text-purple-600" />
          <span className="font-medium text-purple-900">Phase 2: Screen Intelligence</span>
        </div>
        <p className="mt-2 text-sm text-purple-700">
          Global hotkey capture, OCR, screen classification, and Q&A about screen content
          will be implemented in Phase 2.
        </p>
      </div>

      {/* Feature preview */}
      <div className="bg-white rounded-lg border border-surface-200 p-6">
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Coming Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <FeatureCard
            icon={icons.Keyboard}
            title="Global Hotkey"
            description="Press Ctrl+Space to capture screen"
          />
          <FeatureCard
            icon={icons.Scan}
            title="OCR"
            description="Extract text from screenshots"
          />
          <FeatureCard
            icon={icons.Brain}
            title="Screen Classification"
            description="Classify into code, error, document, etc."
          />
          <FeatureCard
            icon={icons.MessageSquare}
            title="Screen Q&A"
            description="Ask questions about your screen"
          />
          <FeatureCard
            icon={icons.AlertCircle}
            title="Error Detection"
            description="Identify programming errors"
          />
          <FeatureCard
            icon={icons.Calendar}
            title="Entity Extraction"
            description="Extract dates, times, and more"
          />
        </div>
      </div>

      {/* Placeholder */}
      <div className="bg-surface-50 rounded-lg border border-surface-200 p-8 text-center">
        <icons.Monitor className="h-12 w-12 mx-auto text-surface-300 mb-4" />
        <p className="text-surface-500">
          Screen capture will be available in Phase 2.
        </p>
        <p className="text-sm text-surface-400 mt-2">
          Press Ctrl+Space to toggle the ContextAI window
        </p>
      </div>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <div className="flex gap-3 p-4 rounded-lg border border-surface-200">
      <Icon className="h-5 w-5 text-primary-500 flex-shrink-0" />
      <div>
        <h3 className="font-medium text-surface-900">{title}</h3>
        <p className="text-sm text-surface-500">{description}</p>
      </div>
    </div>
  );
}

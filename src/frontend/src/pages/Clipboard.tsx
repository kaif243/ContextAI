// Clipboard page - Phase 1 placeholder

import { icons } from '@/utils/icons';

export default function Clipboard() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">Clipboard</h1>
        <p className="text-surface-500 mt-1">
          Intelligent clipboard history
        </p>
      </div>

      {/* Phase indicator */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <div className="flex items-center gap-3">
          <icons.Brain className="h-5 w-5 text-purple-600" />
          <span className="font-medium text-purple-900">Phase 3: AI Clipboard</span>
        </div>
        <p className="mt-2 text-sm text-purple-700">
          Full clipboard history, content classification, semantic search, and privacy controls
          will be implemented in Phase 3.
        </p>
      </div>

      {/* Feature preview */}
      <div className="bg-white rounded-lg border border-surface-200 p-6">
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Coming Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FeatureCard
            icon={icons.Clipboard}
            title="Clipboard History"
            description="Automatic tracking of clipboard content"
          />
          <FeatureCard
            icon={icons.Tag}
            title="Content Classification"
            description="Classify into code, URL, email, etc."
          />
          <FeatureCard
            icon={icons.Search}
            title="Semantic Search"
            description="Find past clipboard items naturally"
          />
          <FeatureCard
            icon={icons.Lock}
            title="Privacy Controls"
            description="Disable monitoring, clear history"
          />
        </div>
      </div>

      {/* Placeholder */}
      <div className="bg-surface-50 rounded-lg border border-surface-200 p-8 text-center">
        <icons.Clipboard className="h-12 w-12 mx-auto text-surface-300 mb-4" />
        <p className="text-surface-500">
          Clipboard monitoring will be available in Phase 3.
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

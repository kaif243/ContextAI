// Memory page - Phase 1 placeholder

import { icons } from '@/utils/icons';

export default function Memory() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">Memory</h1>
        <p className="text-surface-500 mt-1">
          User-controlled personal memory
        </p>
      </div>

      {/* Phase indicator */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <div className="flex items-center gap-3">
          <icons.Brain className="h-5 w-5 text-purple-600" />
          <span className="font-medium text-purple-900">Phase 6: RAG + Memory</span>
        </div>
        <p className="mt-2 text-sm text-purple-700">
          Full memory system with embeddings, vector search, RAG, and memory management UI
          will be implemented in Phase 6.
        </p>
      </div>

      {/* Feature preview */}
      <div className="bg-white rounded-lg border border-surface-200 p-6">
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Coming Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FeatureCard
            icon={icons.Database}
            title="Personal Memory"
            description="Store important notes and information"
          />
          <FeatureCard
            icon={icons.Search}
            title="Semantic Search"
            description="Search memory with natural language"
          />
          <FeatureCard
            icon={icons.Tag}
            title="Tagging"
            description="Organize memories with tags"
          />
          <FeatureCard
            icon={icons.Lock}
            title="Privacy Control"
            description="View, edit, delete, or clear memories"
          />
        </div>
      </div>

      {/* Placeholder */}
      <div className="bg-surface-50 rounded-lg border border-surface-200 p-8 text-center">
        <icons.Database className="h-12 w-12 mx-auto text-surface-300 mb-4" />
        <p className="text-surface-500">
          Memory system will be available in Phase 6.
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

// Files page - Phase 1 placeholder

import { icons } from '@/utils/icons';

export default function Files() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">Files</h1>
        <p className="text-surface-500 mt-1">
          Intelligent file indexing and search
        </p>
      </div>

      {/* Phase indicator */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <div className="flex items-center gap-3">
          <icons.Brain className="h-5 w-5 text-purple-600" />
          <span className="font-medium text-purple-900">Phase 4: File Intelligence</span>
        </div>
        <p className="mt-2 text-sm text-purple-700">
          Full file indexing, metadata extraction, text extraction, file classification,
          and semantic search will be implemented in Phase 4.
        </p>
      </div>

      {/* Feature preview */}
      <div className="bg-white rounded-lg border border-surface-200 p-6">
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Coming Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <FeatureCard
            icon={icons.FolderSearch}
            title="Folder Indexing"
            description="Select folders to index for intelligent search"
          />
          <FeatureCard
            icon={icons.FileText}
            title="Text Extraction"
            description="Extract text from PDFs, documents, and images"
          />
          <FeatureCard
            icon={icons.Tag}
            title="File Classification"
            description="ML-based classification into categories"
          />
          <FeatureCard
            icon={icons.Search}
            title="Semantic Search"
            description="Natural language file search with embeddings"
          />
          <FeatureCard
            icon={icons.Copy}
            title="Duplicate Detection"
            description="Find semantically similar files"
          />
          <FeatureCard
            icon={icons.FolderOpen}
            title="File Organization"
            description="AI-powered organization suggestions"
          />
        </div>
      </div>

      {/* Placeholder file list */}
      <div className="bg-surface-50 rounded-lg border border-surface-200 p-8 text-center">
        <icons.FolderOpen className="h-12 w-12 mx-auto text-surface-300 mb-4" />
        <p className="text-surface-500">
          No folders indexed yet. Folder selection will be available in Phase 4.
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

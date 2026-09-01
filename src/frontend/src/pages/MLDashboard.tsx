// ML Dashboard page - Phase 1 placeholder

import { icons } from '@/utils/icons';

export default function MLDashboard() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">ML Dashboard</h1>
        <p className="text-surface-500 mt-1">
          Machine learning model performance and evaluation
        </p>
      </div>

      {/* Phase indicator */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <div className="flex items-center gap-3">
          <icons.Brain className="h-5 w-5 text-purple-600" />
          <span className="font-medium text-purple-900">Phase 5: ML System</span>
        </div>
        <p className="mt-2 text-sm text-purple-700">
          ML models, evaluation metrics, and the ML dashboard will be implemented in Phase 5.
        </p>
      </div>

      {/* Models preview */}
      <div className="bg-white rounded-lg border border-surface-200 p-6">
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Planned ML Models</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <ModelCard
            name="File Classification"
            description="Classify files into categories: Education, Finance, Career, Programming, etc."
            metrics={null}
          />
          <ModelCard
            name="Screen Classification"
            description="Classify screenshots: Code, Error, Document, Receipt, Table, etc."
            metrics={null}
          />
          <ModelCard
            name="Semantic Similarity"
            description="Detect semantically similar documents for duplicate detection"
            metrics={null}
          />
          <ModelCard
            name="Importance Prediction"
            description="Predict importance of clipboard items and other content"
            metrics={null}
          />
          <ModelCard
            name="Anomaly Detection"
            description="Detect unusual patterns in user activity"
            metrics={null}
          />
        </div>
      </div>

      {/* Metrics placeholder */}
      <div className="bg-surface-50 rounded-lg border border-surface-200 p-8 text-center">
        <icons.Gauge className="h-12 w-12 mx-auto text-surface-300 mb-4" />
        <p className="text-surface-500">
          ML metrics and evaluation results will appear here after Phase 5.
        </p>
        <p className="text-sm text-surface-400 mt-2">
          Metrics: Accuracy, Precision, Recall, F1, Confusion Matrix, Inference Time
        </p>
      </div>
    </div>
  );
}

function ModelCard({
  name,
  description,
  metrics,
}: {
  name: string;
  description: string;
  metrics: {
    accuracy: number;
    precision: number;
    recall: number;
    f1: number;
    dataset_size: number;
    inference_ms: number;
  } | null;
}) {
  return (
    <div className="p-4 rounded-lg border border-surface-200">
      <div className="flex items-center gap-2 mb-2">
        <icons.Brain className="h-5 w-5 text-primary-500" />
        <h3 className="font-medium text-surface-900">{name}</h3>
      </div>
      <p className="text-sm text-surface-500 mb-4">{description}</p>

      {metrics ? (
        <div className="grid grid-cols-3 gap-2 text-xs">
          <Metric label="Accuracy" value={`${(metrics.accuracy * 100).toFixed(1)}%`} />
          <Metric label="Precision" value={`${(metrics.precision * 100).toFixed(1)}%`} />
          <Metric label="Recall" value={`${(metrics.recall * 100).toFixed(1)}%`} />
          <Metric label="F1" value={`${(metrics.f1 * 100).toFixed(1)}%`} />
          <Metric label="Dataset" value={metrics.dataset_size.toString()} />
          <Metric label="Inference" value={`${metrics.inference_ms}ms`} />
        </div>
      ) : (
        <div className="text-xs text-surface-400 italic">
          Metrics not yet available
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center p-2 bg-surface-50 rounded">
      <div className="font-medium text-surface-900">{value}</div>
      <div className="text-surface-500">{label}</div>
    </div>
  );
}

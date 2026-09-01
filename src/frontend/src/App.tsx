import { Routes, Route, Navigate } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import { Layout } from '@/components/Layout';
import { useAppStore } from '@/store/appStore';
import { useEffect } from 'react';

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('@/pages/Dashboard').then(m => ({ default: m.default })));
const Chat = lazy(() => import('@/pages/Chat').then(m => ({ default: m.default })));
const Files = lazy(() => import('@/pages/Files').then(m => ({ default: m.default })));
const Clipboard = lazy(() => import('@/pages/Clipboard').then(m => ({ default: m.default })));
const Screen = lazy(() => import('@/pages/Screen').then(m => ({ default: m.default })));
const Memory = lazy(() => import('@/pages/Memory').then(m => ({ default: m.default })));
const Settings = lazy(() => import('@/pages/Settings').then(m => ({ default: m.default })));
const MLDashboard = lazy(() => import('@/pages/MLDashboard').then(m => ({ default: m.default })));
const About = lazy(() => import('@/pages/About').then(m => ({ default: m.default })));

const LoadingFallback = () => (
  <div className="flex items-center justify-center h-full">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
  </div>
);

function AppContent() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/chat" element={<Chat />} />
      <Route path="/files" element={<Files />} />
      <Route path="/clipboard" element={<Clipboard />} />
      <Route path="/screen" element={<Screen />} />
      <Route path="/memory" element={<Memory />} />
      <Route path="/ml-dashboard" element={<MLDashboard />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/about" element={<About />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default function App() {
  const initializeApp = useAppStore(state => state.initializeApp);
  const isInitialized = useAppStore(state => state.isInitialized);

  useEffect(() => {
    initializeApp();
  }, [initializeApp]);

  if (!isInitialized) {
    return <LoadingFallback />;
  }

  return (
    <Suspense fallback={<LoadingFallback />}>
      <Layout>
        <AppContent />
      </Layout>
    </Suspense>
  );
}
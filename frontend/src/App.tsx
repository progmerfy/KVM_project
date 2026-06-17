import React, { useState, useEffect, useCallback } from 'react';
import { requireAuth, getMe } from './api';
import { User } from './types';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import AuditLog from './pages/AuditLog';

export type Page = 'dashboard' | 'vms' | 'detail' | 'isos' | 'repo' | 'settings' | 'audit';
export type NavigateFn = (page: Page, vmName?: string) => void;

interface Toast { id: number; message: string; type?: 'success' | 'error' | 'info' }

let toastSeq = 0;

const TOAST_COLORS: Record<string, string> = {
  success: '#22c55e',
  error: '#ef4444',
  info: '#60a5fa',
};

export default function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [selectedVM, setSelectedVM] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isoAction, setIsoAction] = useState<'upload' | 'download' | null>(null);

  useEffect(() => {
    requireAuth();
    getMe()
      .then(r => setUser(r.user))
      .catch(() => { window.location.href = '/auth/login-page?redirect=/'; });
  }, []);

  const addToast = useCallback((message: string, type?: 'success' | 'error' | 'info') => {
    const id = ++toastSeq;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  const navigate = useCallback<NavigateFn>((p, vmName?) => {
    setPage(p);
    if (vmName) setSelectedVM(vmName);
    setIsoAction(null);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    window.location.href = '/auth/login-page';
  };

  const handleAction = useCallback((action: string) => {
    if (action === 'upload-iso') { setPage('isos'); setIsoAction('upload'); }
    else if (action === 'download-iso') { setPage('isos'); setIsoAction('download'); }
  }, []);

  const renderPage = () => {
    switch (page) {
      case 'settings':
        return <Settings user={user} addToast={addToast} />;
      case 'audit':
        return <AuditLog addToast={addToast} />;
      default:
        return (
          <Dashboard
            page={page}
            selectedVM={selectedVM}
            navigate={navigate}
            user={user}
            addToast={addToast}
            isoAction={isoAction}
            setIsoAction={setIsoAction}
          />
        );
    }
  };

  return (
    <Layout page={page} user={user} onNavigate={navigate} onLogout={handleLogout} onAction={handleAction}>
      {renderPage()}
      {toasts.length > 0 && (
        <div className="toast-container">
          {toasts.map(t => (
            <div key={t.id} className="toast" style={{
              borderColor: TOAST_COLORS[t.type || 'info'],
              color: TOAST_COLORS[t.type || 'info'],
            }}>
              <span className="toast-icon">
                {t.type === 'success' ? '✓' : t.type === 'error' ? '✕' : 'ℹ'}
              </span>
              {t.message}
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}

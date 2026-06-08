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
        <div style={{
          position: 'fixed', bottom: 20, left: '50%', transform: 'translateX(-50%)',
          zIndex: 1000, display: 'flex', flexDirection: 'column', gap: 8, pointerEvents: 'none',
        }}>
          {toasts.map(t => (
            <div key={t.id} style={{
              background: '#1a1a2e', color: '#e4e4e7', padding: '10px 20px',
              borderRadius: 8, fontSize: 13, border: '1px solid #1e1e32',
              ...(t.type === 'error' ? { borderColor: '#ef4444', color: '#ef4444' } : {}),
              ...(t.type === 'success' ? { borderColor: '#22c55e', color: '#22c55e' } : {}),
            }}>
              {t.message}
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}

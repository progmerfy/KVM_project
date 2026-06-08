import React, { useState } from 'react';
import { User } from '../types';
import { Page } from '../App';

interface LayoutProps {
  page: Page;
  user: User | null;
  onNavigate: (page: Page, vmName?: string) => void;
  onLogout: () => void;
  onAction?: (action: string) => void;
  children: React.ReactNode;
}

const crumbs: Partial<Record<Page, string[]>> = {
  dashboard: ['Dashboard'],
  vms: ['Dashboard', 'Virtual Machines'],
  detail: ['Dashboard', 'VM Detail'],
  isos: ['ISO Store', 'Browse'],
  repo: ['ISO Store', 'Repo'],
  settings: ['Settings'],
  audit: ['Audit Log'],
};

export default function Layout({ page, user, onNavigate, onLogout, onAction, children }: LayoutProps) {
  const [isoOpen, setIsoOpen] = useState(page === 'isos' || page === 'repo');
  const bc = crumbs[page] || [page];

  return (
    <div className="layout">
      <div className="topbar">
        <div className="breadcrumbs">
          {bc.map((c, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span style={{ margin: '0 4px', color: '#71717a' }}>/</span>}
              {i < bc.length - 1 ? (
                <a href="#" onClick={e => { e.preventDefault(); onNavigate('dashboard'); }}>{c}</a>
              ) : (
                <span>{c}</span>
              )}
            </React.Fragment>
          ))}
        </div>
        <div className="user-menu">
          <div className="avatar">{user?.username?.[0]?.toUpperCase() || '?'}</div>
          <span className="email">{user?.email || user?.username || ''}</span>
          <a href="#" className="logout" onClick={e => { e.preventDefault(); onLogout(); }}>Logout</a>
        </div>
      </div>
      <div className="body-wrap">
        <div className="sidebar">
          <div className="logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 24, height: 24 }}>
              <rect x="4" y="4" width="16" height="16" rx="2" />
              <rect x="9" y="9" width="6" height="6" rx="1" />
            </svg>
            KVM Manager
          </div>
          <nav>
            <a href="#" className={page === 'dashboard' ? 'active' : ''} onClick={e => { e.preventDefault(); onNavigate('dashboard'); }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 18, height: 18 }}>
                <rect x="3" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="14" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" />
              </svg>
              Dashboard
            </a>
            <div>
              <a href="#" onClick={e => { e.preventDefault(); setIsoOpen(!isoOpen); }}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 18, height: 18 }}>
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 6v6l4 2" />
                  </svg>
                  ISO Store
                </span>
                <span style={{ fontSize: 10, transition: 'transform 0.15s', transform: isoOpen ? 'rotate(90deg)' : '' }}>▶</span>
              </a>
              {isoOpen && (
                <div style={{ paddingLeft: 0 }}>
                  {[
                    { label: 'Browse', action: () => onNavigate('isos'), active: page === 'isos' },
                    { label: 'Repo', action: () => onNavigate('repo'), active: page === 'repo' },
                    { label: 'Upload', action: () => onAction?.('upload-iso'), active: false },
                    { label: 'Download', action: () => onAction?.('download-iso'), active: false },
                  ].map(item => (
                    <a key={item.label} href="#"
                      className={item.active ? 'active' : ''}
                      onClick={e => { e.preventDefault(); item.action(); }}
                      style={{ paddingLeft: 44 }}
                    >
                      {item.label}
                    </a>
                  ))}
                </div>
              )}
            </div>
            <a href="#" className={page === 'settings' ? 'active' : ''} onClick={e => { e.preventDefault(); onNavigate('settings'); }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 18, height: 18 }}>
                <circle cx="12" cy="12" r="3" />
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
              </svg>
              Settings
            </a>
            {user?.is_admin && (
              <a href="#" className={page === 'audit' ? 'active' : ''} onClick={e => { e.preventDefault(); onNavigate('audit'); }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 18, height: 18 }}>
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                </svg>
                Audit Log
              </a>
            )}
          </nav>
        </div>
        <div className="main">
          {children}
        </div>
      </div>
    </div>
  );
}

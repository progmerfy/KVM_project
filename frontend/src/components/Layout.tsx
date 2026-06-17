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

  const navItem = (label: string, icon: string, active: boolean, onClick: () => void) => (
    <a href="#" className={active ? 'active' : ''} onClick={e => { e.preventDefault(); onClick(); }}>
      <span className="nav-icon" dangerouslySetInnerHTML={{ __html: icon }} />
      {label}
    </a>
  );

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
          <a href="#" className="logout" onClick={e => { e.preventDefault(); onLogout(); }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            Logout
          </a>
        </div>
      </div>
      <div className="body-wrap">
        <div className="sidebar">
          <div className="logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="4" y="4" width="16" height="16" rx="2" />
              <rect x="9" y="9" width="6" height="6" rx="1" />
            </svg>
            <span>KVM Manager</span>
          </div>
          <nav>
            {navItem('Dashboard',
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>',
              page === 'dashboard',
              () => onNavigate('dashboard'))}
            <div className="nav-group">
              <a href="#" onClick={e => { e.preventDefault(); setIsoOpen(!isoOpen); }}>
                <span className="nav-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                </span>
                ISO Store
                <span className={`nav-arrow ${isoOpen ? 'open' : ''}`}>▶</span>
              </a>
              {isoOpen && (
                <div className="nav-sub">
                  {[
                    { label: 'Browse', action: () => onNavigate('isos'), active: page === 'isos' },
                    { label: 'Repo', action: () => onNavigate('repo'), active: page === 'repo' },
                    { label: 'Upload', action: () => onAction?.('upload-iso'), active: false },
                    { label: 'Download', action: () => onAction?.('download-iso'), active: false },
                  ].map(item => (
                    <a key={item.label} href="#"
                      className={item.active ? 'active' : ''}
                      onClick={e => { e.preventDefault(); item.action(); }}>
                      {item.label}
                    </a>
                  ))}
                </div>
              )}
            </div>
            {navItem('Settings',
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>',
              page === 'settings',
              () => onNavigate('settings'))}
            {user?.is_admin && navItem('Audit Log',
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
              page === 'audit',
              () => onNavigate('audit'))}
          </nav>
        </div>
        <div className="main">
          {children}
        </div>
      </div>
    </div>
  );
}

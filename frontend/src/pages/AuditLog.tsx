import React, { useState, useEffect, useCallback } from 'react';
import { AuditLog as AuditLogType } from '../types';
import { listAuditLogs } from '../api';

interface Props {
  addToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

const ACTIONS = ['', 'create', 'start', 'stop', 'destroy', 'delete', 'clone', 'restart', 'shutdown', 'login', 'logout', 'register'];
const RESOURCE_TYPES = ['', 'vm', 'host', 'image', 'user', 'network', 'backup', 'snapshot'];

const ACTION_STYLES: Record<string, { bg: string; color: string; icon: string }> = {
  create: { bg: 'rgba(34,197,94,0.12)', color: '#22c55e', icon: '+' },
  start: { bg: 'rgba(96,165,250,0.12)', color: '#60a5fa', icon: '▶' },
  stop: { bg: 'rgba(234,179,8,0.12)', color: '#eab308', icon: '■' },
  shutdown: { bg: 'rgba(234,179,8,0.12)', color: '#eab308', icon: '■' },
  destroy: { bg: 'rgba(239,68,68,0.12)', color: '#ef4444', icon: '✕' },
  delete: { bg: 'rgba(239,68,68,0.12)', color: '#ef4444', icon: '✕' },
  clone: { bg: 'rgba(167,139,250,0.12)', color: '#a78bfa', icon: '⧉' },
  restart: { bg: 'rgba(251,191,36,0.12)', color: '#fbbf24', icon: '↻' },
  login: { bg: 'rgba(34,211,238,0.12)', color: '#22d3ee', icon: '→' },
  logout: { bg: 'rgba(34,211,238,0.12)', color: '#22d3ee', icon: '←' },
  register: { bg: 'rgba(34,197,94,0.12)', color: '#22c55e', icon: '+' },
};

export default function AuditLog({ addToast }: Props) {
  const [logs, setLogs] = useState<AuditLogType[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [filterAction, setFilterAction] = useState('');
  const [filterResource, setFilterResource] = useState('');
  const [limit, setLimit] = useState(50);

  const load = useCallback(async (append: boolean) => {
    if (append) setLoadingMore(true); else setLoading(true);
    try {
      const params: any = { limit, offset: append ? offset : 0 };
      if (filterAction) params.action = filterAction;
      if (filterResource) params.resource_type = filterResource;
      const r = await listAuditLogs(params);
      if (append) {
        setLogs(prev => [...prev, ...r.logs]);
        setHasMore(r.logs.length === limit);
      } else {
        setLogs(r.logs);
        setHasMore(r.logs.length === limit);
        setOffset(0);
      }
      if (append) setOffset(prev => prev + r.logs.length);
    } catch (e: any) {
      addToast(e.message || 'Failed to load audit logs', 'error');
    }
    setLoading(false);
    setLoadingMore(false);
  }, [filterAction, filterResource, limit, offset, addToast]);

  useEffect(() => {
    load(false);
  }, [filterAction, filterResource, limit]);

  const selectStyle: React.CSSProperties = {
    padding: '8px 12px', background: '#0a0a0f', border: '1px solid #1e1e32',
    borderRadius: 8, color: '#fff', fontSize: 13, fontFamily: 'inherit',
    outline: 'none',
  };

  const actionCounts = logs.reduce((acc, l) => {
    acc[l.action] = (acc[l.action] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <>
      <div style={{ marginBottom: 28 }}>
        <h1>Audit Log</h1>
        <p className="sub">System audit trail (admin only)</p>
      </div>

      {/* Summary cards */}
      <div className="stats" style={{ marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-icon blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <div className="label">Total Entries</div>
          <div className="value blue">{logs.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          </div>
          <div className="label">Unique Actions</div>
          <div className="value green">{Object.keys(actionCounts).length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon purple">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
          </div>
          <div className="label">Resources Tracked</div>
          <div className="value purple">{new Set(logs.map(l => l.resource_type)).size}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="dash-section" style={{ marginBottom: 20, padding: '16px 20px' }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: '#71717a', marginBottom: 4 }}>Action</label>
            <select style={selectStyle} value={filterAction}
              onChange={e => setFilterAction(e.target.value)}>
              <option value="">All</option>
              {ACTIONS.filter(Boolean).map(a => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: '#71717a', marginBottom: 4 }}>Resource</label>
            <select style={selectStyle} value={filterResource}
              onChange={e => setFilterResource(e.target.value)}>
              <option value="">All</option>
              {RESOURCE_TYPES.filter(Boolean).map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: '#71717a', marginBottom: 4 }}>Per Page</label>
            <select style={selectStyle} value={limit}
              onChange={e => setLimit(Number(e.target.value))}>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>
          {filterAction || filterResource ? (
            <button className="btn btn-ghost" style={{ padding: '8px 14px' }}
              onClick={() => { setFilterAction(''); setFilterResource(''); }}>
              Clear Filters
            </button>
          ) : null}
        </div>
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : logs.length === 0 ? (
        <div className="empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 48, height: 48, opacity: 0.3 }}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <p>No audit log entries found</p>
        </div>
      ) : (
        <>
          <div className="dash-section" style={{ overflow: 'auto', padding: 0 }}>
            <table style={{
              width: '100%', minWidth: 800, borderCollapse: 'collapse', fontSize: 12,
            }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={thStyle}>Timestamp</th>
                  <th style={thStyle}>User</th>
                  <th style={thStyle}>Action</th>
                  <th style={thStyle}>Resource</th>
                  <th style={thStyle}>Name</th>
                  <th style={thStyle}>Details</th>
                  <th style={thStyle}>IP</th>
                  <th style={thStyle}>Status</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => {
                  const actStyle = ACTION_STYLES[log.action] || { bg: 'rgba(113,113,122,0.12)', color: '#a1a1aa', icon: '?' };
                  return (
                    <tr key={log.id}
                      style={{ borderBottom: '1px solid var(--border)', transition: 'background 0.1s' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                      onMouseLeave={e => e.currentTarget.style.background = ''}>
                      <td style={{ ...tdStyle, color: '#71717a', whiteSpace: 'nowrap' }}>
                        {log.created_at ? new Date(log.created_at).toLocaleString() : '-'}
                      </td>
                      <td style={{ ...tdStyle, fontFamily: 'inherit', fontWeight: 500 }}>{log.username}</td>
                      <td style={tdStyle}>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                          padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 500,
                          background: actStyle.bg, color: actStyle.color,
                        }}>
                          {actStyle.icon} {log.action}
                        </span>
                      </td>
                      <td style={{ ...tdStyle, fontFamily: 'inherit', color: '#71717a' }}>{log.resource_type}</td>
                      <td style={{ ...tdStyle, fontWeight: 500 }}>{log.resource_name || '-'}</td>
                      <td style={{
                        ...tdStyle, maxWidth: 200, overflow: 'hidden',
                        textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#71717a',
                      }}>
                        {log.details || '-'}
                      </td>
                      <td style={{ ...tdStyle, fontFamily: 'monospace', color: '#71717a' }}>{log.ip_address || '-'}</td>
                      <td style={tdStyle}>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12,
                          color: log.success ? '#22c55e' : '#ef4444',
                        }}>
                          <span style={{
                            width: 6, height: 6, borderRadius: '50%',
                            background: log.success ? '#22c55e' : '#ef4444',
                            display: 'inline-block',
                            boxShadow: log.success ? '0 0 6px #22c55e' : '0 0 6px #ef4444',
                          }} />
                          {log.success ? 'OK' : 'FAIL'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div style={{ textAlign: 'center', marginTop: 20 }}>
              <button className={`btn btn-ghost ${loadingMore ? 'loading' : ''}`}
                onClick={() => load(true)}
                disabled={loadingMore}
                style={{ padding: '10px 32px' }}>
                {loadingMore ? 'Loading...' : 'Load More'}
              </button>
            </div>
          )}
        </>
      )}
    </>
  );
}

const thStyle: React.CSSProperties = {
  padding: '10px 8px', textAlign: 'left', fontWeight: 500,
  color: '#71717a', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px',
  whiteSpace: 'nowrap',
};

const tdStyle: React.CSSProperties = {
  padding: '10px 8px', fontSize: 12,
};

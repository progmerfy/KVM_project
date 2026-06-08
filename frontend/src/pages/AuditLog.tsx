import React, { useState, useEffect, useCallback } from 'react';
import { AuditLog as AuditLogType } from '../types';
import { listAuditLogs } from '../api';

interface Props {
  addToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

const ACTIONS = ['', 'create', 'start', 'stop', 'destroy', 'delete', 'clone', 'restart', 'shutdown', 'login', 'logout'];
const RESOURCE_TYPES = ['', 'vm', 'host', 'image', 'user', 'network', 'backup', 'snapshot'];

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
    borderRadius: 6, color: '#fff', fontSize: 13, fontFamily: 'inherit',
  };

  return (
    <>
      <h1>Audit Log</h1>
      <p className="sub">System audit trail (admin only)</p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24, alignItems: 'end', flexWrap: 'wrap' }}>
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
          <label style={{ display: 'block', fontSize: 12, color: '#71717a', marginBottom: 4 }}>Resource Type</label>
          <select style={selectStyle} value={filterResource}
            onChange={e => setFilterResource(e.target.value)}>
            <option value="">All</option>
            {RESOURCE_TYPES.filter(Boolean).map(r => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: 12, color: '#71717a', marginBottom: 4 }}>Limit</label>
          <select style={selectStyle} value={limit}
            onChange={e => setLimit(Number(e.target.value))}>
            <option value={20}>20</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={200}>200</option>
          </select>
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
          <div className="detail-section" style={{ overflow: 'auto', padding: 0 }}>
            <table className="leases-table" style={{ width: '100%', minWidth: 700 }}>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>Name</th>
                  <th>Details</th>
                  <th>IP</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id}>
                    <td style={{ fontSize: 11, whiteSpace: 'nowrap', color: '#71717a' }}>
                      {log.created_at ? new Date(log.created_at).toLocaleString() : '-'}
                    </td>
                    <td style={{ fontFamily: 'inherit', fontWeight: 500 }}>{log.username}</td>
                    <td>
                      <span style={{
                        padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 500,
                        background: log.action === 'create' ? 'rgba(34,197,94,0.12)' :
                          log.action === 'delete' || log.action === 'destroy' ? 'rgba(239,68,68,0.12)' :
                            log.action === 'start' ? 'rgba(96,165,250,0.12)' :
                              log.action === 'stop' || log.action === 'shutdown' ? 'rgba(234,179,8,0.12)' : 'rgba(113,113,122,0.12)',
                        color: log.action === 'create' ? '#22c55e' :
                          log.action === 'delete' || log.action === 'destroy' ? '#ef4444' :
                            log.action === 'start' ? '#60a5fa' :
                              log.action === 'stop' || log.action === 'shutdown' ? '#eab308' : '#a1a1aa',
                      }}>
                        {log.action}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'inherit' }}>{log.resource_type}</td>
                    <td>{log.resource_name || '-'}</td>
                    <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#71717a', fontSize: 12 }}>
                      {log.details || '-'}
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{log.ip_address || '-'}</td>
                    <td>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12,
                        color: log.success ? '#22c55e' : '#ef4444',
                      }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: log.success ? '#22c55e' : '#ef4444', display: 'inline-block' }} />
                        {log.success ? 'OK' : 'FAIL'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div style={{ textAlign: 'center', marginTop: 20 }}>
              <button className={`btn btn-ghost ${loadingMore ? 'loading' : ''}`}
                onClick={() => load(true)}
                disabled={loadingMore}>Load More</button>
            </div>
          )}
        </>
      )}
    </>
  );
}

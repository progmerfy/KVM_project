import React, { useState, useEffect } from 'react';
import { User, HostInfo, StorageInfo, BackupSchedule } from '../types';
import {
  getHostInfo, getStorageInfo, listUsers, getMe,
  listSchedules, createSchedule, updateSchedule, deleteSchedule,
  apiJson,
} from '../api';

interface Props {
  user: User | null;
  addToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

type TabId = 'password' | 'server' | 'admin';

const TABS: { id: TabId; label: string; icon: string; adminOnly?: boolean }[] = [
  { id: 'password', label: 'Change Password', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>' },
  { id: 'server', label: 'Server Info', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>' },
  { id: 'admin', label: 'Administration', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>', adminOnly: true },
];

export default function Settings({ user, addToast }: Props) {
  const [tab, setTab] = useState<TabId>('password');
  const [hostInfo, setHostInfo] = useState<HostInfo | null>(null);
  const [storageInfo, setStorageInfo] = useState<StorageInfo | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [schedules, setSchedules] = useState<BackupSchedule[]>([]);

  const [oldPw, setOldPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwLoading, setPwLoading] = useState(false);

  const [editSched, setEditSched] = useState<BackupSchedule | null>(null);
  const [showSchedForm, setShowSchedForm] = useState(false);
  const [schedForm, setSchedForm] = useState({ vm_name: '', cron_expression: '0 */6 * * *', retention: 3 });
  const [schedLoading, setSchedLoading] = useState(false);

  useEffect(() => {
    getHostInfo().then(r => setHostInfo(r.host)).catch(() => { });
    getStorageInfo().then(r => setStorageInfo(r.storage)).catch(() => { });
    if (user?.is_admin) {
      listUsers().then(r => setUsers(r.users)).catch(() => { });
      listSchedules().then(r => setSchedules(r.schedules)).catch(() => { });
    }
  }, [user]);

  const handleChangePassword = async () => {
    if (!oldPw || !newPw) { addToast('Fill all fields', 'error'); return; }
    if (newPw !== confirmPw) { addToast('Passwords do not match', 'error'); return; }
    setPwLoading(true);
    try {
      await apiJson('/auth/change-password', 'POST', { old_password: oldPw, new_password: newPw });
      addToast('Password changed successfully', 'success');
      setOldPw(''); setNewPw(''); setConfirmPw('');
    } catch (e: any) {
      addToast(e.message || 'Failed to change password', 'error');
    }
    setPwLoading(false);
  };

  const refreshSchedules = async () => {
    try { const r = await listSchedules(); setSchedules(r.schedules); } catch { }
  };

  const handleSaveSchedule = async () => {
    if (!schedForm.vm_name || !schedForm.cron_expression) return;
    setSchedLoading(true);
    try {
      if (editSched) {
        await updateSchedule(editSched.id, schedForm);
        addToast('Schedule updated', 'success');
      } else {
        await createSchedule(schedForm);
        addToast('Schedule created', 'success');
      }
      setEditSched(null);
      setShowSchedForm(false);
      setSchedForm({ vm_name: '', cron_expression: '0 */6 * * *', retention: 3 });
      await refreshSchedules();
    } catch (e: any) {
      addToast(e.message || 'Failed to save schedule', 'error');
    }
    setSchedLoading(false);
  };

  const handleDeleteSchedule = async (id: number) => {
    try {
      await deleteSchedule(id);
      addToast('Schedule deleted', 'success');
      await refreshSchedules();
    } catch (e: any) {
      addToast(e.message || 'Failed to delete schedule', 'error');
    }
  };

  const AVATAR_COLORS = ['#60a5fa', '#a78bfa', '#22c55e', '#f59e0b', '#ef4444', '#22d3ee', '#fb923c', '#ec4899'];
  const userAvatar = (u: string) => {
    let hash = 0; for (let i = 0; i < u.length; i++) hash = u.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 12px', marginBottom: 14,
    background: '#0a0a0f', border: '1px solid #1e1e32', borderRadius: 8,
    color: '#fff', fontSize: 14, fontFamily: 'inherit',
    outline: 'none',
  };
  const labelStyle: React.CSSProperties = {
    display: 'block', marginBottom: 6, fontSize: 13, color: '#71717a',
  };

  return (
    <>
      <div style={{ marginBottom: 28 }}>
        <h1>Settings</h1>
        <p className="sub">System configuration and management</p>
      </div>

      <div className="tabs" style={{ marginBottom: 28 }}>
        {TABS.filter(t => !t.adminOnly || user?.is_admin).map(t => (
          <div key={t.id}
            className={`tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}>
            <span className="tab-icon" dangerouslySetInnerHTML={{ __html: t.icon }} />
            {t.label}
          </div>
        ))}
      </div>

      {/* ─── Password Tab ─── */}
      <div className={`tab-content ${tab === 'password' ? 'active' : ''}`}>
        <div className="detail-section" style={{ maxWidth: 460 }}>
          <h3 style={{ textTransform: 'none', letterSpacing: 0, color: '#e4e4e7', marginBottom: 20 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 8, verticalAlign: 'middle' }}>
              <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
            Change Password
          </h3>
          <div>
            <label style={labelStyle}>Current Password</label>
            <input type="password" style={inputStyle} placeholder="••••••••" value={oldPw}
              onChange={e => setOldPw(e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>New Password</label>
            <input type="password" style={inputStyle} placeholder="••••••••" value={newPw}
              onChange={e => setNewPw(e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>Confirm New Password</label>
            <input type="password" style={inputStyle} placeholder="••••••••" value={confirmPw}
              onChange={e => setConfirmPw(e.target.value)} />
          </div>
          <button className={`btn btn-primary ${pwLoading ? 'loading' : ''}`}
            onClick={handleChangePassword}
            disabled={pwLoading}
            style={{ marginTop: 4 }}>
            {pwLoading ? 'Changing...' : 'Change Password'}
          </button>
        </div>
      </div>

      {/* ─── Server Tab ─── */}
      <div className={`tab-content ${tab === 'server' ? 'active' : ''}`}>
        <div className="dash-two-col">
          <div className="dash-section">
            <h3>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
              Host Info
            </h3>
            <div className="row"><span className="label">Hostname</span><span className="value">{hostInfo?.hostname || '-'}</span></div>
            <div className="row"><span className="label">Uptime</span><span className="value">{hostInfo?.uptime || '-'}</span></div>
            <div className="row"><span className="label">CPU</span><span className="value">{hostInfo?.cpu?.model ? `${hostInfo.cpu.model} (${hostInfo.cpu.cores} cores)` : '-'}</span></div>
            <div className="row"><span className="label">Memory</span><span className="value">{hostInfo?.memory?.total_gb ? hostInfo.memory.total_gb + ' GB' : '-'}</span></div>
          </div>
          <div className="dash-section">
            <h3>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><rect x="2" y="3" width="20" height="18" rx="2"/><line x1="2" y1="9" x2="22" y2="9"/></svg>
              Image Storage
            </h3>
            {!storageInfo ? (
              <div style={{ color: '#71717a', fontSize: 13 }}>Loading...</div>
            ) : (
              <>
                <div className="row"><span className="label">Path</span><span className="value" style={{ fontSize: 12 }}>{storageInfo.path || '-'}</span></div>
                <div className="row"><span className="label">Total</span><span className="value">{storageInfo.total_gb?.toFixed(1)} GB</span></div>
                <div className="row"><span className="label">Used</span><span className="value">{storageInfo.used_gb?.toFixed(1)} GB</span></div>
                <div className="row"><span className="label">Free</span><span className="value" style={{ color: '#22c55e' }}>{storageInfo.free_gb?.toFixed(1)} GB</span></div>
                {storageInfo.total_gb && (
                  <div className="stat-bar-wrap" style={{ marginTop: 8 }}>
                    <div className="stat-bar blue" style={{ width: ((storageInfo.used_gb || 0) / storageInfo.total_gb * 100) + '%' }} />
                  </div>
                )}
              </>
            )}
          </div>
        </div>
        {hostInfo?.storage && hostInfo.storage.length > 0 && (
          <div className="dash-section" style={{ marginTop: 16 }}>
            <h3>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><rect x="2" y="3" width="20" height="18" rx="2"/><line x1="2" y1="9" x2="22" y2="9"/><circle cx="6" cy="6" r="1"/></svg>
              Filesystems
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {hostInfo.storage.map((fs, i) => {
                const pct = fs.size_gb ? (fs.used_gb! / fs.size_gb) * 100 : 0;
                return (
                  <div key={i}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4 }}>
                      <span style={{ fontWeight: 500 }}>{fs.filesystem || '-'}</span>
                      <span style={{ color: '#71717a' }}>{fs.used_gb?.toFixed(1)} / {fs.size_gb?.toFixed(1)} GB</span>
                    </div>
                    <div className="stat-bar-wrap">
                      <div className={`stat-bar ${pct > 80 ? 'red' : 'green'}`} style={{ width: pct + '%' }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ─── Admin Tab ─── */}
      {user?.is_admin && (
        <div className={`tab-content ${tab === 'admin' ? 'active' : ''}`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div className="dash-section">
              <h3>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                Users
              </h3>
              {users.length === 0 ? (
                <div style={{ color: '#71717a', fontSize: 13 }}>No users</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {users.map(u => (
                    <div key={u.id} className="row" style={{ alignItems: 'center' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{
                          width: 28, height: 28, borderRadius: 8, display: 'inline-flex',
                          alignItems: 'center', justifyContent: 'center',
                          background: userAvatar(u.username), color: '#000',
                          fontWeight: 600, fontSize: 12,
                        }}>{u.username[0].toUpperCase()}</span>
                        <span>
                          <div style={{ fontWeight: 500, fontSize: 14 }}>{u.username}</div>
                          <div style={{ fontSize: 11, color: '#71717a' }}>{u.email || 'no email'}</div>
                        </span>
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {u.is_admin && <span className="status-badge running" style={{ fontSize: 10, padding: '2px 8px' }}><span className="dot" />Admin</span>}
                        <span style={{ fontSize: 12, color: '#71717a' }}>
                          {u.created_at ? new Date(u.created_at).toLocaleDateString() : ''}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="dash-section">
              <h3>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                Backup Schedules
              </h3>
              <button className="btn btn-primary" style={{ marginBottom: 16, padding: '8px 16px', fontSize: 13 }}
                onClick={() => {
                  setEditSched(null);
                  setShowSchedForm(true);
                  setSchedForm({ vm_name: '', cron_expression: '0 */6 * * *', retention: 3 });
                }}>+ Add Schedule</button>
              {showSchedForm && (
                <div style={{ marginBottom: 20, padding: 20, background: '#0a0a0f', borderRadius: 10, border: '1px solid #1e1e32' }}>
                  <h4 style={{ fontSize: 14, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    {editSched ? 'Edit Schedule' : 'New Schedule'}
                  </h4>
                  <div>
                    <label style={labelStyle}>VM Name</label>
                    <input type="text" style={inputStyle} placeholder="my-vm" value={schedForm.vm_name}
                      onChange={e => setSchedForm({ ...schedForm, vm_name: e.target.value })} />
                  </div>
                  <div>
                    <label style={labelStyle}>Cron Expression</label>
                    <input type="text" style={inputStyle} placeholder="0 */6 * * *" value={schedForm.cron_expression}
                      onChange={e => setSchedForm({ ...schedForm, cron_expression: e.target.value })} />
                  </div>
                  <div>
                    <label style={labelStyle}>Retention (number of backups)</label>
                    <input type="number" min={1} style={inputStyle} value={schedForm.retention}
                      onChange={e => setSchedForm({ ...schedForm, retention: parseInt(e.target.value) || 3 })} />
                  </div>
                  <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                    <button className={`btn btn-primary ${schedLoading ? 'loading' : ''}`}
                      onClick={handleSaveSchedule} disabled={schedLoading}>Save</button>
                    <button className="btn btn-ghost" onClick={() => {
                      setEditSched(null);
                      setShowSchedForm(false);
                      setSchedForm({ vm_name: '', cron_expression: '0 */6 * * *', retention: 3 });
                    }}>Cancel</button>
                  </div>
                </div>
              )}
              {schedules.length === 0 ? (
                <div style={{ color: '#71717a', fontSize: 13 }}>No schedules configured</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {schedules.map(s => (
                    <div key={s.id}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '12px 16px', borderRadius: 8, border: '1px solid var(--border)',
                      }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(96,165,250,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                        </div>
                        <div>
                          <div style={{ fontWeight: 500, fontSize: 14 }}>{s.vm_name}</div>
                          <div style={{ fontSize: 12, color: '#71717a', fontFamily: 'monospace' }}>{s.cron_expression}</div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                        <div style={{ textAlign: 'right', fontSize: 12, color: '#71717a' }}>
                          <div>Retention: {s.retention}</div>
                          <div>{s.enabled ? 'Enabled' : 'Disabled'}</div>
                        </div>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn btn-ghost" style={{ padding: '5px 10px', fontSize: 11 }}
                            onClick={() => {
                              setEditSched(s);
                              setShowSchedForm(true);
                              setSchedForm({ vm_name: s.vm_name, cron_expression: s.cron_expression, retention: s.retention });
                            }}>Edit</button>
                          <button className="btn btn-danger" style={{ padding: '5px 10px', fontSize: 11 }}
                            onClick={() => handleDeleteSchedule(s.id)}>Delete</button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

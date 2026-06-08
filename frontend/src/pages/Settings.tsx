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

export default function Settings({ user, addToast }: Props) {
  const [tab, setTab] = useState<'password' | 'server' | 'admin'>('password');
  const [hostInfo, setHostInfo] = useState<HostInfo | null>(null);
  const [storageInfo, setStorageInfo] = useState<StorageInfo | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [schedules, setSchedules] = useState<BackupSchedule[]>([]);
  const [loading, setLoading] = useState(false);

  const [oldPw, setOldPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwLoading, setPwLoading] = useState(false);

  const [editSched, setEditSched] = useState<BackupSchedule | null>(null);
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
      addToast('Password changed', 'success');
      setOldPw(''); setNewPw(''); setConfirmPw('');
    } catch (e: any) {
      addToast(e.message || 'Failed', 'error');
    }
    setPwLoading(false);
  };

  const refreshSchedules = async () => {
    try {
      const r = await listSchedules();
      setSchedules(r.schedules);
    } catch { }
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
      setSchedForm({ vm_name: '', cron_expression: '0 */6 * * *', retention: 3 });
      await refreshSchedules();
    } catch (e: any) {
      addToast(e.message || 'Failed', 'error');
    }
    setSchedLoading(false);
  };

  const handleDeleteSchedule = async (id: number) => {
    try {
      await deleteSchedule(id);
      addToast('Schedule deleted', 'success');
      await refreshSchedules();
    } catch (e: any) {
      addToast(e.message || 'Failed', 'error');
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 12px', marginBottom: 14,
    background: '#0a0a0f', border: '1px solid #1e1e32', borderRadius: 6,
    color: '#fff', fontSize: 14, fontFamily: 'inherit',
  };
  const labelStyle: React.CSSProperties = {
    display: 'block', marginBottom: 6, fontSize: 13, color: '#71717a',
  };

  return (
    <>
      <h1>Settings</h1>
      <p className="sub">System configuration and management</p>

      <div className="tabs">
        <div className={`tab ${tab === 'password' ? 'active' : ''}`} onClick={() => setTab('password')}>Change Password</div>
        <div className={`tab ${tab === 'server' ? 'active' : ''}`} onClick={() => setTab('server')}>Server Info</div>
        {user?.is_admin && (
          <div className={`tab ${tab === 'admin' ? 'active' : ''}`} onClick={() => setTab('admin')}>Administration</div>
        )}
      </div>

      <div className={`tab-content ${tab === 'password' ? 'active' : ''}`}>
        <div className="detail-section" style={{ maxWidth: 440 }}>
          <h3 style={{ textTransform: 'none', letterSpacing: 0, color: '#e4e4e7' }}>Change Password</h3>
          <div>
            <label style={labelStyle}>Current Password</label>
            <input type="password" style={inputStyle} value={oldPw}
              onChange={e => setOldPw(e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>New Password</label>
            <input type="password" style={inputStyle} value={newPw}
              onChange={e => setNewPw(e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>Confirm New Password</label>
            <input type="password" style={inputStyle} value={confirmPw}
              onChange={e => setConfirmPw(e.target.value)} />
          </div>
          <button className={`btn btn-primary ${pwLoading ? 'loading' : ''}`}
            onClick={handleChangePassword}
            disabled={pwLoading}>Change Password</button>
        </div>
      </div>

      <div className={`tab-content ${tab === 'server' ? 'active' : ''}`}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="detail-section">
            <h3>Host Info</h3>
            <div className="row">
              <span className="label">Hostname</span>
              <span className="value">{hostInfo?.hostname || '-'}</span>
            </div>
            <div className="row">
              <span className="label">Uptime</span>
              <span className="value">{hostInfo?.uptime || '-'}</span>
            </div>
            <div className="row">
              <span className="label">CPU</span>
              <span className="value">{hostInfo?.cpu?.model ? `${hostInfo.cpu.model} (${hostInfo.cpu.cores} cores)` : '-'}</span>
            </div>
            <div className="row">
              <span className="label">Memory</span>
              <span className="value">{hostInfo?.memory?.total_gb ? hostInfo.memory.total_gb + ' GB' : '-'}</span>
            </div>
          </div>
          <div className="detail-section">
            <h3>Storage</h3>
            {!storageInfo ? (
              <div style={{ color: '#71717a', fontSize: 13 }}>Loading...</div>
            ) : (
              <>
                <div className="row">
                  <span className="label">Path</span>
                  <span className="value">{storageInfo.path || '-'}</span>
                </div>
                <div className="row">
                  <span className="label">Total</span>
                  <span className="value">{storageInfo.total_gb?.toFixed(1)} GB</span>
                </div>
                <div className="row">
                  <span className="label">Used</span>
                  <span className="value">{storageInfo.used_gb?.toFixed(1)} GB</span>
                </div>
                <div className="row">
                  <span className="label">Free</span>
                  <span className="value" style={{ color: '#22c55e' }}>{storageInfo.free_gb?.toFixed(1)} GB</span>
                </div>
              </>
            )}
          </div>
          {hostInfo?.storage && (
            <div className="detail-section">
              <h3>Filesystems</h3>
              {hostInfo.storage.map((fs, i) => (
                <div className="row" key={i}>
                  <span className="label">{fs.filesystem || '-'}</span>
                  <span className="value">{fs.used_gb?.toFixed(1)} / {fs.size_gb?.toFixed(1)} GB ({fs.avail_gb?.toFixed(1)} free)</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {user?.is_admin && (
        <div className={`tab-content ${tab === 'admin' ? 'active' : ''}`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="detail-section">
              <h3>Users</h3>
              <table className="leases-table" style={{ width: '100%' }}>
                <thead>
                  <tr><th>ID</th><th>Username</th><th>Email</th><th>Admin</th><th>Created</th></tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id}>
                      <td>{u.id}</td>
                      <td style={{ fontFamily: 'inherit', fontWeight: 500 }}>{u.username}</td>
                      <td>{u.email || '-'}</td>
                      <td>{u.is_admin ? 'Yes' : 'No'}</td>
                      <td style={{ color: '#71717a' }}>{u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="detail-section">
              <h3>Backup Schedules</h3>
              {editSched && (
                <div style={{ marginBottom: 16, padding: 16, background: '#0a0a0f', borderRadius: 8, border: '1px solid #1e1e32' }}>
                  <h4 style={{ fontSize: 14, marginBottom: 12 }}>{editSched ? 'Edit Schedule' : 'New Schedule'}</h4>
                  <div>
                    <label style={labelStyle}>VM Name</label>
                    <input type="text" style={inputStyle} value={schedForm.vm_name}
                      onChange={e => setSchedForm({ ...schedForm, vm_name: e.target.value })} />
                  </div>
                  <div>
                    <label style={labelStyle}>Cron Expression</label>
                    <input type="text" style={inputStyle} value={schedForm.cron_expression}
                      onChange={e => setSchedForm({ ...schedForm, cron_expression: e.target.value })} />
                  </div>
                  <div>
                    <label style={labelStyle}>Retention (number of backups)</label>
                    <input type="number" min={1} style={inputStyle} value={schedForm.retention}
                      onChange={e => setSchedForm({ ...schedForm, retention: parseInt(e.target.value) || 3 })} />
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className={`btn btn-primary ${schedLoading ? 'loading' : ''}`}
                      onClick={handleSaveSchedule} disabled={schedLoading}>Save</button>
                    <button className="btn btn-ghost" onClick={() => {
                      setEditSched(null);
                      setSchedForm({ vm_name: '', cron_expression: '0 */6 * * *', retention: 3 });
                    }}>Cancel</button>
                  </div>
                </div>
              )}
              <button className="btn btn-primary" style={{ marginBottom: 12, padding: '6px 14px', fontSize: 12 }}
                onClick={() => {
                  setEditSched(null);
                  setSchedForm({ vm_name: '', cron_expression: '0 */6 * * *', retention: 3 });
                }}>+ Add Schedule</button>
              <table className="leases-table" style={{ width: '100%' }}>
                <thead>
                  <tr><th>VM</th><th>Cron</th><th>Retention</th><th>Enabled</th><th>Last Run</th><th></th></tr>
                </thead>
                <tbody>
                  {schedules.map(s => (
                    <tr key={s.id}>
                      <td style={{ fontFamily: 'inherit', fontWeight: 500 }}>{s.vm_name}</td>
                      <td style={{ fontFamily: 'monospace' }}>{s.cron_expression}</td>
                      <td>{s.retention}</td>
                      <td>{s.enabled ? 'Yes' : 'No'}</td>
                      <td style={{ color: '#71717a' }}>{s.last_run || '-'}</td>
                      <td>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <a href="#" style={{ fontSize: 12, color: '#60a5fa' }}
                            onClick={e => {
                              e.preventDefault();
                              setEditSched(s);
                              setSchedForm({ vm_name: s.vm_name, cron_expression: s.cron_expression, retention: s.retention });
                            }}>Edit</a>
                          <a href="#" style={{ fontSize: 12, color: '#ef4444' }}
                            onClick={e => { e.preventDefault(); handleDeleteSchedule(s.id); }}>Delete</a>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {schedules.length === 0 && (
                <div style={{ color: '#71717a', fontSize: 13, marginTop: 8 }}>No schedules configured</div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

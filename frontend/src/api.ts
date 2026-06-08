const TOKEN = () => localStorage.getItem('token');

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { ...init?.headers, 'Authorization': 'Bearer ' + TOKEN() },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail?.message || body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export function apiJson<T>(path: string, method: string, body: unknown): Promise<T> {
  return api<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function getToken() { return TOKEN(); }

export function requireAuth() {
  if (!TOKEN()) window.location.href = '/auth/login-page?redirect=/';
}

// ── Host ──
export const getHostInfo = () => api<{ status: string; host: import('./types').HostInfo }>('/host/info');
export const getHostStats = () => api<{ status: string; stats: import('./types').HostStats }>('/host/stats');
export const getHostNetworks = () => api<{ status: string; networks: import('./types').Network[]; leases: import('./types').Lease[] }>('/host/networks');

// ── VM ──
export const listVMs = () => api<{ status: string; vms: import('./types').VM[] }>('/vm/list');
export const getVMInfo = (name: string) => api<{ status: string; vm: import('./types').VM }>('/vm/info/' + encodeURIComponent(name));
export const vmAction = (name: string, action: string) => apiJson<any>('/vm/' + action, 'POST', { name });
export const cloneVM = (name: string, newName: string) => apiJson<any>('/vm/clone', 'POST', { name, new_name: newName });
export const createVM = (body: any) => apiJson<any>('/vm/create', 'POST', body);
export const getVMetrics = (name: string) => api<{ status: string; metrics: import('./types').Metrics }>('/vm/metrics/' + encodeURIComponent(name));

// Snapshots
export const listSnapshots = (name: string) => api<{ status: string; snapshots: import('./types').Snapshot[] }>('/vm/snapshot/list/' + encodeURIComponent(name));
export const createSnapshot = (name: string, snapName: string) => api<any>('/vm/snapshot/create?name=' + encodeURIComponent(name) + '&snap_name=' + encodeURIComponent(snapName), { method: 'POST' });
export const revertSnapshot = (name: string, snapName: string) => api<any>('/vm/snapshot/revert?name=' + encodeURIComponent(name) + '&snap_name=' + encodeURIComponent(snapName), { method: 'POST' });
export const deleteSnapshot = (name: string, snapName: string) => api<any>('/vm/snapshot/delete?name=' + encodeURIComponent(name) + '&snap_name=' + encodeURIComponent(snapName), { method: 'DELETE' });

// Backups
export const listBackups = (name: string) => api<{ status: string; backups: import('./types').Backup[] }>('/vm/backup/list/' + encodeURIComponent(name));
export const createBackup = (name: string) => apiJson<any>('/vm/backup', 'POST', { name });
export const deleteBackup = (backupDir: string) => api<any>('/vm/backup/delete?backup_dir=' + encodeURIComponent(backupDir), { method: 'DELETE' });
export const listSchedules = () => api<{ status: string; schedules: import('./types').BackupSchedule[] }>('/vm/backup/schedules');
export const createSchedule = (s: { vm_name: string; cron_expression: string; retention: number }) => apiJson<any>('/vm/backup/schedules', 'POST', s);
export const updateSchedule = (id: number, s: any) => apiJson<any>('/vm/backup/schedules/' + id, 'PUT', s);
export const deleteSchedule = (id: number) => api<any>('/vm/backup/schedules/' + id, { method: 'DELETE' });

// Images
export const listImages = () => api<{ status: string; images: import('./types').Image[] }>('/images/list');
export const deleteImage = (name: string) => api<any>('/images/' + encodeURIComponent(name), { method: 'DELETE' });
export const listRepoImages = () => api<{ status: string; families: import('./types').RepoFamilies }>('/images/repo/list');
export const downloadCloudImage = (name: string) => apiJson<any>('/images/download-cloud?name=' + encodeURIComponent(name), 'POST', {});
export const getStorageInfo = () => api<{ status: string; storage: import('./types').StorageInfo }>('/images/storage/info');

// Auth
export const getMe = () => api<{ status: string; user: import('./types').User }>('/auth/me');
export const listUsers = () => api<{ status: string; users: import('./types').User[] }>('/auth/users');

// Audit
export const listAuditLogs = (params?: { limit?: number; offset?: number; action?: string; resource_type?: string }) => {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  if (params?.action) q.set('action', params.action);
  if (params?.resource_type) q.set('resource_type', params.resource_type);
  return api<{ status: string; logs: import('./types').AuditLog[] }>('/audit/logs?' + q.toString());
};

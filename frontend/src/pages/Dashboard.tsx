import React, { useState, useEffect, useCallback } from 'react';
import { User, VM, HostInfo, HostStats, Network, Lease, Image, RepoFamilies, StorageInfo } from '../types';
import {
  getHostInfo, getHostStats, getHostNetworks, listVMs, getVMInfo,
  getStorageInfo, listImages, listRepoImages, listSnapshots, listBackups,
  vmAction, cloneVM, createVM, deleteImage, downloadCloudImage,
  createSnapshot, revertSnapshot, deleteSnapshot,
  createBackup, deleteBackup, getVMetrics,
} from '../api';
import { Page, NavigateFn } from '../App';

interface Props {
  page: Page;
  selectedVM: string | null;
  navigate: NavigateFn;
  user: User | null;
  addToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
  isoAction: 'upload' | 'download' | null;
  setIsoAction: (v: null) => void;
}

function addActivity(action: string, name: string) {
  const list = JSON.parse(localStorage.getItem('activities') || '[]');
  list.unshift({ action, name, time: new Date().toLocaleString() });
  if (list.length > 50) list.pop();
  localStorage.setItem('activities', JSON.stringify(list));
}

function getActivities() {
  return JSON.parse(localStorage.getItem('activities') || '[]');
}

export default function Dashboard({ page, selectedVM, navigate, user, addToast, isoAction, setIsoAction }: Props) {
  const [vms, setVms] = useState<VM[]>([]);
  const [hostInfo, setHostInfo] = useState<HostInfo | null>(null);
  const [hostStats, setHostStats] = useState<HostStats | null>(null);
  const [networks, setNetworks] = useState<Network[]>([]);
  const [leases, setLeases] = useState<Lease[]>([]);
  const [images, setImages] = useState<Image[]>([]);
  const [storageInfo, setStorageInfo] = useState<StorageInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activities, setActivities] = useState<any[]>([]);

  const [showCreate, setShowCreate] = useState(false);
  const [showClone, setShowClone] = useState(false);
  const [cloneSource, setCloneSource] = useState('');
  const [cloneName, setCloneName] = useState('');
  const [confirmAction, setConfirmAction] = useState<{ action: string; vmName: string } | null>(null);
  const [createForm, setCreateForm] = useState({
    name: '', image: '', cpu: 1, ram: 1024, disk: 10, iso: '', ssh_key: '',
  });
  const [validationError, setValidationError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [backupLoading, setBackupLoading] = useState(false);
  const [deletingBackup, setDeletingBackup] = useState<string | null>(null);
  const [snapLoading, setSnapLoading] = useState<string | null>(null);

  const [repoFamilies, setRepoFamilies] = useState<RepoFamilies | null>(null);
  const [repoLoading, setRepoLoading] = useState(false);

  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState('');

  const [vmDetail, setVmDetail] = useState<VM | null>(null);
  const [snapshots, setSnapshots] = useState<any[]>([]);
  const [backups, setBackups] = useState<any[]>([]);
  const [snapName, setSnapName] = useState('');

  const recordActivity = useCallback((action: string, name: string) => {
    const list = JSON.parse(localStorage.getItem('activities') || '[]');
    list.unshift({ action, name, time: new Date().toLocaleString() });
    if (list.length > 50) list.pop();
    localStorage.setItem('activities', JSON.stringify(list));
    setActivities(list);
  }, []);

  useEffect(() => {
    setActivities(getActivities());
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [hinfo, hstats, nets, vmList, stInfo, imgList] = await Promise.all([
        getHostInfo().catch(() => null),
        getHostStats().catch(() => null),
        getHostNetworks().catch(() => null),
        listVMs().catch(() => null),
        getStorageInfo().catch(() => null),
        listImages().catch(() => null),
      ]);
      if (hinfo) setHostInfo(hinfo.host);
      if (hstats) setHostStats(hstats.stats);
      if (nets) { setNetworks(nets.networks); setLeases(nets.leases); }
      if (vmList) setVms(vmList.vms);
      if (stInfo) setStorageInfo(stInfo.storage);
      if (imgList) setImages(imgList.images);
    } catch { }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (page !== 'isos' && page !== 'repo') loadData();
  }, [page, loadData]);

  useEffect(() => {
    if (page === 'isos') {
      listImages().then(r => setImages(r.images)).catch(() => { });
      getStorageInfo().then(r => setStorageInfo(r.storage)).catch(() => { });
    }
    if (page === 'repo') {
      setRepoLoading(true);
      listRepoImages().then(r => setRepoFamilies(r.families)).catch(() => { }).finally(() => setRepoLoading(false));
    }
    if (isoAction === 'upload') setShowIsoUpload(true);
    if (isoAction === 'download') setShowIsoDownload(true);
    setIsoAction(null);
  }, [page, isoAction, setIsoAction]);

  useEffect(() => {
    if (page === 'detail' && selectedVM) {
      getVMInfo(selectedVM).then(r => setVmDetail(r.vm)).catch(() => setVmDetail(null));
      listSnapshots(selectedVM).then(r => setSnapshots(r.snapshots)).catch(() => setSnapshots([]));
      listBackups(selectedVM).then(r => setBackups(r.backups)).catch(() => setBackups([]));
    } else {
      setVmDetail(null);
    }
  }, [page, selectedVM]);

  const [showIsoUpload, setShowIsoUpload] = useState(false);
  const [showIsoDownload, setShowIsoDownload] = useState(false);

  const filtered = vms.filter(v => v.name.toLowerCase().includes(search.toLowerCase()));

  const handleVMAction = async (name: string, action: string) => {
    if (action === 'stop' || action === 'destroy') {
      setConfirmAction({ action, vmName: name });
      return;
    }
    if (action === 'delete') {
      setConfirmAction({ action: 'undefine', vmName: name });
      return;
    }
    setActionLoading(name);
    try {
      await vmAction(name, action);
      recordActivity(action === 'start' ? 'start' : action, name);
      addToast(`${action} initiated for ${name}`, 'success');
      loadData();
    } catch (e: any) {
      addToast(e.message || 'Action failed', 'error');
    }
    setActionLoading(null);
  };

  const confirmHandler = async () => {
    if (!confirmAction) return;
    const { action, vmName } = confirmAction;
    setActionLoading(vmName);
    try {
      const act = action === 'undefine' ? 'destroy' : action;
      await vmAction(vmName, act);
      if (action === 'undefine') {
        try { await vmAction(vmName, 'undefine'); } catch { }
        recordActivity('delete', vmName);
      } else {
        recordActivity(action === 'destroy' ? 'stop' : action, vmName);
      }
      addToast(`VM ${action === 'undefine' ? 'deleted' : action + 'ed'}`, 'success');
      loadData();
    } catch (e: any) {
      addToast(e.message || 'Action failed', 'error');
    }
    setActionLoading(null);
    setConfirmAction(null);
  };

  const handleClone = async () => {
    if (!cloneSource || !cloneName) return;
    setActionLoading(cloneSource);
    try {
      await cloneVM(cloneSource, cloneName);
      recordActivity('create', cloneName);
      addToast(`VM cloned to ${cloneName}`, 'success');
      setShowClone(false);
      setCloneName('');
      loadData();
    } catch (e: any) {
      addToast(e.message || 'Clone failed', 'error');
    }
    setActionLoading(null);
  };

  const handleCreate = async () => {
    const errs: string[] = [];
    if (!createForm.name.trim()) errs.push('VM Name is required');
    if (!createForm.image && !createForm.iso) errs.push('Select an Image or an ISO');
    if (errs.length) { setValidationError(errs.join('. ')); return; }
    setValidationError('');
    setActionLoading('create');
    try {
      const payload = {
        name: createForm.name.trim(),
        cpu: createForm.cpu,
        memory_mb: createForm.ram,
        disk_gb: createForm.disk,
        image: createForm.image || null,
        iso_path: createForm.iso || null,
        cloud_init_ssh_key: createForm.ssh_key || null,
      };
      await createVM(payload);
      recordActivity('create', createForm.name);
      addToast(`VM ${createForm.name} created`, 'success');
      setShowCreate(false);
      setCreateForm({ name: '', image: '', cpu: 1, ram: 1024, disk: 10, iso: '', ssh_key: '' });
      setValidationError('');
      loadData();
    } catch (e: any) {
      addToast(e.message || 'Create failed', 'error');
    }
    setActionLoading(null);
  };

  const handleDeleteImage = async (name: string) => {
    try {
      await deleteImage(name);
      addToast(`Image ${name} deleted`, 'success');
      const r = await listImages();
      setImages(r.images);
    } catch (e: any) {
      addToast(e.message || 'Delete failed', 'error');
    }
  };

  const handleDownloadCloud = async (name: string) => {
    try {
      await downloadCloudImage(name);
      addToast(`Download started for ${name}`, 'success');
    } catch (e: any) {
      addToast(e.message || 'Download failed', 'error');
    }
  };

  const divStyle = { marginBottom: 14 };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 12px', marginBottom: 14,
    background: '#0a0a0f', border: '1px solid #1e1e32', borderRadius: 6,
    color: '#fff', fontSize: 14, fontFamily: 'inherit',
  };

  const labelStyle: React.CSSProperties = {
    display: 'block', marginBottom: 6, fontSize: 13, color: '#71717a',
  };

  if (page === 'isos') {
    return (
      <>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div>
            <h1>ISO Store</h1>
            <p className="sub">Uploaded ISO images and disk images</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-primary" onClick={() => setShowIsoUpload(true)}>Upload ISO</button>
            <button className="btn btn-ghost" onClick={() => setShowIsoDownload(true)}>Download from URL</button>
          </div>
        </div>
        {storageInfo && (
          <div className="stats" style={{ marginBottom: 24 }}>
            <div className="stat-card">
              <div className="label">Image Storage</div>
              <div className="value">{storageInfo.total_gb?.toFixed(1) || '0'} GB</div>
              <div style={{ fontSize: 12, color: '#71717a' }}>
                {storageInfo.used_gb?.toFixed(1)} GB used · {storageInfo.free_gb?.toFixed(1)} GB free
              </div>
            </div>
          </div>
        )}
        <div className="detail-section" style={{ overflow: 'auto' }}>
          <table className="leases-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Format</th>
                <th>Size</th>
                <th>Path</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {images.map(img => (
                <tr key={img.name}>
                  <td style={{ fontWeight: 500, fontFamily: 'inherit' }}>{img.name}</td>
                  <td>{img.format || '-'}</td>
                  <td>{img.actual_size_bytes ? (img.actual_size_bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB' : img.virtual_size_gb ? img.virtual_size_gb + ' GB' : '-'}</td>
                  <td style={{ color: '#71717a' }}>{img.path || '-'}</td>
                  <td>
                    <button className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 12 }}
                      onClick={() => handleDeleteImage(img.name)}>Delete</button>
                  </td>
                </tr>
              ))}
              {images.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 40, color: '#71717a' }}>No images uploaded</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {showIsoUpload && (
          <div className="modal-overlay open" onClick={() => setShowIsoUpload(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <span className="close" onClick={() => setShowIsoUpload(false)}>✕</span>
              <h2>Upload ISO</h2>
              <div style={divStyle}>
                <label style={labelStyle}>Select ISO file</label>
                <input type="file" accept=".iso,.qcow2,.img" style={inputStyle}
                  onChange={e => setUploadFile(e.target.files?.[0] || null)} />
              </div>
              <div className="confirm-btns">
                <button className="btn btn-ghost" onClick={() => setShowIsoUpload(false)}>Cancel</button>
                <button className={`btn btn-primary ${uploading ? 'loading' : ''}`}
                  disabled={!uploadFile || uploading}
                  onClick={async () => {
                    if (!uploadFile) return;
                    setUploading(true);
                    try {
                      const form = new FormData();
                      form.append('file', uploadFile);
                      const res = await fetch('/images/upload', {
                        method: 'POST',
                        headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') },
                        body: form,
                      });
                      if (!res.ok) throw new Error('Upload failed');
                      addToast('ISO uploaded', 'success');
                      setShowIsoUpload(false);
                      setUploadFile(null);
                      const r = await listImages();
                      setImages(r.images);
                    } catch (e: any) { addToast(e.message || 'Upload failed', 'error'); }
                    setUploading(false);
                  }}
                >Upload</button>
              </div>
            </div>
          </div>
        )}

        {showIsoDownload && (
          <div className="modal-overlay open" onClick={() => setShowIsoDownload(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <span className="close" onClick={() => setShowIsoDownload(false)}>✕</span>
              <h2>Download ISO from URL</h2>
              <div style={divStyle}>
                <label style={labelStyle}>URL</label>
                <input type="url" placeholder="https://example.com/image.iso" style={inputStyle}
                  value={downloadUrl}
                  onChange={e => setDownloadUrl(e.target.value)} />
              </div>
              <div className="confirm-btns">
                <button className="btn btn-ghost" onClick={() => setShowIsoDownload(false)}>Cancel</button>
                <button className="btn btn-primary"
                  disabled={!downloadUrl}
                  onClick={async () => {
                    try {
                      const res = await fetch('/images/download', {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                          'Authorization': 'Bearer ' + localStorage.getItem('token'),
                        },
                        body: JSON.stringify({ url: downloadUrl }),
                      });
                      if (!res.ok) throw new Error('Download failed');
                      addToast('Download started', 'success');
                      setShowIsoDownload(false);
                      setDownloadUrl('');
                    } catch (e: any) { addToast(e.message || 'Download failed', 'error'); }
                  }}
                >Download</button>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  if (page === 'repo') {
    return (
      <>
        <h1>Repository Images</h1>
        <p className="sub">Cloud images available for download</p>
        {repoLoading ? (
          <div className="loading"><div className="spinner" /></div>
        ) : !repoFamilies ? (
          <div className="empty">Failed to load repository images</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {Object.entries(repoFamilies).map(([family, imgs]) => (
              <div key={family} className="detail-section">
                <h3 style={{ fontSize: 16, textTransform: 'none', letterSpacing: 0, marginBottom: 12, color: '#e4e4e7' }}>{family}</h3>
                {imgs.map(img => (
                  <div key={img.name}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '10px 0', borderBottom: '1px solid var(--border)',
                    }}>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: 14 }}>{img.name}</div>
                      <div style={{ fontSize: 12, color: '#71717a' }}>{img.description}</div>
                    </div>
                    <button className="btn btn-primary" style={{ padding: '6px 14px', fontSize: 12 }}
                      onClick={() => handleDownloadCloud(img.name)}>Download</button>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </>
    );
  }

  if (page === 'detail' && selectedVM) {
    if (!vmDetail) return <div className="loading"><div className="spinner" /></div>;

    return (
      <>
        <div className="detail-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <a href="#" onClick={e => { e.preventDefault(); navigate('dashboard'); }}
              style={{ color: '#71717a', fontSize: 14, cursor: 'pointer' }}>← Back</a>
            <h1 style={{ margin: 0 }}>{vmDetail.name}</h1>
            <span className={`status-badge ${vmDetail.state === 'running' ? 'running' : 'stopped'}`}>
              <span className="dot" />{vmDetail.state}
            </span>
          </div>
          <div className="actions" style={{ margin: 0 }}>
            {vmDetail.state === 'running' ? (
              <button className="btn btn-ghost" onClick={() => handleVMAction(vmDetail.name, 'stop')}>Stop</button>
            ) : (
              <button className="btn btn-primary" onClick={() => handleVMAction(vmDetail.name, 'start')}>Start</button>
            )}
            {vmDetail.state === 'running' && (
              <button className="btn btn-ghost" onClick={() => window.open('/vnc.html?vm=' + encodeURIComponent(vmDetail.name), '_blank')}>Console</button>
            )}
            <button className="btn btn-ghost" onClick={() => { setCloneSource(vmDetail.name); setCloneName(''); setShowClone(true); }}>Clone</button>
            <button className="btn btn-ghost" style={{ color: '#ef4444' }} onClick={() => handleVMAction(vmDetail.name, 'delete')}>Delete</button>
          </div>
        </div>

        <div className="detail-grid">
          <div className="detail-section">
            <h3>General</h3>
            <div className="row"><span className="label">State</span><span className="value">{vmDetail.state}</span></div>
            <div className="row"><span className="label">UUID</span><span className="value" style={{ fontFamily: 'monospace', fontSize: 12 }}>{vmDetail.uuid || '-'}</span></div>
            <div className="row"><span className="label">OS Type</span><span className="value">{vmDetail.os_type || '-'}</span></div>
            <div className="row"><span className="label">Autostart</span><span className="value">{vmDetail.autostart ? 'Yes' : 'No'}</span></div>
            <div className="row"><span className="label">Uptime</span><span className="value">{vmDetail.uptime_seconds ? Math.floor(vmDetail.uptime_seconds / 3600) + 'h ' + Math.floor((vmDetail.uptime_seconds % 3600) / 60) + 'm' : '-'}</span></div>
          </div>
          <div className="detail-section">
            <h3>Resources</h3>
            <div className="row"><span className="label">vCPUs</span><span className="value">{vmDetail.cpu || vmDetail.max_memory_mb ? vmDetail.cpu || '-' : '-'}</span></div>
            <div className="row"><span className="label">Memory</span><span className="value">{vmDetail.memory_mb ? vmDetail.memory_mb + ' MB' : vmDetail.max_memory_mb ? vmDetail.max_memory_mb + ' MB' : '-'}</span></div>
            <div className="row"><span className="label">IP Address</span><span className="value">{vmDetail.ip_address || vmDetail.guest_ip || '-'}</span></div>
            <div className="row"><span className="label">VNC Port</span><span className="value">{vmDetail.vnc_port || '-'}</span></div>
          </div>
          {vmDetail.disks && vmDetail.disks.length > 0 && (
            <div className="detail-section">
              <h3>Disks</h3>
              {vmDetail.disks.map((d, i) => (
                <div className="row" key={i}>
                  <span className="label">{d.device || d.target || 'disk'}</span>
                  <span className="value" style={{ fontSize: 12 }}>{d.source || d.type}{d.readonly ? ' (ro)' : ''}</span>
                </div>
              ))}
            </div>
          )}
          {vmDetail.interfaces && vmDetail.interfaces.length > 0 && (
            <div className="detail-section">
              <h3>Network Interfaces</h3>
              {vmDetail.interfaces.map((ni, i) => (
                <div className="row" key={i}>
                  <span className="label">{ni.type} {ni.mac ? '(' + ni.mac + ')' : ''}</span>
                  <span className="value">{ni.source || ni.model || '-'}</span>
                </div>
              ))}
            </div>
          )}
          <div className="detail-section">
            <h3>Snapshots</h3>
            <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
              <input type="text" placeholder="snapshot name" style={{ ...inputStyle, marginBottom: 0, flex: 1 }}
                value={snapName} onChange={e => setSnapName(e.target.value)} />
              <button className="btn btn-primary" style={{ padding: '6px 14px', fontSize: 12, whiteSpace: 'nowrap' }}
                disabled={!snapName}
                onClick={async () => {
                  try {
                    await createSnapshot(selectedVM, snapName);
                    addToast('Snapshot created', 'success');
                    setSnapName('');
                    listSnapshots(selectedVM).then(r => setSnapshots(r.snapshots)).catch(() => { });
                  } catch (e: any) { addToast(e.message || 'Failed', 'error'); }
                }}>Create</button>
            </div>
            {snapshots.length === 0 ? (
              <div style={{ color: '#71717a', fontSize: 13 }}>No snapshots</div>
            ) : (
              snapshots.map(s => (
                <div key={s.name} className="row">
                  <span className="label">{s.name}</span>
                  <span className="value" style={{ display: 'flex', gap: 6 }}>
                    <span style={{ fontSize: 11, color: '#71717a' }}>{s.created || ''}</span>
                    <a href="#" style={{ fontSize: 12, color: snapLoading === s.name ? '#71717a' : '#60a5fa' }}
                      onClick={e => { e.preventDefault();
                        if (snapLoading) return;
                        if (confirm('Revert to snapshot ' + s.name + '?')) {
                          setSnapLoading(s.name);
                          revertSnapshot(selectedVM, s.name).then(() => addToast('Reverted', 'success')).catch(e => addToast(e.message, 'error')).finally(() => setSnapLoading(null));
                        }
                      }}>{snapLoading === s.name ? 'Reverting...' : 'Revert'}</a>
                    <a href="#" style={{ fontSize: 12, color: snapLoading === s.name ? '#71717a' : '#ef4444' }}
                      onClick={e => { e.preventDefault();
                        if (snapLoading) return;
                        setSnapLoading(s.name);
                        deleteSnapshot(selectedVM, s.name).then(() => {
                          addToast('Snapshot deleted', 'success');
                          listSnapshots(selectedVM).then(r => setSnapshots(r.snapshots)).catch(() => { });
                        }).catch(e => addToast(e.message, 'error')).finally(() => setSnapLoading(null));
                      }}>{snapLoading === s.name ? 'Deleting...' : 'Delete'}</a>
                  </span>
                </div>
              ))
            )}
          </div>
          <div className="detail-section">
            <h3>Backups</h3>
            <button className={`btn btn-primary ${backupLoading ? 'loading' : ''}`}
              style={{ marginBottom: 12, padding: '6px 14px', fontSize: 12 }}
              disabled={backupLoading}
              onClick={async () => {
                setBackupLoading(true);
                try {
                  await createBackup(selectedVM);
                  addToast('Backup started', 'success');
                  listBackups(selectedVM).then(r => setBackups(r.backups)).catch(() => { });
                } catch (e: any) { addToast(e.message || 'Failed', 'error'); }
                setBackupLoading(false);
              }}>Create Backup</button>
            {backups.length === 0 ? (
              <div style={{ color: '#71717a', fontSize: 13 }}>No backups</div>
            ) : (
              backups.map(b => (
                <div key={b.timestamp} className="row">
                  <span className="label">{b.dir || b.timestamp}</span>
                  <span className="value">
                    <span style={{ fontSize: 11, color: '#71717a', marginRight: 8 }}>{b.timestamp}</span>
                    <a href="#" style={{ fontSize: 12, color: deletingBackup === b.dir ? '#71717a' : '#ef4444' }}
                      onClick={e => { e.preventDefault();
                        if (deletingBackup) return;
                        setDeletingBackup(b.dir);
                        deleteBackup(b.dir).then(() => {
                          addToast('Backup deleted', 'success');
                          listBackups(selectedVM).then(r => setBackups(r.backups)).catch(() => { });
                        }).catch(e => addToast(e.message, 'error')).finally(() => setDeletingBackup(null));
                      }}>{deletingBackup === b.dir ? 'Deleting...' : 'Delete'}</a>
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1>Dashboard</h1>
          <p className="sub">KVM virtualization manager</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input type="text" placeholder="Search VMs..." style={{
            padding: '8px 14px', background: '#0a0a0f', border: '1px solid #1e1e32',
            borderRadius: 6, color: '#fff', fontSize: 13, width: 200, fontFamily: 'inherit',
          }}
            value={search} onChange={e => setSearch(e.target.value)} />
          <button className="btn btn-primary" onClick={() => {
            setCreateForm({ name: '', image: '', cpu: 1, ram: 1024, disk: 10, iso: '', ssh_key: '' });
            setShowCreate(true);
          }}>+ New VM</button>
        </div>
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : (
        <>
          <div className="stats">
            <div className="stat-card">
              <div className="label">CPU Usage</div>
              <div className={`value ${(hostStats?.cpu?.used_percent || 0) > 80 ? 'red' : 'green'}`}>
                {hostStats?.cpu?.used_percent != null ? hostStats.cpu.used_percent.toFixed(0) + '%' : '-'}
              </div>
              <div style={{ fontSize: 12, color: '#71717a' }}>{hostInfo?.cpu?.cores || '?'} cores · {hostInfo?.cpu?.model || ''}</div>
            </div>
            <div className="stat-card">
              <div className="label">Memory</div>
              <div className={`value ${(hostStats?.memory?.used_percent || 0) > 80 ? 'red' : 'green'}`}>
                {hostStats?.memory?.used_percent != null ? hostStats.memory.used_percent.toFixed(0) + '%' : '-'}
              </div>
              <div style={{ fontSize: 12, color: '#71717a' }}>
                {hostStats?.memory?.used_mb ? (hostStats.memory.used_mb / 1024).toFixed(1) + ' GB' : '-'} / {hostStats?.memory?.total_mb ? (hostStats.memory.total_mb / 1024).toFixed(1) + ' GB' : hostInfo?.memory?.total_gb ? hostInfo.memory.total_gb + ' GB' : '-'}
              </div>
            </div>
            <div className="stat-card">
              <div className="label">Disk Usage</div>
              <div className={`value ${(hostStats?.storage?.[0]?.used_percent || 0) > 80 ? 'red' : 'green'}`}>
                {hostStats?.storage?.[0]?.used_percent != null ? hostStats.storage[0].used_percent.toFixed(0) + '%' : '-'}
              </div>
              <div style={{ fontSize: 12, color: '#71717a' }}>
                {hostStats?.storage?.[0]?.used_gb?.toFixed(1) || '-'} GB / {hostStats?.storage?.[0]?.size_gb?.toFixed(0) || '-'} GB
              </div>
            </div>
            <div className="stat-card">
              <div className="label">Image Storage</div>
              <div className="value green">{storageInfo?.total_gb?.toFixed(1) || '-'} GB</div>
              <div style={{ fontSize: 12, color: '#71717a' }}>
                {storageInfo?.used_gb?.toFixed(1) || '0'} GB used · {storageInfo?.free_gb?.toFixed(1) || '0'} GB free
              </div>
            </div>
            <div className="stat-card">
              <div className="label">Virtual Machines</div>
              <div className="value" style={{ color: '#60a5fa' }}>{vms.length}</div>
              <div style={{ fontSize: 12, color: '#71717a' }}>
                {vms.filter(v => v.state === 'running').length} running · {vms.filter(v => v.state !== 'running').length} stopped
              </div>
            </div>
          </div>

          <div style={{ marginBottom: 32 }}>
            <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Virtual Machines</h2>
            {filtered.length === 0 ? (
              <div className="empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 48, height: 48, opacity: 0.3 }}>
                  <rect x="4" y="4" width="16" height="16" rx="2" />
                  <line x1="8" y1="9" x2="16" y2="9" />
                  <line x1="8" y1="13" x2="14" y2="13" />
                  <line x1="8" y1="17" x2="12" y2="17" />
                </svg>
                <p>No virtual machines found</p>
              </div>
            ) : (
              <div className="vm-grid">
                {filtered.map(vm => (
                  <div key={vm.name} className="vm-card" onClick={() => navigate('detail', vm.name)}>
                    <div className="top">
                      <div className="name">{vm.name}</div>
                      <span className={`status-badge ${vm.state === 'running' ? 'running' : 'stopped'}`}>
                        <span className="dot" />{vm.state}
                      </span>
                    </div>
                    <div className="info">
                      <div className="info-item">CPU: <span>{vm.cpu || '-'}</span></div>
                      <div className="info-item">RAM: <span>{vm.memory_mb ? vm.memory_mb + ' MB' : '-'}</span></div>
                      <div className="info-item">IP: <span>{vm.ip_address || vm.guest_ip || '-'}</span></div>
                      <div className="info-item">Uptime: <span>{vm.uptime_seconds ? Math.floor(vm.uptime_seconds / 3600) + 'h' : '-'}</span></div>
                    </div>
                    <div className="actions" onClick={e => e.stopPropagation()}>
                      {vm.state === 'running' ? (
                        <button className="btn btn-ghost" style={{ padding: '5px 12px', fontSize: 12 }}
                          onClick={() => handleVMAction(vm.name, 'stop')}>Stop</button>
                      ) : (
                        <button className="btn btn-primary" style={{ padding: '5px 12px', fontSize: 12 }}
                          onClick={() => handleVMAction(vm.name, 'start')}>Start</button>
                      )}
                      {vm.state === 'running' && (
                        <button className="btn btn-ghost" style={{ padding: '5px 12px', fontSize: 12 }}
                          onClick={() => window.open('/vnc.html?vm=' + encodeURIComponent(vm.name), '_blank')}>Console</button>
                      )}
                      <button className="btn btn-ghost" style={{ padding: '5px 12px', fontSize: 12 }}
                        onClick={() => { setCloneSource(vm.name); setCloneName(''); setShowClone(true); }}>Clone</button>
                      <button className="btn btn-ghost" style={{ padding: '5px 12px', fontSize: 12, color: '#ef4444' }}
                        onClick={() => handleVMAction(vm.name, 'delete')}>Delete</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ marginBottom: 32 }}>
            <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Network Interfaces</h2>
            <div className="net-grid">
              <div className="detail-section">
                <h3>Networks</h3>
                {networks.length === 0 ? (
                  <div style={{ color: '#71717a', fontSize: 13 }}>No networks</div>
                ) : (
                  networks.map(net => (
                    <div className="row" key={net.name}>
                      <span className="label">{net.name}</span>
                      <span className="value" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {net.active ? <span style={{ color: '#22c55e', fontSize: 10 }}>●</span> : <span style={{ color: '#ef4444', fontSize: 10 }}>●</span>}
                        {net.active ? 'Active' : 'Inactive'}
                        {net.subnet && <span style={{ fontSize: 11, color: '#71717a' }}>({net.subnet})</span>}
                      </span>
                    </div>
                  ))
                )}
              </div>
              <div className="detail-section">
                <h3>DHCP Leases</h3>
                {leases.length === 0 ? (
                  <div style={{ color: '#71717a', fontSize: 13 }}>No active leases</div>
                ) : (
                  <table className="leases-table">
                    <thead>
                      <tr><th>Network</th><th>IP</th><th>MAC</th><th>Hostname</th></tr>
                    </thead>
                    <tbody>
                      {leases.map((l, i) => (
                        <tr key={i}>
                          <td>{l.network}</td>
                          <td>{l.ip}</td>
                          <td>{l.mac}</td>
                          <td>{l.hostname || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

          <div>
            <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Recent Activity</h2>
            {activities.length === 0 ? (
              <div style={{ color: '#71717a', fontSize: 13 }}>No activity yet</div>
            ) : (
              <div className="activity-list">
                {activities.slice(0, 20).map((a, i) => (
                  <div key={i} className="activity-item">
                    <div className={`act-icon ${a.action}`}>
                      {a.action === 'create' ? '+' : a.action === 'start' ? '▶' : a.action === 'stop' ? '■' : '✕'}
                    </div>
                    <div className="act-text">
                      <div className="act-name">{a.action === 'create' ? 'Created' : a.action === 'start' ? 'Started' : a.action === 'stop' ? 'Stopped' : 'Deleted'} <strong>{a.name}</strong></div>
                      <div className="act-time">{a.time}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {showCreate && (
        <div className="modal-overlay open" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ width: 520 }}>
            <span className="close" onClick={() => setShowCreate(false)}>✕</span>
            <h2>Create Virtual Machine</h2>
            <div className="create-form">
              <label>VM Name</label>
              <input type="text" placeholder="my-vm" value={createForm.name}
                onChange={e => { setCreateForm({ ...createForm, name: e.target.value }); setValidationError(''); }} />
              <label>ISO (for OS installation)</label>
              <select value={createForm.iso}
                onChange={e => { setCreateForm({ ...createForm, iso: e.target.value }); setValidationError(''); }}>
                <option value="">Select ISO...</option>
                {images.filter(i => i.name.endsWith('.iso')).map(img => (
                  <option key={img.name} value={img.path || img.name}>{img.name}</option>
                ))}
              </select>
              <label>Disk Image (optional — blank disk if omitted)</label>
              <select value={createForm.image}
                onChange={e => { setCreateForm({ ...createForm, image: e.target.value }); setValidationError(''); }}>
                <option value="">None (blank disk)</option>
                {images.filter(i => !i.name.endsWith('.iso')).map(img => (
                  <option key={img.name} value={img.path || img.name}>{img.name}</option>
                ))}
              </select>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label>vCPUs</label>
                  <input type="number" min={1} value={createForm.cpu}
                    onChange={e => setCreateForm({ ...createForm, cpu: parseInt(e.target.value) || 1 })} />
                </div>
                <div>
                  <label>RAM (MB)</label>
                  <input type="number" min={256} step={256} value={createForm.ram}
                    onChange={e => setCreateForm({ ...createForm, ram: parseInt(e.target.value) || 1024 })} />
                </div>
              </div>
              <label>Disk Size (GB)</label>
              <input type="number" min={1} value={createForm.disk}
                onChange={e => setCreateForm({ ...createForm, disk: parseInt(e.target.value) || 10 })} />
              <label>SSH Public Key (optional)</label>
              <textarea rows={3} placeholder="ssh-rsa ..." value={createForm.ssh_key}
                onChange={e => setCreateForm({ ...createForm, ssh_key: e.target.value })} />
              {validationError && (
                <div style={{ color: '#ef4444', fontSize: 13, marginTop: 8, padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 6 }}>
                  {validationError}
                </div>
              )}
            </div>
            <div className="confirm-btns">
              <button className="btn btn-ghost" onClick={() => { setShowCreate(false); setValidationError(''); }}>Cancel</button>
              <button className={`btn btn-primary ${actionLoading === 'create' ? 'loading' : ''}`}
                disabled={actionLoading === 'create'}
                onClick={handleCreate}>{actionLoading === 'create' ? 'Creating...' : 'Create VM'}</button>
            </div>
          </div>
        </div>
      )}

      {showClone && (
        <div className="modal-overlay open" onClick={() => setShowClone(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <span className="close" onClick={() => setShowClone(false)}>✕</span>
            <h2>Clone VM</h2>
            <p style={{ fontSize: 13, color: '#71717a', marginBottom: 16 }}>
              Source: <strong>{cloneSource}</strong>
            </p>
            <div style={{ marginBottom: 14 }}>
              <label style={labelStyle}>New VM Name</label>
              <input type="text" placeholder="cloned-vm" style={inputStyle}
                value={cloneName} onChange={e => setCloneName(e.target.value)} />
            </div>
            <div className="confirm-btns">
              <button className="btn btn-ghost" onClick={() => setShowClone(false)}>Cancel</button>
              <button className={`btn btn-primary ${actionLoading === cloneSource ? 'loading' : ''}`}
                disabled={!cloneName || actionLoading === cloneSource}
                onClick={handleClone}>Clone</button>
            </div>
          </div>
        </div>
      )}

      {confirmAction && (
        <div className="modal-overlay open" onClick={() => setConfirmAction(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>Confirm</h2>
            <p style={{ fontSize: 14, color: '#71717a', marginBottom: 20 }}>
              Are you sure you want to {confirmAction.action === 'undefine' ? 'delete' : confirmAction.action} <strong>{confirmAction.vmName}</strong>?
            </p>
            <div className="confirm-btns">
              <button className="btn btn-ghost" onClick={() => setConfirmAction(null)}>Cancel</button>
              <button className={`btn ${confirmAction.action === 'undefine' ? 'btn-ghost' : 'btn-primary'}`}
                style={confirmAction.action === 'undefine' ? { color: '#ef4444', borderColor: '#ef4444' } : {}}
                onClick={confirmHandler}>Confirm</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

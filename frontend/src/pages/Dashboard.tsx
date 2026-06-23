import React, { useState, useEffect, useCallback, useRef } from 'react';
import { User, VM, HostInfo, HostStats, Network, Lease, Image, RepoFamilies, StorageInfo } from '../types';
import {
  getHostInfo, getHostStats, getHostNetworks, listVMs, getVMInfo,
  getStorageInfo, listImages, listRepoImages, listSnapshots, listBackups,
  vmAction, cloneVM, createVM, deleteImage, downloadCloudImage, downloadRepoIso,
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
  const [downloading, setDownloading] = useState<Set<string>>(new Set());

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
  const [expandedFamily, setExpandedFamily] = useState<string | null>(null);

  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState('');

  const [isoSearch, setIsoSearch] = useState('');
  const [isoSort, setIsoSort] = useState<'name'|'size'|'date'|'type'>('date');
  const [isoSortDir, setIsoSortDir] = useState<'asc'|'desc'>('desc');
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<'grid'|'table'>('grid');
  const prevPage = useRef(page);

  const [imageUsage, setImageUsage] = useState<Record<string, string[]>>({});
  const [isosLoading, setIsosLoading] = useState(true);
  const [downloadStarted, setDownloadStarted] = useState<Record<string, number>>(() => {
    const saved: Record<string, number> = {};
    try {
      const raw = sessionStorage.getItem('dl_started');
      if (raw) Object.assign(saved, JSON.parse(raw));
    } catch {}
    return saved;
  });

  function saveDownloadStarted(update: Record<string, number>) {
    setDownloadStarted(update);
    sessionStorage.setItem('dl_started', JSON.stringify(update));
  }

  function markDownloadStart(name: string) {
    saveDownloadStarted({ ...downloadStarted, [name]: Date.now() });
  }

  function clearDownloadStart(name: string) {
    const next = { ...downloadStarted };
    delete next[name];
    saveDownloadStarted(next);
  }

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
      setIsosLoading(true);
      Promise.all([
        listImages().then(r => setImages(r.images)),
        getStorageInfo().then(r => setStorageInfo(r.storage)),
        fetch('/images/usage', { headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') } })
          .then(r => r.json().then(d => setImageUsage(d.usage || {})))
      ]).catch(() => {}).finally(() => setIsosLoading(false));
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
    markDownloadStart(name);
    setDownloading(prev => new Set(prev).add(name));
    try {
      await downloadCloudImage(name);
      addToast(`Download started for ${name}`, 'success');
    } catch (e: any) {
      addToast(e.message || 'Download failed', 'error');
    } finally {
      setDownloading(prev => { const next = new Set(prev); next.delete(name); return next; });
    }
  };

  const handleDownloadIso = async (name: string) => {
    markDownloadStart(name);
    setDownloading(prev => new Set(prev).add(name));
    try {
      await downloadRepoIso(name);
      addToast(`Download started for ${name}`, 'success');
    } catch (e: any) {
      addToast(e.message || 'Download failed', 'error');
    } finally {
      setDownloading(prev => { const next = new Set(prev); next.delete(name); return next; });
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

  function isoFamily(name: string): string | null {
    const n = name.toLowerCase();
    if (n.includes('ubuntu')) return 'ubuntu';
    if (n.includes('debian')) return 'debian';
    if (n.includes('fedora')) return 'fedora';
    if (n.includes('centos')) return 'centos';
    if (n.includes('rocky')) return 'rocky';
    if (n.includes('almalinux')) return 'almalinux';
    if (n.includes('rhel')) return 'rhel';
    if (n.includes('arch')) return 'arch';
    if (n.includes('freebsd')) return 'freebsd';
    if (n.includes('suse') || n.includes('opensuse')) return 'suse';
    if (n.includes('alpine')) return 'alpine';
    if (n.includes('astra')) return 'astra';
    if (n.includes('redos') || n.includes('red os') || n.includes('murom')) return 'redos';
    return null;
  }

  function distroImgKey(name: string): string {
    const n = name.toLowerCase();
    if (n.includes('ubuntu')) return 'ubuntu';
    if (n.includes('debian')) return 'debian';
    if (n.includes('fedora')) return 'fedora';
    if (n.includes('centos')) return 'centos';
    if (n.includes('rocky')) return 'rocky';
    if (n.includes('almalinux')) return 'almalinux';
    if (n.includes('arch')) return 'arch';
    if (n.includes('freebsd')) return 'freebsd';
    if (n.includes('suse')) return 'suse';
    if (n.includes('opensuse')) return 'suse';
    if (n.includes('alpine')) return 'alpine';
    if (n.includes('astra')) return 'astra';
    if (n.includes('redos') || n.includes('red os') || n.includes('murom')) return 'redos';
    return 'unknown';
  }

  if (page === 'isos' && prevPage.current !== 'isos') {
    setIsosLoading(true);
  }
  prevPage.current = page;

  const OS_COLORS: Record<string, { bg: string; icon: string; accent: string }> = {
    ubuntu: { bg: 'linear-gradient(135deg, #E95420 0%, #C7431A 100%)', icon: '/logos/ubuntu.svg', accent: '#E95420' },
    debian: { bg: 'linear-gradient(135deg, #D70A53 0%, #A8083E 100%)', icon: '/logos/debian.svg', accent: '#D70A53' },
    fedora: { bg: 'linear-gradient(135deg, #294172 0%, #1C2F52 100%)', icon: '/logos/fedora.svg', accent: '#294172' },
    centos: { bg: 'linear-gradient(135deg, #262577 0%, #1C1B5C 100%)', icon: '/logos/centos.svg', accent: '#262577' },
    rocky: { bg: 'linear-gradient(135deg, #10B981 0%, #0D9668 100%)', icon: '/logos/rocky.svg', accent: '#10B981' },
    almalinux: { bg: 'linear-gradient(135deg, #005E8C 0%, #004569 100%)', icon: '/logos/almalinux.svg', accent: '#005E8C' },
    rhel: { bg: 'linear-gradient(135deg, #CC0000 0%, #990000 100%)', icon: '/logos/centos.svg', accent: '#CC0000' },
    arch: { bg: 'linear-gradient(135deg, #1793D1 0%, #0E6B9E 100%)', icon: '/logos/arch.svg', accent: '#1793D1' },
    freebsd: { bg: 'linear-gradient(135deg, #AB2B28 0%, #871F1D 100%)', icon: '/logos/freebsd.svg', accent: '#AB2B28' },
    suse: { bg: 'linear-gradient(135deg, #30BA78 0%, #24985F 100%)', icon: '/logos/opensuse.svg', accent: '#30BA78' },
    alpine: { bg: 'linear-gradient(135deg, #0D597F 0%, #094361 100%)', icon: '/logos/alpine.svg', accent: '#0D597F' },
    astra: { bg: 'linear-gradient(135deg, #1a5276 0%, #0e3451 100%)', icon: '/logos/astra.svg', accent: '#1a5276' },
    redos: { bg: 'linear-gradient(135deg, #cc2b2b 0%, #991f1f 100%)', icon: '/logos/redos.svg', accent: '#cc2b2b' },
    unknown: { bg: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', icon: '', accent: '#6366f1' },
  };
  const FAMILY_NAMES: Record<string, string> = {
    ubuntu: 'Ubuntu',
    debian: 'Debian',
    fedora: 'Fedora',
    centos: 'CentOS Stream',
    rocky: 'Rocky Linux',
    almalinux: 'AlmaLinux',
    rhel: 'RHEL',
    arch: 'Arch Linux',
    freebsd: 'FreeBSD',
    suse: 'openSUSE / SUSE',
    alpine: 'Alpine Linux',
    astra: 'Astra Linux',
    redos: 'RED OS',
    unknown: 'Other',
  };
  /* Backend uses 'debian' and 'rhel' as family-group keys; remap to group logos */
  const FAMILY_GROUP_OS: Record<string, string> = {
    debian: 'debian',
    rhel: 'fedora',
  };

  if (page === 'isos') {
    if (isosLoading) {
      return <div className="loading"><div className="spinner" /></div>;
    }
    const sorted = [...images].sort((a, b) => {
      let cmp = 0;
      if (isoSort === 'name') cmp = a.name.localeCompare(b.name);
      else if (isoSort === 'size') cmp = (b.actual_size_bytes || 0) - (a.actual_size_bytes || 0);
      else if (isoSort === 'date') cmp = (b.mtime || 0) - (a.mtime || 0);
      else if (isoSort === 'type') cmp = (a.name.endsWith('.iso') ? 1 : 0) - (b.name.endsWith('.iso') ? 1 : 0);
      return isoSortDir === 'asc' ? cmp : -cmp;
    });
    const filtered = isoSearch ? sorted.filter(i => i.name.toLowerCase().includes(isoSearch.toLowerCase())) : sorted;
    const selCount = selectedImages.size;
    const selectAll = filtered.length > 0 && filtered.every(i => selectedImages.has(i.name));

    return (
      <>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <h1>Image Storage</h1>
            <p className="sub">{images.length} file{images.length !== 1 ? 's' : ''} in {storageInfo?.path || 'storage pool'}</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost" onClick={async () => {
              const r = await listImages();
              setImages(r.images);
              const u = await fetch('/images/usage', { headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') } }).then(r => r.json());
              setImageUsage(u.usage || {});
              addToast('Refreshed', 'info');
            }} style={{ padding: '6px 12px', fontSize: 12 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 4 }}><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
              Refresh
            </button>
            <button className="btn btn-primary" onClick={() => setShowIsoUpload(true)} style={{ padding: '6px 14px', fontSize: 12 }}>Upload</button>
            <button className="btn btn-ghost" onClick={() => setShowIsoDownload(true)} style={{ padding: '6px 14px', fontSize: 12 }}>Download URL</button>
          </div>
        </div>
        {storageInfo && (
          <div className="stats" style={{ marginBottom: 16 }}>
            <div className="stat-card" style={{ padding: '12px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div className="stat-icon green" style={{ width: 36, height: 36 }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 11, color: '#71717a' }}>{storageInfo.path}</div>
                  <div style={{ display: 'flex', gap: 16, alignItems: 'baseline', marginTop: 2 }}>
                    <span style={{ fontWeight: 600, fontSize: 18 }}>{storageInfo.total_gb?.toFixed(1)} <span style={{ fontSize: 11, fontWeight: 400, color: '#71717a' }}>GB</span></span>
                    <span style={{ fontSize: 12, color: '#71717a' }}>{storageInfo.used_gb?.toFixed(1)} GB used · {storageInfo.free_gb?.toFixed(1)} GB free</span>
                  </div>
                  <div className="stat-bar-wrap" style={{ marginTop: 6, height: 6 }}>
                    <div className="stat-bar green" style={{ width: ((storageInfo.used_gb || 0) / (storageInfo.total_gb || 1) * 100) + '%', height: 6 }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 160, position: 'relative' }}>
            <svg style={{ position: 'absolute', left: 10, top: '50%', marginTop: -7, pointerEvents: 'none' }} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#71717a" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" placeholder="Search files…" value={isoSearch} onChange={e => setIsoSearch(e.target.value)}
              style={{ width: '100%', padding: '7px 10px 7px 30px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--text)', fontSize: 13, outline: 'none' }} />
          </div>
          <select value={isoSort} onChange={e => setIsoSort(e.target.value as any)}
            style={{ padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--text)', fontSize: 12, outline: 'none' }}>
            <option value="date">Date</option>
            <option value="name">Name</option>
            <option value="size">Size</option>
            <option value="type">Type</option>
          </select>
          <button className="btn btn-ghost" onClick={() => setIsoSortDir(d => d === 'asc' ? 'desc' : 'asc')} style={{ padding: '6px 10px', fontSize: 12 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ transform: isoSortDir === 'desc' ? 'none' : 'rotate(180deg)' }}><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg>
          </button>
          <div style={{ display: 'flex', borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden' }}>
            <button onClick={() => setViewMode('grid')} style={{ padding: '6px 10px', background: viewMode === 'grid' ? 'rgba(255,255,255,0.06)' : 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text)', fontSize: 12 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
            </button>
            <button onClick={() => setViewMode('table')} style={{ padding: '6px 10px', background: viewMode === 'table' ? 'rgba(255,255,255,0.06)' : 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text)', fontSize: 12 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            </button>
          </div>
          {filtered.length > 0 && (
            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, cursor: 'pointer', color: '#71717a', userSelect: 'none' }}>
              <input type="checkbox" checked={selectAll} onChange={() => {
                if (selectAll) setSelectedImages(new Set());
                else setSelectedImages(new Set(filtered.map(i => i.name)));
              }} style={{ accentColor: '#6366f1' }} />
              Select all
            </label>
          )}
          {selCount > 0 && (
            <button className="btn btn-danger" style={{ padding: '6px 12px', fontSize: 12 }}
              onClick={async () => {
                if (!confirm(`Delete ${selCount} file${selCount !== 1 ? 's' : ''}?`)) return;
                for (const name of selectedImages) {
                  try { await deleteImage(name); } catch {}
                }
                addToast(`Deleted ${selCount} file${selCount !== 1 ? 's' : ''}`, 'success');
                setSelectedImages(new Set());
                const r = await listImages();
                setImages(r.images);
              }}>Delete {selCount > 0 ? `(${selCount})` : ''}</button>
          )}
        </div>
        {filtered.length === 0 ? (
          <div className="empty">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 48, height: 48, opacity: 0.3 }}><rect x="2" y="3" width="20" height="18" rx="2"/><line x1="2" y1="9" x2="22" y2="9"/><circle cx="6" cy="6" r="1"/></svg>
            <p>{isoSearch ? 'No matching files' : 'No images uploaded'}</p>
          </div>
        ) : viewMode === 'grid' ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 10 }}>
            {filtered.map(img => {
              const isIso = img.name.endsWith('.iso');
              const sizeGb = img.actual_size_bytes ? (img.actual_size_bytes / 1024 / 1024 / 1024).toFixed(2) : img.virtual_size_gb ? img.virtual_size_gb.toFixed(1) : null;
              const family = isoFamily(img.name);
              const os = family ? OS_COLORS[family] : null;
              const usedIn = imageUsage[img.name];
              const sel = selectedImages.has(img.name);
              return (
                <div key={img.name} className="vm-card" style={{ cursor: 'default', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', border: sel ? '1px solid #6366f1' : undefined }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                      <div style={{
                        width: 36, height: 36, borderRadius: 10,
                        background: os ? os.bg : (isIso ? 'rgba(234,179,8,0.12)' : 'rgba(96,165,250,0.12)'),
                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                      }}>
                        {os ? <img src={os.icon} alt="" style={{ width: 18, height: 18, filter: 'brightness(0) invert(1)' }} /> : isIso ? (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#eab308" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                        ) : (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2"><rect x="2" y="3" width="20" height="18" rx="2"/><line x1="2" y1="9" x2="22" y2="9"/><circle cx="6" cy="6" r="1"/></svg>
                        )}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <input type="checkbox" checked={sel} onChange={() => {
                            const next = new Set(selectedImages);
                            sel ? next.delete(img.name) : next.add(img.name);
                            setSelectedImages(next);
                          }} style={{ accentColor: '#6366f1' }} />
                          <div className="name" style={{ fontSize: 13, wordBreak: 'break-all' }}>
                            {img.name}
                            {downloading.has(img.name) && <span style={{ marginLeft: 6, fontSize: 10, color: '#eab308' }}>↓</span>}
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                          <span style={{ fontSize: 11, padding: '1px 5px', borderRadius: 4, background: isIso ? 'rgba(234,179,8,0.12)' : 'rgba(96,165,250,0.12)', color: isIso ? '#eab308' : '#60a5fa', fontWeight: 500 }}>{img.format || 'raw'}</span>
                          {family && <span style={{ fontSize: 11, color: '#71717a' }}>{FAMILY_NAMES[family] || family}</span>}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, fontSize: 12, color: '#71717a', flexWrap: 'wrap', alignItems: 'center' }}>
                      {downloading.has(img.name) ? (
                        <span style={{ color: '#eab308' }}><span className="spinner" style={{ width: 10, height: 10, borderWidth: 2, marginRight: 4 }} />Downloading…</span>
                      ) : (
                        <span>Size: <strong style={{ color: !img.actual_size_bytes && !img.virtual_size_gb ? '#ef4444' : '#e4e4e7' }}>{sizeGb || '0.00'} GB</strong></span>
                      )}
                      {!downloading.has(img.name) && !img.actual_size_bytes && !img.virtual_size_gb && (() => {
                        const t = downloadStarted[img.name];
                        if (t) {
                          const elapsed = Math.round((Date.now() - t) / 1000);
                          return <span style={{ color: '#f59e0b', fontSize: 11 }}>DL started {elapsed < 60 ? elapsed + 's ago' : Math.round(elapsed / 60) + 'm ago'}</span>;
                        }
                        return <span style={{ color: '#ef4444', fontSize: 11 }}>Stale / failed · <button className="btn btn-ghost" style={{ padding: 0, fontSize: 11, color: '#ef4444', textDecoration: 'underline', border: 'none', background: 'none', cursor: 'pointer' }} onClick={() => clearDownloadStart(img.name)}>clear</button></span>;
                      })()}
                      {img.mtime && <span>Modified: <strong style={{ color: '#e4e4e7' }}>{new Date(img.mtime * 1000).toLocaleDateString()}</strong></span>}
                    </div>
                    {usedIn && usedIn.length > 0 && (
                      <div style={{ marginTop: 6, fontSize: 11, color: '#6366f1' }}>In use by: {usedIn.join(', ')}</div>
                    )}
                  </div>
                  <div style={{ marginTop: 10, display: 'flex', gap: 6 }}>
                    <button className="btn btn-danger" style={{ padding: '5px 10px', fontSize: 11 }}
                      onClick={async () => {
                        if (!confirm(`Delete "${img.name}"?`)) return;
                        await deleteImage(img.name);
                        addToast(`Deleted ${img.name}`, 'success');
                        const r = await listImages();
                        setImages(r.images);
                      }}>Delete</button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="dash-section" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 500, fontSize: 11, color: '#71717a', letterSpacing: '0.5px' }}>
                      <input type="checkbox" checked={selectAll} onChange={() => {
                        if (selectAll) setSelectedImages(new Set());
                        else setSelectedImages(new Set(filtered.map(i => i.name)));
                      }} style={{ accentColor: '#6366f1' }} />
                    </th>
                    <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 500, fontSize: 11, color: '#71717a', letterSpacing: '0.5px' }}>Name</th>
                    <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 500, fontSize: 11, color: '#71717a', letterSpacing: '0.5px' }}>Type</th>
                    <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 500, fontSize: 11, color: '#71717a', letterSpacing: '0.5px' }}>Size</th>
                    <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 500, fontSize: 11, color: '#71717a', letterSpacing: '0.5px' }}>Modified</th>
                    <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 500, fontSize: 11, color: '#71717a', letterSpacing: '0.5px' }}>Used by</th>
                    <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 500, fontSize: 11, color: '#71717a', letterSpacing: '0.5px' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(img => {
                    const isIso = img.name.endsWith('.iso');
                    const usedIn = imageUsage[img.name];
                    const sel = selectedImages.has(img.name);
                    return (
                      <tr key={img.name} style={{ borderBottom: '1px solid var(--border)', background: sel ? 'rgba(99,102,241,0.04)' : '' }}>
                        <td style={{ padding: '8px 12px' }}>
                          <input type="checkbox" checked={sel} onChange={() => {
                            const next = new Set(selectedImages);
                            sel ? next.delete(img.name) : next.add(img.name);
                            setSelectedImages(next);
                          }} style={{ accentColor: '#6366f1' }} />
                        </td>
                        <td style={{ padding: '8px 12px', fontWeight: 500 }}>
                          {img.name}
                          {downloading.has(img.name) && (
                            <span style={{ marginLeft: 6, fontSize: 10, color: '#eab308' }}>↓ downloading</span>
                          )}
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          <span style={{ padding: '1px 6px', borderRadius: 4, background: isIso ? 'rgba(234,179,8,0.12)' : 'rgba(96,165,250,0.12)', color: isIso ? '#eab308' : '#60a5fa', fontSize: 11 }}>{img.format || 'raw'}</span>
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: '#71717a', whiteSpace: 'nowrap', fontSize: 12 }}>
                          {downloading.has(img.name) ? (
                            <span style={{ color: '#eab308' }}><span className="spinner" style={{ width: 10, height: 10, borderWidth: 2, marginRight: 4, verticalAlign: 'middle' }} />DL</span>
                          ) : img.actual_size_bytes ? (
                            (img.actual_size_bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
                          ) : img.virtual_size_gb ? (
                            img.virtual_size_gb.toFixed(1) + ' GB'
                          ) : (() => {
                            const t = downloadStarted[img.name];
                            return t
                              ? <span style={{ color: '#f59e0b' }}>0.00 GB · DL {Math.round((Date.now() - t) / 60000)}m ago</span>
                              : <span style={{ color: '#ef4444' }}>0.00 GB</span>;
                          })()}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: '#71717a', whiteSpace: 'nowrap' }}>
                          {img.mtime ? new Date(img.mtime * 1000).toLocaleDateString() : '-'}
                        </td>
                        <td style={{ padding: '8px 12px', color: usedIn?.length ? '#6366f1' : '#71717a', fontSize: 12 }}>
                          {usedIn?.length ? usedIn.join(', ') : '-'}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                          <button className="btn btn-danger" style={{ padding: '3px 8px', fontSize: 11 }}
                            onClick={async () => {
                              if (!confirm(`Delete "${img.name}"?`)) return;
                              await deleteImage(img.name);
                              addToast(`Deleted ${img.name}`, 'success');
                              const r = await listImages();
                              setImages(r.images);
                            }}>Delete</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {showIsoUpload && (
          <div className="modal-overlay open" onClick={() => setShowIsoUpload(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <span className="close" onClick={() => setShowIsoUpload(false)}>✕</span>
              <h2>Upload File</h2>
              <div style={divStyle}>
                <label style={labelStyle}>Select file (.iso, .qcow2, .img)</label>
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
                      addToast('File uploaded', 'success');
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
              <h2>Download from URL</h2>
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
    const entries = Object.entries(repoFamilies || {});
    const activeFamily = expandedFamily || entries[0]?.[0] || '';
    const activeImgs = repoFamilies?.[activeFamily] || [];

    return (
      <>
        <div style={{ marginBottom: 24 }}>
          <h1>Repository Images</h1>
          <p className="sub">Cloud images and installation ISOs available for download</p>
        </div>
        {repoLoading ? (
          <div className="loading"><div className="spinner" /></div>
        ) : !repoFamilies ? (
          <div className="empty">Failed to load repository images</div>
        ) : (
          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
            <div style={{ width: 200, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {entries.map(([family, imgs]) => {
                const osKey = FAMILY_GROUP_OS[family] || family;
                const os = OS_COLORS[osKey] || { bg: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', icon: family[0]?.toUpperCase(), accent: '#6366f1' };
                const selected = activeFamily === family;
                return (
                  <div key={family} onClick={() => setExpandedFamily(family)}
                    style={{
                      cursor: 'pointer', userSelect: 'none', display: 'flex', alignItems: 'center', gap: 10,
                      padding: '10px 12px', borderRadius: 10,
                      background: selected ? 'rgba(255,255,255,0.04)' : 'transparent',
                      border: selected ? '1px solid rgba(255,255,255,0.08)' : '1px solid transparent',
                      transition: 'all 0.15s',
                    }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: 8,
                      background: os.bg, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', flexShrink: 0,
                    }}><img src={os.icon} alt="" style={{ width: 20, height: 20, filter: 'brightness(0) invert(1)' }} /></div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 500, fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{FAMILY_NAMES[family] || family}</div>
                      <div style={{ fontSize: 11, color: '#71717a' }}>{imgs.length} image{imgs.length !== 1 ? 's' : ''}</div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="dash-section" style={{ flex: 1, padding: 0, overflow: 'hidden' }}>
              <div style={{
                padding: '12px 16px', borderBottom: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: 10,
              }}>
                {(() => {
                  const hdrKey = FAMILY_GROUP_OS[activeFamily] || activeFamily;
                  const hdrOs = OS_COLORS[hdrKey];
                  return hdrOs ? (
                    <div style={{
                      width: 28, height: 28, borderRadius: 6,
                      background: hdrOs.bg, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', flexShrink: 0,
                    }}><img src={hdrOs.icon} alt="" style={{ width: 18, height: 18, filter: 'brightness(0) invert(1)' }} /></div>
                  ) : null;
                })()}
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{
                    activeFamily === 'debian' ? 'Debian / Ubuntu' :
                    activeFamily === 'rhel' ? 'RHEL / Fedora / CentOS' :
                    FAMILY_NAMES[activeFamily] || activeFamily
                  }</div>
                  <div style={{ fontSize: 11, color: '#71717a' }}>{activeImgs.length} available</div>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {activeImgs.map((img, idx) => {
                  const imgKey = distroImgKey(img.name);
                  const imgOs = OS_COLORS[imgKey] || OS_COLORS.unknown;
                  return (
                  <div key={img.name}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '10px 16px',
                      borderBottom: idx < activeImgs.length - 1 ? '1px solid var(--border)' : 'none',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                      <div style={{
                        width: 28, height: 28, borderRadius: 6,
                        background: imgOs.bg, display: 'flex', alignItems: 'center',
                        justifyContent: 'center', flexShrink: 0,
                      }}>
                        {imgOs.icon ? (
                          <img src={imgOs.icon} alt="" style={{ width: 18, height: 18, filter: 'brightness(0) invert(1)' }} />
                        ) : img.is_iso ? (
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                        ) : (
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
                        )}
                      </div>
                      <div>
                        <div style={{ fontWeight: 500, fontSize: 13 }}>{img.name}</div>
                        {img.description && <div style={{ fontSize: 11, color: '#71717a' }}>{img.description}</div>}
                      </div>
                    </div>
                    <button className="btn btn-primary" style={{ padding: '5px 14px', fontSize: 11, flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 6 }}
                      onClick={() => img.is_iso ? handleDownloadIso(img.name) : handleDownloadCloud(img.name)} disabled={downloading.has(img.name)}>
                      {downloading.has(img.name) ? (
                        <><span className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} /> Downloading</>
                      ) : 'Download'}
                    </button>
                  </div>
                );})}
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  if (page === 'detail' && selectedVM) {
    if (!vmDetail) return <div className="loading"><div className="spinner" /></div>;
    const running = vmDetail.state === 'running';

    return (
      <>
        <div className="detail-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <a href="#" onClick={e => { e.preventDefault(); navigate('dashboard'); }}
              style={{ color: '#71717a', fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
              Back
            </a>
            <h1 style={{ margin: 0 }}>{vmDetail.name}</h1>
            <span className={`status-badge ${running ? 'running' : 'stopped'}`}>
              <span className="dot" />{vmDetail.state}
            </span>
          </div>
          <div className="actions" style={{ margin: 0 }}>
            {running ? (
              <button className="btn btn-ghost" onClick={() => handleVMAction(vmDetail.name, 'stop')}>■ Stop</button>
            ) : (
              <button className="btn btn-success" onClick={() => handleVMAction(vmDetail.name, 'start')}>▶ Start</button>
            )}
            {running && (
              <button className="btn btn-ghost" onClick={() => window.open('/vm/vnc/console/' + encodeURIComponent(vmDetail.name), '_blank')}>🖥 Console</button>
            )}
            <button className="btn btn-ghost" onClick={() => { setCloneSource(vmDetail.name); setCloneName(''); setShowClone(true); }}>⧉ Clone</button>
            <button className="btn btn-danger" onClick={() => handleVMAction(vmDetail.name, 'delete')}>Delete</button>
          </div>
        </div>

        <div className="detail-grid">
          <div className="dash-section">
            <h3>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><rect x="4" y="4" width="16" height="16" rx="2"/><line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="13" x2="14" y2="13"/><line x1="8" y1="17" x2="12" y2="17"/></svg>
              General
            </h3>
            <div className="row"><span className="label"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, flexShrink: 0 }}><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg>State</span><span className="value">{vmDetail.state}</span></div>
            <div className="row"><span className="label"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, flexShrink: 0 }}><path d="M10 3H6a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2v-4"/><path d="M15 3h6v6"/><path d="M10 14L21 3"/></svg>UUID</span><span className="value" style={{ fontFamily: 'monospace', fontSize: 12 }}>{vmDetail.uuid || '-'}</span></div>
            <div className="row"><span className="label"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, flexShrink: 0 }}><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>OS Type</span><span className="value">{vmDetail.os_type || '-'}</span></div>
            <div className="row"><span className="label"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, flexShrink: 0 }}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>Uptime</span><span className="value">{vmDetail.uptime_seconds ? Math.floor(vmDetail.uptime_seconds / 3600) + 'h ' + Math.floor((vmDetail.uptime_seconds % 3600) / 60) + 'm' : '-'}</span></div>
            <div className="row"><span className="label"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, flexShrink: 0 }}><path d="M18.36 6.64a9 9 0 11-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>Autostart</span><span className="value">{vmDetail.autostart ? 'Yes' : 'No'}</span></div>
            {vmDetail.root_password && (
              <div className="row"><span className="label">Root Password</span><span className="value" style={{ fontFamily: 'monospace', fontSize: 13, color: '#f59e0b' }}>{vmDetail.root_password}</span></div>
            )}
          </div>
          <div className="dash-section">
            <h3>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><rect x="4" y="4" width="16" height="22" rx="2"/><line x1="9" y1="2" x2="9" y2="6"/><line x1="15" y1="2" x2="15" y2="6"/></svg>
              Resources
            </h3>
            <div className="row"><span className="label"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, flexShrink: 0 }}><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="2" x2="9" y2="4"/><line x1="15" y1="2" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="22"/><line x1="15" y1="20" x2="15" y2="22"/><line x1="2" y1="9" x2="4" y2="9"/><line x1="2" y1="15" x2="4" y2="15"/><line x1="20" y1="9" x2="22" y2="9"/><line x1="20" y1="15" x2="22" y2="15"/></svg>vCPUs</span><span className="value">{vmDetail.cpu || '-'}</span></div>
            {vmDetail.cpu && <div className="stat-bar-wrap" style={{ margin: '0 0 8px 0' }}><div className="stat-bar blue" style={{ width: Math.min((vmDetail.cpu / 16) * 100, 100) + '%' }} /></div>}
            <div className="row"><span className="label"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, flexShrink: 0 }}><rect x="4" y="4" width="16" height="6" rx="1"/><rect x="4" y="14" width="16" height="6" rx="1"/><line x1="8" y1="10" x2="8" y2="14"/><line x1="16" y1="10" x2="16" y2="14"/></svg>Memory</span><span className="value">{vmDetail.memory_mb ? vmDetail.memory_mb + ' MB' : vmDetail.max_memory_mb ? vmDetail.max_memory_mb + ' MB' : '-'}</span></div>
            {vmDetail.memory_mb && <div className="stat-bar-wrap" style={{ margin: '0 0 8px 0' }}><div className="stat-bar purple" style={{ width: Math.min((vmDetail.memory_mb / (hostInfo?.memory?.total_mb || 32768)) * 100, 100) + '%' }} /></div>}
            <div className="row"><span className="label"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, flexShrink: 0 }}><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/></svg>IP Address</span><span className="value" style={{ fontFamily: 'monospace' }}>{vmDetail.ip_address || vmDetail.guest_ip || '-'}</span></div>
            <div className="row"><span className="label"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, flexShrink: 0 }}><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>VNC Port</span><span className="value">{vmDetail.vnc_port || '-'}</span></div>
          </div>
          {vmDetail.disks && vmDetail.disks.length > 0 && (
            <div className="dash-section">
              <h3>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><rect x="2" y="3" width="20" height="18" rx="2"/><line x1="2" y1="9" x2="22" y2="9"/><circle cx="6" cy="6" r="1"/></svg>
                Disks
              </h3>
              {vmDetail.disks.map((d, i) => (
                <div className="row" key={i}>
                  <span className="label">{d.device || d.target || 'disk'}</span>
                  <span className="value" style={{ fontSize: 12 }}>{d.source || d.type}{d.readonly ? ' (ro)' : ''}</span>
                </div>
              ))}
            </div>
          )}
          {vmDetail.interfaces && vmDetail.interfaces.length > 0 && (
            <div className="dash-section">
              <h3>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
                Network Interfaces
              </h3>
              {vmDetail.interfaces.map((ni, i) => (
                <div className="row" key={i}>
                  <span className="label">{ni.type} {ni.mac ? '(' + ni.mac + ')' : ''}</span>
                  <span className="value">{ni.source || ni.model || '-'}</span>
                </div>
              ))}
            </div>
          )}
          <div className="dash-section">
            <h3>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
              Snapshots
            </h3>
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
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {snapshots.map(s => (
                  <div key={s.name}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13,
                    }}>
                    <div>
                      <div style={{ fontWeight: 500 }}>{s.name}</div>
                      <div style={{ fontSize: 11, color: '#71717a' }}>{s.created || ''}</div>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 11 }}
                        disabled={!!snapLoading}
                        onClick={() => {
                          if (confirm('Revert to snapshot ' + s.name + '?')) {
                            setSnapLoading(s.name);
                            revertSnapshot(selectedVM, s.name).then(() => addToast('Reverted', 'success')).catch(e => addToast(e.message, 'error')).finally(() => setSnapLoading(null));
                          }
                        }}>{snapLoading === s.name ? 'Reverting...' : 'Revert'}</button>
                      <button className="btn btn-danger" style={{ padding: '4px 10px', fontSize: 11 }}
                        disabled={!!snapLoading}
                        onClick={() => {
                          setSnapLoading(s.name);
                          deleteSnapshot(selectedVM, s.name).then(() => {
                            addToast('Snapshot deleted', 'success');
                            listSnapshots(selectedVM).then(r => setSnapshots(r.snapshots)).catch(() => { });
                          }).catch(e => addToast(e.message, 'error')).finally(() => setSnapLoading(null));
                        }}>{snapLoading === s.name ? 'Deleting...' : 'Delete'}</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="dash-section">
            <h3>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6 }}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              Backups
            </h3>
            <button className={`btn btn-primary ${backupLoading ? 'loading' : ''}`}
              style={{ marginBottom: 12, padding: '8px 16px', fontSize: 12 }}
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
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {backups.map(b => (
                  <div key={b.timestamp}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13,
                    }}>
                    <div>
                      <div style={{ fontWeight: 500 }}>{b.dir || b.timestamp}</div>
                      <div style={{ fontSize: 11, color: '#71717a' }}>{b.timestamp}</div>
                    </div>
                    <button className="btn btn-danger" style={{ padding: '4px 10px', fontSize: 11 }}
                      disabled={!!deletingBackup}
                      onClick={() => {
                        setDeletingBackup(b.dir);
                        deleteBackup(b.dir).then(() => {
                          addToast('Backup deleted', 'success');
                          listBackups(selectedVM).then(r => setBackups(r.backups)).catch(() => { });
                        }).catch(e => addToast(e.message, 'error')).finally(() => setDeletingBackup(null));
                      }}>{deletingBackup === b.dir ? 'Deleting...' : 'Delete'}</button>
                  </div>
                ))}
              </div>
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
              <div className="stat-icon blue">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="4" width="16" height="16" rx="2"/><line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="13" x2="14" y2="13"/><line x1="8" y1="17" x2="12" y2="17"/></svg>
              </div>
              <div className="label">CPU Usage</div>
              <div className={`value ${(hostStats?.cpu?.used_percent || 0) > 80 ? 'red' : 'blue'}`}>
                {hostStats?.cpu?.used_percent != null ? hostStats.cpu.used_percent.toFixed(0) + '%' : '-'}
              </div>
              <div className="stat-sub">{hostInfo?.cpu?.cores || '?'} cores · {hostInfo?.cpu?.model || ''}</div>
              <div className="stat-bar-wrap">
                <div className={`stat-bar ${(hostStats?.cpu?.used_percent || 0) > 80 ? 'red' : 'blue'}`}
                  style={{ width: (hostStats?.cpu?.used_percent || 0) + '%' }} />
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon purple">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="4" width="16" height="22" rx="2"/><line x1="9" y1="2" x2="9" y2="6"/><line x1="15" y1="2" x2="15" y2="6"/></svg>
              </div>
              <div className="label">Memory</div>
              <div className={`value ${(hostStats?.memory?.used_percent || 0) > 80 ? 'red' : 'purple'}`}>
                {hostStats?.memory?.used_percent != null ? hostStats.memory.used_percent.toFixed(0) + '%' : '-'}
              </div>
              <div className="stat-sub">
                {hostStats?.memory?.used_mb ? (hostStats.memory.used_mb / 1024).toFixed(1) + ' GB' : '-'}
                {' / '}
                {hostStats?.memory?.total_mb ? (hostStats.memory.total_mb / 1024).toFixed(1) + ' GB' : hostInfo?.memory?.total_gb ? hostInfo.memory.total_gb + ' GB' : '-'}
              </div>
              <div className="stat-bar-wrap">
                <div className={`stat-bar ${(hostStats?.memory?.used_percent || 0) > 80 ? 'red' : 'purple'}`}
                  style={{ width: (hostStats?.memory?.used_percent || 0) + '%' }} />
              </div>
            </div>
            {hostStats?.storage?.map((d, i) => {
              const pct = d.size_gb > 0 ? (d.used_gb / d.size_gb) * 100 : 0;
              const color = pct > 80 ? 'red' : 'cyan';
              return (
                <div className="stat-card" key={i}>
                  <div className={`stat-icon ${color}`}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="18" rx="2"/><line x1="2" y1="9" x2="22" y2="9"/><circle cx="6" cy="6" r="1"/></svg>
                  </div>
                  <div className="label">{d.mount === '/' ? 'System Disk' : 'Disk ' + d.mount}</div>
                  <div className={`value ${color}`}>{pct.toFixed(0) + '%'}</div>
                  <div className="stat-sub">{d.used_gb?.toFixed(1) || '-'} GB / {d.size_gb?.toFixed(0) || '-'} GB · {d.filesystem}</div>
                  <div className="stat-bar-wrap">
                    <div className={`stat-bar ${color}`} style={{ width: pct + '%' }} />
                  </div>
                </div>
              );
            })}
            <div className="stat-card">
              <div className="stat-icon green">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
              </div>
              <div className="label">Image Storage</div>
              <div className="value green">{storageInfo?.total_gb?.toFixed(1) || '-'} GB</div>
              <div className="stat-sub">{storageInfo?.used_gb?.toFixed(1) || '0'} GB used · {storageInfo?.free_gb?.toFixed(1) || '0'} GB free</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon blue">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 8h6"/><path d="M9 12h6"/><path d="M9 16h4"/></svg>
              </div>
              <div className="label">Virtual Machines</div>
              <div className="value blue">{vms.length}</div>
              <div className="stat-sub">
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
                {filtered.map(vm => {
                  const running = vm.state === 'running';
                  return (
                    <div key={vm.name} className="vm-card" onClick={() => navigate('detail', vm.name)}>
                      <div className="top">
                        <div className="name">{vm.name}</div>
                        <span className={`status-badge ${running ? 'running' : 'stopped'}`}>
                          <span className="dot" />{vm.state}
                        </span>
                      </div>
                      <div className="vm-meta">
                        <div className="vm-meta-item">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
                          IP: <span>{vm.ip_address || vm.guest_ip || '-'}</span>
                        </div>
                        <div className="vm-meta-item">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="4" width="16" height="16" rx="2"/><line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="13" x2="14" y2="13"/><line x1="8" y1="17" x2="12" y2="17"/></svg>
                          CPU: <span>{vm.cpu || '-'}</span>
                        </div>
                        <div className="vm-meta-item">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="4" width="16" height="22" rx="2"/><line x1="9" y1="2" x2="9" y2="6"/><line x1="15" y1="2" x2="15" y2="6"/></svg>
                          RAM: <span>{vm.memory_mb ? (vm.memory_mb / 1024).toFixed(1) + ' GB' : '-'}</span>
                        </div>
                        <div className="vm-meta-item">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                          Uptime: <span>{vm.uptime_seconds ? Math.floor(vm.uptime_seconds / 3600) + 'h' : '-'}</span>
                        </div>
                      </div>
                      <div className="vm-actions" onClick={e => e.stopPropagation()}>
                        {running ? (
                          <button className="btn btn-ghost" onClick={() => handleVMAction(vm.name, 'stop')}>■ Stop</button>
                        ) : (
                          <button className="btn btn-success" onClick={() => handleVMAction(vm.name, 'start')}>▶ Start</button>
                        )}
                        {running && (
                          <button className="btn btn-ghost"
                            onClick={() => window.open('/vm/vnc/console/' + encodeURIComponent(vm.name), '_blank')}>🖥 Console</button>
                        )}
                        <button className="btn btn-ghost"
                          onClick={() => { setCloneSource(vm.name); setCloneName(''); setShowClone(true); }}>Clone</button>
                        <button className="btn btn-danger"
                          onClick={() => handleVMAction(vm.name, 'delete')}>Delete</button>
                      </div>
                    </div>
                  );
                })}
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

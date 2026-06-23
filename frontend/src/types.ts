export interface User {
  id: number; username: string; email?: string; is_admin: boolean; created_at?: string;
}

export interface VM {
  name: string; state: string; ip_address?: string; guest_ip?: string;
  cpu?: number; memory_mb?: number; os_type?: string; uuid?: string;
  vnc_port?: number; autostart?: boolean; uptime_seconds?: number;
  max_memory_mb?: number; cpu_time_s?: number; disks?: Disk[];
  interfaces?: NetInterface[]; root_password?: string;
}

export interface Disk { type: string; device: string; source?: string; target?: string; readonly?: boolean; }

export interface NetInterface { type: string; mac?: string; source?: string; model?: string; }

export interface HostInfo { hostname?: string; uptime?: string; cpu?: { cores?: number; model?: string }; memory?: { total_gb?: number; total_mb?: number }; storage?: { filesystem?: string; size_gb?: number; used_gb?: number; avail_gb?: number }[]; }

export interface HostStats { cpu?: { used_percent?: number }; memory?: { used_percent?: number; used_mb?: number; total_mb?: number }; storage?: { mount?: string; used_percent?: number; size_gb?: number; used_gb?: number }[]; }

export interface StorageInfo { path?: string; total_gb?: number; used_gb?: number; free_gb?: number; }

export interface Network { name: string; active: boolean; bridge?: string; subnet?: string; autostart?: boolean; }

export interface Lease { network: string; ip: string; mac: string; hostname: string; prefix?: number; expirytime?: number; }

export interface Snapshot { name: string; created?: string; }

export interface Backup { dir: string; timestamp: string; xml?: string; disks?: string[]; }

export interface BackupSchedule { id: number; vm_name: string; cron_expression: string; retention: number; enabled: boolean; last_run?: string; created_at?: string; }

export interface AuditLog { id: number; user_id?: number; username: string; action: string; resource_type: string; resource_name?: string; details?: string; ip_address?: string; success: boolean; created_at: string; }

export interface Image { name: string; path?: string; format?: string; actual_size_bytes?: number; virtual_size_gb?: number; mtime?: number; ctime?: number; }

export interface RepoImage { name: string; description: string; url?: string; type?: string; is_iso?: boolean; }
export interface RepoFamilies { [family: string]: RepoImage[]; }

export interface Metrics { state?: string; max_memory_mb?: number; memory_mb?: number; cpu_count?: number; cpu_time_ns?: number; cpu_time_s?: number; memory_stats?: { available?: number; unused?: number }; block_stats?: { [dev: string]: { rd_req: number; rd_bytes: number; wr_req: number; wr_bytes: number } }; }

import React, { useState, useEffect, useCallback } from 'react';
import {
  Users, Radio, Video, MessageSquare, Activity, Send, StopCircle,
  Search, RefreshCw, Trash2, CheckCircle, AlertCircle, Cpu, HardDrive
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription
} from '../components/ui/dialog';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

const StatCard = ({ icon: Icon, label, value, tone = 'blue', testid, onClick }) => {
  const tones = {
    blue: 'from-blue-500/20 to-blue-600/10 border-blue-500/30 text-blue-300',
    red: 'from-red-500/20 to-red-600/10 border-red-500/30 text-red-300',
    emerald: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-300',
    amber: 'from-amber-500/20 to-amber-600/10 border-amber-500/30 text-amber-300',
    purple: 'from-purple-500/20 to-purple-600/10 border-purple-500/30 text-purple-300',
  };
  const clickable = typeof onClick === 'function';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!clickable}
      className={`text-left w-full bg-gradient-to-br ${tones[tone]} border rounded-2xl p-5 transition-all ${
        clickable ? 'hover:scale-[1.02] hover:brightness-110 cursor-pointer' : 'cursor-default'
      }`}
      data-testid={testid}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs uppercase tracking-wider text-gray-400 font-semibold">{label}</span>
        <Icon className="w-5 h-5 opacity-60" />
      </div>
      <p className="text-3xl font-bold text-white" data-testid={`${testid}-value`}>{value ?? '—'}</p>
      {clickable && <p className="text-[10px] text-gray-400 mt-2 uppercase tracking-wider">Click for details →</p>}
    </button>
  );
};

const formatBytes = (n) => {
  if (!n) return '0 MB';
  const mb = n / (1024 * 1024);
  return mb < 1024 ? `${mb.toFixed(0)} MB` : `${(mb / 1024).toFixed(2)} GB`;
};
const fmtDate = (iso) => iso ? new Date(iso).toLocaleString() : '—';
const fmtDateOnly = (iso) => iso ? new Date(iso).toLocaleDateString() : '—';

const AdminDashboard = () => {
  const { user } = useAuth();
  const [tab, setTab] = useState('overview');
  const [summary, setSummary] = useState(null);
  const [system, setSystem] = useState(null);
  const [liveUsers, setLiveUsers] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [users, setUsers] = useState([]);
  const [broadcasts, setBroadcasts] = useState([]);
  const [userQ, setUserQ] = useState('');
  const [historyOpen, setHistoryOpen] = useState(null);  // user_id
  const [historyData, setHistoryData] = useState(null);
  const [replyOpen, setReplyOpen] = useState(null);      // ticket_id
  const [replyText, setReplyText] = useState('');
  const [broadcast, setBroadcast] = useState({ title: '', body: '', audience: 'all', severity: 'info' });

  // Drill-down dialogs opened from Overview stat cards
  const [detail, setDetail] = useState(null);     // { title, kind: 'users' | 'videos', rows: [] }
  const [detailLoading, setDetailLoading] = useState(false);

  const isAdmin = user?.role === 'admin' || user?.plan === 'lifetime';

  const loadSummary = useCallback(async () => {
    try { const { data } = await api.get('/admin/summary'); setSummary(data); } catch {}
  }, []);
  const loadSystem = useCallback(async () => {
    try { const { data } = await api.get('/admin/system'); setSystem(data); } catch {}
  }, []);
  const loadLive = useCallback(async () => {
    try { const { data } = await api.get('/admin/live-users'); setLiveUsers(data.streams || []); } catch {}
  }, []);
  const loadTickets = useCallback(async () => {
    try { const { data } = await api.get('/admin/tickets'); setTickets(data.tickets || []); } catch {}
  }, []);
  const loadUsers = useCallback(async (q = '') => {
    try {
      const { data } = await api.get(`/admin/users${q ? `?q=${encodeURIComponent(q)}` : ''}`);
      setUsers(data.users || []);
    } catch {}
  }, []);
  const loadBroadcasts = useCallback(async () => {
    try { const { data } = await api.get('/admin/broadcasts'); setBroadcasts(data.broadcasts || []); } catch {}
  }, []);

  // Initial + polling loop for real-time counters
  useEffect(() => {
    if (!isAdmin) return;
    loadSummary(); loadSystem(); loadLive(); loadTickets(); loadUsers(''); loadBroadcasts();
    const t = setInterval(() => { loadSummary(); loadSystem(); loadLive(); }, 15000);
    return () => clearInterval(t);
  }, [isAdmin, loadSummary, loadSystem, loadLive, loadTickets, loadUsers, loadBroadcasts]);

  const stopStream = async (streamId, userEmail) => {
    if (!window.confirm(`Force-stop the live stream for ${userEmail}?`)) return;
    try {
      await api.post(`/admin/stream/${streamId}/stop`);
      toast.success('Stream stopped');
      await loadLive(); await loadSummary();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to stop stream');
    }
  };

  const openHistory = async (userId) => {
    setHistoryOpen(userId); setHistoryData(null);
    try {
      const { data } = await api.get(`/admin/users/${userId}/history`);
      setHistoryData(data);
    } catch {
      toast.error('Failed to load user history');
    }
  };

  const sendReply = async (ticketId, closeAfter) => {
    try {
      const body = {};
      if (replyText.trim()) body.reply = replyText.trim();
      if (closeAfter) body.status = 'closed';
      await api.post(`/admin/tickets/${ticketId}/reply`, body);
      toast.success('Ticket updated');
      setReplyOpen(null); setReplyText('');
      await loadTickets(); await loadSummary();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to reply');
    }
  };

  const sendBroadcast = async () => {
    if (!broadcast.title.trim() || !broadcast.body.trim()) {
      toast.error('Title and body required'); return;
    }
    try {
      await api.post('/admin/broadcast', broadcast);
      toast.success('Broadcast sent to users');
      setBroadcast({ title: '', body: '', audience: 'all', severity: 'info' });
      await loadBroadcasts();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to broadcast');
    }
  };

  const deleteBroadcast = async (id) => {
    if (!window.confirm('Delete this broadcast permanently?')) return;
    try { await api.delete(`/admin/broadcast/${id}`); await loadBroadcasts(); toast.success('Deleted'); }
    catch { toast.error('Failed to delete'); }
  };

  // --- Overview card drill-downs ------------------------------------------------
  const openUserDetail = async (title, filter) => {
    setDetail({ title, kind: 'users', rows: [] });
    setDetailLoading(true);
    try {
      const { data } = await api.get(`/admin/users/filtered?filter=${filter}`);
      setDetail({ title, kind: 'users', rows: data.users || [] });
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load list');
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const openVideosDetail = async () => {
    setDetail({ title: 'All Videos', kind: 'videos', rows: [] });
    setDetailLoading(true);
    try {
      const { data } = await api.get('/admin/videos?limit=500');
      setDetail({ title: 'All Videos', kind: 'videos', rows: data.videos || [] });
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load videos');
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const deleteVideoAsAdmin = async (v) => {
    const warn = v.is_live
      ? `⚠️ This video is CURRENTLY LIVE STREAMING for ${v.user_email}.\n\nDeleting it will force-stop the stream immediately AND remove the file from the server. This cannot be undone.\n\nProceed?`
      : `Delete "${v.title || v.filename}" (owner: ${v.user_email})?\n\nThe file will be removed from the server and this cannot be undone.`;
    if (!window.confirm(warn)) return;
    try {
      const { data } = await api.delete(`/admin/videos/${v.video_id}`);
      toast.success(`Deleted (${(data.bytes_freed / (1024 * 1024)).toFixed(0)} MB freed${data.streams_stopped ? `, ${data.streams_stopped} stream stopped` : ''})`);
      // Refresh the open dialog + summary in the background
      await openVideosDetail();
      await loadSummary();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to delete video');
    }
  };
  // ------------------------------------------------------------------------------

  if (!isAdmin) {
    return (
      <div className="p-8 text-center text-gray-400" data-testid="admin-forbidden">
        <AlertCircle className="w-12 h-12 mx-auto mb-3 text-red-400" />
        <h2 className="text-white text-xl font-bold mb-1">Admin access required</h2>
        <p>You don't have permission to view this page.</p>
      </div>
    );
  }

  const tabs = [
    { key: 'overview',   label: 'Overview',    icon: Activity },
    { key: 'live',       label: 'Live Users',  icon: Radio },
    { key: 'tickets',    label: 'Tickets',     icon: MessageSquare, badge: summary?.open_tickets },
    { key: 'users',      label: 'Users',       icon: Users },
    { key: 'broadcast',  label: 'Broadcast',   icon: Send },
  ];

  return (
    <div className="space-y-6" data-testid="admin-dashboard">
      <div>
        <h1 className="text-3xl font-bold text-white mb-1">Analytics</h1>
        <p className="text-gray-400">Live Adda admin dashboard · real-time overview & controls</p>
      </div>

      {/* Tab strip */}
      <div className="flex gap-2 flex-wrap border-b border-gray-800 pb-1">
        {tabs.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              data-testid={`admin-tab-${t.key}`}
              className={`px-4 py-2 rounded-t-lg text-sm font-semibold flex items-center gap-2 transition-colors ${
                active
                  ? 'bg-gray-800 text-white border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
              {typeof t.badge === 'number' && t.badge > 0 && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full bg-red-500 text-white text-[10px] font-bold">{t.badge}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* OVERVIEW */}
      {tab === 'overview' && (
        <div className="space-y-6" data-testid="admin-overview">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard testid="stat-live" icon={Radio} tone="red" label="Live Now" value={summary?.live_users}
              onClick={() => setTab('live')} />
            <StatCard testid="stat-total-users" icon={Users} tone="blue" label="Total Users" value={summary?.total_users}
              onClick={() => setTab('users')} />
            <StatCard testid="stat-paying" icon={CheckCircle} tone="emerald" label="Paying Users" value={summary?.active_paying_users}
              onClick={() => openUserDetail('Paying Users', 'paying')} />
            <StatCard testid="stat-tickets" icon={MessageSquare} tone="amber" label="Open Tickets" value={summary?.open_tickets}
              onClick={() => setTab('tickets')} />
            <StatCard testid="stat-signups-today" icon={Users} tone="purple" label="Sign-ups Today" value={summary?.signups_today}
              onClick={() => openUserDetail('Sign-ups Today', 'signups_today')} />
            <StatCard testid="stat-signups-week" icon={Users} tone="purple" label="Sign-ups (7d)" value={summary?.signups_this_week}
              onClick={() => openUserDetail('Sign-ups (7 days)', 'signups_7d')} />
            <StatCard testid="stat-live-streams" icon={Radio} tone="red" label="Active Streams" value={summary?.live_streams}
              onClick={() => setTab('live')} />
            <StatCard testid="stat-videos" icon={Video} tone="blue" label="Total Videos" value={summary?.total_videos}
              onClick={openVideosDetail} />
          </div>

          {/* System health */}
          {system && (
            <div className="bg-gray-800/50 border border-gray-700 rounded-2xl p-6" data-testid="admin-system-panel">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-bold flex items-center gap-2"><Cpu className="w-4 h-4" /> System</h3>
                <span className="text-gray-500 text-xs">Build: {system.build_sha}</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <p className="text-gray-400 text-xs mb-1">CPU</p>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-white">{system.cpu_percent}%</span>
                    <span className="text-gray-500 text-xs">load {system.load_avg['1min'].toFixed(2)}</span>
                  </div>
                  <div className="w-full bg-gray-700 h-2 rounded-full mt-2">
                    <div className={`h-2 rounded-full ${system.cpu_percent > 80 ? 'bg-red-500' : 'bg-blue-500'}`}
                      style={{ width: `${Math.min(100, system.cpu_percent)}%` }} />
                  </div>
                </div>
                <div>
                  <p className="text-gray-400 text-xs mb-1">RAM</p>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-white">{system.ram.percent}%</span>
                    <span className="text-gray-500 text-xs">{system.ram.used_mb}/{system.ram.total_mb} MB</span>
                  </div>
                  <div className="w-full bg-gray-700 h-2 rounded-full mt-2">
                    <div className={`h-2 rounded-full ${system.ram.percent > 85 ? 'bg-red-500' : 'bg-emerald-500'}`}
                      style={{ width: `${system.ram.percent}%` }} />
                  </div>
                </div>
                <div>
                  <p className="text-gray-400 text-xs mb-1">Disk</p>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-white">{system.disk.percent}%</span>
                    <span className="text-gray-500 text-xs">{system.disk.used_gb}/{system.disk.total_gb} GB</span>
                  </div>
                  <div className="w-full bg-gray-700 h-2 rounded-full mt-2">
                    <div className={`h-2 rounded-full ${system.disk.percent > 85 ? 'bg-red-500' : 'bg-purple-500'}`}
                      style={{ width: `${system.disk.percent}%` }} />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* LIVE USERS */}
      {tab === 'live' && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-2xl overflow-hidden" data-testid="admin-live-panel">
          <div className="p-4 border-b border-gray-700 flex justify-between items-center">
            <h3 className="text-white font-bold">Active live streams ({liveUsers.length})</h3>
            <Button size="sm" variant="ghost" onClick={loadLive}><RefreshCw className="w-4 h-4"/></Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 text-xs uppercase tracking-wider bg-gray-900/50">
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Mobile</th>
                  <th className="px-4 py-3">Plan</th>
                  <th className="px-4 py-3">Started</th>
                  <th className="px-4 py-3">Expires</th>
                  <th className="px-4 py-3">Video</th>
                  <th className="px-4 py-3">Size</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {liveUsers.length === 0 && (
                  <tr><td colSpan="8" className="text-center text-gray-500 py-8">No one is live right now.</td></tr>
                )}
                {liveUsers.map((s) => (
                  <tr key={s.stream_id} data-testid={`admin-live-row-${s.stream_id}`} className="border-t border-gray-800 hover:bg-gray-900/40">
                    <td className="px-4 py-3">
                      <div className="text-white font-medium">{s.user_email}</div>
                      <div className="text-gray-500 text-xs">{s.user_name}</div>
                    </td>
                    <td className="px-4 py-3 text-gray-300">{s.user_mobile || '—'}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-xs font-semibold">{s.plan || '—'}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{fmtDate(s.plan_started_at)}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{fmtDate(s.plan_expires_at)}</td>
                    <td className="px-4 py-3 text-gray-300 max-w-[200px] truncate">
                      {s.current_video}
                      {s.video_resolution && <span className="ml-2 text-blue-400 text-xs">{s.video_resolution}</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-400">{formatBytes(s.video_size)}</td>
                    <td className="px-4 py-3 text-right">
                      <Button size="sm" variant="destructive" onClick={() => stopStream(s.stream_id, s.user_email)}
                        data-testid={`admin-stop-${s.stream_id}`}>
                        <StopCircle className="w-4 h-4 mr-1" /> Stop
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TICKETS */}
      {tab === 'tickets' && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-2xl overflow-hidden" data-testid="admin-tickets-panel">
          <div className="p-4 border-b border-gray-700 flex justify-between items-center">
            <h3 className="text-white font-bold">Support tickets ({tickets.length})</h3>
            <Button size="sm" variant="ghost" onClick={loadTickets}><RefreshCw className="w-4 h-4"/></Button>
          </div>
          <div className="divide-y divide-gray-800">
            {tickets.length === 0 && <div className="text-center text-gray-500 py-8">No tickets yet.</div>}
            {tickets.map((t) => {
              const isOpen = !t.status || t.status === 'open';
              return (
                <div key={t.ticket_id} className="p-4" data-testid={`admin-ticket-${t.ticket_id}`}>
                  <div className="flex items-start justify-between gap-4 mb-2 flex-wrap">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${isOpen ? 'bg-amber-500/20 text-amber-300' : 'bg-gray-700 text-gray-400'}`}>{isOpen ? 'OPEN' : 'CLOSED'}</span>
                        <span className="text-white font-semibold">{t.subject}</span>
                      </div>
                      <div className="text-gray-500 text-xs">
                        {t.user_email} · {t.user_mobile || 'no mobile'} · plan: {t.user_plan || '—'} · {fmtDate(t.created_at)}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => { setReplyOpen(t.ticket_id); setReplyText(''); }}
                        data-testid={`admin-reply-${t.ticket_id}`}>Reply</Button>
                    </div>
                  </div>
                  <p className="text-gray-300 text-sm bg-gray-900/50 rounded p-3 mt-2 whitespace-pre-wrap">{t.message}</p>
                  {t.replies && t.replies.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {t.replies.map((r, i) => (
                        <div key={i} className="bg-blue-500/10 border-l-2 border-blue-500 rounded p-2 text-xs">
                          <div className="text-blue-300 font-semibold">{r.author}</div>
                          <div className="text-gray-300 whitespace-pre-wrap">{r.message}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* USERS */}
      {tab === 'users' && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-2xl overflow-hidden" data-testid="admin-users-panel">
          <div className="p-4 border-b border-gray-700 flex gap-2">
            <div className="flex-1 flex items-center bg-gray-900 border border-gray-700 rounded-lg px-3">
              <Search className="w-4 h-4 text-gray-500 mr-2" />
              <input
                value={userQ}
                onChange={(e) => setUserQ(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && loadUsers(userQ)}
                placeholder="Search email…"
                className="bg-transparent outline-none text-white text-sm py-2 w-full"
                data-testid="admin-users-search"
              />
            </div>
            <Button size="sm" onClick={() => loadUsers(userQ)}>Search</Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 text-xs uppercase tracking-wider bg-gray-900/50">
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Mobile</th>
                  <th className="px-4 py-3">Plan</th>
                  <th className="px-4 py-3">Slots</th>
                  <th className="px-4 py-3">Joined</th>
                  <th className="px-4 py-3 text-right">History</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.user_id} className="border-t border-gray-800 hover:bg-gray-900/40">
                    <td className="px-4 py-3 text-white">{u.email}</td>
                    <td className="px-4 py-3 text-gray-300">{u.name || '—'}</td>
                    <td className="px-4 py-3 text-gray-300">{u.mobile_number || '—'}</td>
                    <td className="px-4 py-3 text-gray-300">{u.plan || '—'}</td>
                    <td className="px-4 py-3 text-gray-300">{u.stream_slots}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{fmtDateOnly(u.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Button size="sm" variant="secondary" onClick={() => openHistory(u.user_id)}
                        data-testid={`admin-history-${u.user_id}`}>View</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* BROADCAST */}
      {tab === 'broadcast' && (
        <div className="space-y-6" data-testid="admin-broadcast-panel">
          <div className="bg-gray-800/50 border border-gray-700 rounded-2xl p-6">
            <h3 className="text-white font-bold mb-4">Send broadcast to users</h3>
            <div className="space-y-3">
              <Input placeholder="Title" value={broadcast.title}
                onChange={(e) => setBroadcast({ ...broadcast, title: e.target.value })}
                className="bg-gray-900 border-gray-700 text-white"
                data-testid="broadcast-title" />
              <Textarea placeholder="Message body…" value={broadcast.body}
                onChange={(e) => setBroadcast({ ...broadcast, body: e.target.value })}
                className="bg-gray-900 border-gray-700 text-white min-h-[120px]"
                data-testid="broadcast-body" />
              <div className="grid grid-cols-2 gap-3">
                <select value={broadcast.audience}
                  onChange={(e) => setBroadcast({ ...broadcast, audience: e.target.value })}
                  className="bg-gray-900 border border-gray-700 text-white rounded-md p-2"
                  data-testid="broadcast-audience">
                  <option value="all">All registered users</option>
                  <option value="active_plan">Users with active plan</option>
                  <option value="live_only">Users currently live</option>
                </select>
                <select value={broadcast.severity}
                  onChange={(e) => setBroadcast({ ...broadcast, severity: e.target.value })}
                  className="bg-gray-900 border border-gray-700 text-white rounded-md p-2"
                  data-testid="broadcast-severity">
                  <option value="info">Info</option>
                  <option value="success">Success</option>
                  <option value="warning">Warning</option>
                </select>
              </div>
              <Button onClick={sendBroadcast} data-testid="broadcast-send"><Send className="w-4 h-4 mr-2" /> Send broadcast</Button>
            </div>
          </div>

          <div className="bg-gray-800/50 border border-gray-700 rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-gray-700 text-white font-bold">Past broadcasts ({broadcasts.length})</div>
            <div className="divide-y divide-gray-800">
              {broadcasts.length === 0 && <div className="text-center text-gray-500 py-8">No broadcasts yet.</div>}
              {broadcasts.map((b) => (
                <div key={b.notification_id} className="p-4 flex justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                        b.severity === 'warning' ? 'bg-amber-500/20 text-amber-300' :
                        b.severity === 'success' ? 'bg-emerald-500/20 text-emerald-300' :
                        'bg-blue-500/20 text-blue-300'
                      }`}>{b.severity}</span>
                      <span className="text-white font-semibold">{b.title}</span>
                      <span className="text-gray-500 text-xs">→ {b.audience}</span>
                    </div>
                    <p className="text-gray-400 text-sm whitespace-pre-wrap">{b.body}</p>
                    <p className="text-gray-600 text-xs mt-1">{fmtDate(b.created_at)}</p>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => deleteBroadcast(b.notification_id)}
                    data-testid={`broadcast-delete-${b.notification_id}`}>
                    <Trash2 className="w-4 h-4 text-red-400" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* User history dialog */}
      <Dialog open={!!historyOpen} onOpenChange={() => setHistoryOpen(null)}>
        <DialogContent className="max-w-2xl bg-gray-900 border-gray-700 text-white">
          <DialogHeader>
            <DialogTitle>User history</DialogTitle>
            <DialogDescription className="text-gray-400">
              {historyData?.user?.email || '…'}
            </DialogDescription>
          </DialogHeader>
          {!historyData ? (
            <div className="text-gray-400 py-6 text-center">Loading…</div>
          ) : (
            <div className="space-y-4 max-h-[60vh] overflow-y-auto text-sm">
              <div className="bg-gray-800 rounded-lg p-3">
                <p><b>Plan:</b> {historyData.user.plan || '—'} · <b>Slots:</b> {historyData.user.stream_slots}</p>
                <p><b>Mobile:</b> {historyData.user.mobile_number || '—'} · <b>Storage:</b> {formatBytes(historyData.user.storage_used)}</p>
                {historyData.user.active_plans?.length > 0 && (
                  <div className="mt-2 space-y-1">
                    <p className="text-gray-400 text-xs uppercase">Active plans</p>
                    {historyData.user.active_plans.map((p, i) => (
                      <p key={i} className="text-xs">{p.plan_id} → expires {fmtDate(p.expires_at)}</p>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <p className="text-gray-400 text-xs uppercase mb-2">Transactions ({historyData.transactions.length})</p>
                {historyData.transactions.slice(0, 10).map((t, i) => (
                  <div key={i} className="text-xs text-gray-300 py-1 border-b border-gray-800">
                    ₹{t.amount} · {t.plan_id} · {t.status} · {fmtDate(t.created_at)}
                  </div>
                ))}
                {historyData.transactions.length === 0 && <div className="text-gray-500 text-xs">No transactions.</div>}
              </div>
              <div>
                <p className="text-gray-400 text-xs uppercase mb-2">Streams ({historyData.streams.length})</p>
                {historyData.streams.slice(0, 10).map((s, i) => (
                  <div key={i} className="text-xs text-gray-300 py-1 border-b border-gray-800">
                    {s.current_video} · {s.is_live ? 'LIVE' : 'stopped'} · {fmtDate(s.started_at)}
                  </div>
                ))}
                {historyData.streams.length === 0 && <div className="text-gray-500 text-xs">No streams.</div>}
              </div>
              <div>
                <p className="text-gray-400 text-xs uppercase mb-2">Videos ({historyData.videos.length})</p>
                {historyData.videos.slice(0, 10).map((v, i) => (
                  <div key={i} className="text-xs text-gray-300 py-1 border-b border-gray-800">
                    {v.title} · {formatBytes(v.size)} · {v.height ? `${v.height}p` : ''}
                  </div>
                ))}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Ticket reply dialog */}
      <Dialog open={!!replyOpen} onOpenChange={() => setReplyOpen(null)}>
        <DialogContent className="max-w-lg bg-gray-900 border-gray-700 text-white">
          <DialogHeader>
            <DialogTitle>Reply to ticket</DialogTitle>
          </DialogHeader>
          <Textarea value={replyText} onChange={(e) => setReplyText(e.target.value)}
            placeholder="Your reply (will be stored on the ticket)…"
            className="bg-gray-800 border-gray-700 text-white min-h-[140px]"
            data-testid="ticket-reply-input" />
          <DialogFooter className="flex gap-2 mt-2">
            <Button variant="ghost" onClick={() => setReplyOpen(null)}>Cancel</Button>
            <Button onClick={() => sendReply(replyOpen, false)} data-testid="ticket-reply-send">Send reply</Button>
            <Button variant="destructive" onClick={() => sendReply(replyOpen, true)} data-testid="ticket-close">Send & Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Card drill-down dialog (Paying Users, Sign-ups, All Videos) */}
      <Dialog open={!!detail} onOpenChange={() => setDetail(null)}>
        <DialogContent className="max-w-5xl bg-gray-900 border-gray-700 text-white" data-testid="drilldown-dialog">
          <DialogHeader>
            <DialogTitle data-testid="drilldown-title">{detail?.title}</DialogTitle>
            <DialogDescription className="text-gray-400">
              {detailLoading ? 'Loading…' : `${detail?.rows?.length ?? 0} record${(detail?.rows?.length ?? 0) === 1 ? '' : 's'}`}
            </DialogDescription>
          </DialogHeader>

          {detail?.kind === 'users' && (
            <div className="overflow-x-auto max-h-[60vh]">
              <table className="w-full text-sm">
                <thead className="text-gray-400 text-xs uppercase border-b border-gray-800 sticky top-0 bg-gray-900">
                  <tr>
                    <th className="text-left py-2 px-2">Email</th>
                    <th className="text-left py-2 px-2">Mobile</th>
                    <th className="text-left py-2 px-2">Plan</th>
                    <th className="text-left py-2 px-2">Signed up</th>
                    <th className="text-left py-2 px-2">Expires</th>
                  </tr>
                </thead>
                <tbody data-testid="drilldown-users-body">
                  {detail.rows.map((u) => (
                    <tr key={u.user_id} className="border-b border-gray-800 hover:bg-gray-800/40">
                      <td className="py-2 px-2 text-white">{u.email}</td>
                      <td className="py-2 px-2 text-gray-300">{u.mobile_number || '—'}</td>
                      <td className="py-2 px-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                          u.plan === 'lifetime' ? 'bg-purple-500/20 text-purple-300'
                          : u.plan ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-gray-700 text-gray-400'
                        }`}>{u.plan || 'free'}</span>
                      </td>
                      <td className="py-2 px-2 text-gray-300">{fmtDate(u.created_at)}</td>
                      <td className="py-2 px-2 text-gray-300">{u.plan === 'lifetime' ? '∞' : fmtDate(u.plan_expires_at)}</td>
                    </tr>
                  ))}
                  {detail.rows.length === 0 && !detailLoading && (
                    <tr><td colSpan={5} className="py-6 text-center text-gray-500">No matching users.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {detail?.kind === 'videos' && (
            <div className="overflow-x-auto max-h-[60vh]">
              <table className="w-full text-sm">
                <thead className="text-gray-400 text-xs uppercase border-b border-gray-800 sticky top-0 bg-gray-900">
                  <tr>
                    <th className="text-left py-2 px-2">Title</th>
                    <th className="text-left py-2 px-2">Owner</th>
                    <th className="text-left py-2 px-2">Size</th>
                    <th className="text-left py-2 px-2">Res</th>
                    <th className="text-left py-2 px-2">Uploaded</th>
                    <th className="text-left py-2 px-2">Status</th>
                    <th className="text-right py-2 px-2">Action</th>
                  </tr>
                </thead>
                <tbody data-testid="drilldown-videos-body">
                  {detail.rows.map((v) => (
                    <tr key={v.video_id} className="border-b border-gray-800 hover:bg-gray-800/40">
                      <td className="py-2 px-2 text-white max-w-[220px] truncate" title={v.title}>{v.title || v.filename || '(untitled)'}</td>
                      <td className="py-2 px-2 text-gray-300 max-w-[180px] truncate" title={v.user_email}>{v.user_email || '—'}</td>
                      <td className="py-2 px-2 text-gray-300">{formatBytes(v.size)}</td>
                      <td className="py-2 px-2 text-gray-300">{v.height ? `${v.height}p` : '—'}</td>
                      <td className="py-2 px-2 text-gray-300">{fmtDateOnly(v.uploaded_at)}</td>
                      <td className="py-2 px-2">
                        {v.is_live ? (
                          <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 text-xs font-semibold">● LIVE</span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-gray-700 text-gray-400 text-xs">idle</span>
                        )}
                      </td>
                      <td className="py-2 px-2 text-right">
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => deleteVideoAsAdmin(v)}
                          data-testid={`admin-delete-video-${v.video_id}`}
                          className="h-7 px-2"
                        >
                          <Trash2 className="w-3.5 h-3.5 mr-1" /> Delete
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {detail.rows.length === 0 && !detailLoading && (
                    <tr><td colSpan={7} className="py-6 text-center text-gray-500">No videos on the server.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AdminDashboard;

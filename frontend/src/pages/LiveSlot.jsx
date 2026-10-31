import React, { useState, useEffect, useCallback } from 'react';
import { Plus, AlertTriangle, Radio, HelpCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { slotsAPI, youtubeAPI, videoAPI } from '../services/api';
import { SlotCard } from '../components/SlotCard';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

const FILTERS = [
  { id: 'all', label: 'All slots' },
  { id: 'live', label: 'Live' },
  { id: 'ready', label: 'Ready' },
  { id: 'expired', label: 'Expired' },
];

const LiveSlot = () => {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const [slots, setSlots] = useState([]);
  const [summary, setSummary] = useState({ total: 0, live: 0, ready: 0, expired: 0 });
  const [videos, setVideos] = useState([]);
  const [filter, setFilter] = useState('all');
  const [busySlot, setBusySlot] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    const [{ data: s }, { data: v }] = await Promise.all([slotsAPI.list(), videoAPI.getAll()]);
    if (s) { setSlots(s.slots); setSummary(s.summary); }
    if (v) setVideos(v.filter((x) => x.processing_status !== 'transcoding'));
    setLoaded(true);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const handleRename = async (slotId, name) => {
    if (!name) { toast.error('Name cannot be empty'); return false; }
    const { data, error } = await slotsAPI.rename(slotId, name);
    if (!data) { toast.error(error || 'Rename failed'); return false; }
    setSlots((prev) => prev.map((s) => (s.slot_id === slotId ? { ...s, name: data.name } : s)));
    toast.success('Slot renamed');
    return true;
  };

  const handleGoLive = async (slot, videoId, key) => {
    setBusySlot(slot.slot_id);
    const { data, error } = await youtubeAPI.startWithKey(videoId, key, true, slot.slot_id);
    setBusySlot(null);
    if (!data) { toast.error(error || 'Failed to start stream'); return false; }
    toast.success(data.message || `'${slot.name}' is now live!`);
    await load();
    return true;
  };

  const handleStop = async (slot) => {
    if (!window.confirm(`Stop "${slot.name}"? The video being streamed will be PERMANENTLY DELETED from storage.`)) return;
    setBusySlot(slot.slot_id);
    const { data, error } = await youtubeAPI.stopStream(slot.stream?.stream_id);
    setBusySlot(null);
    if (!data) { toast.error(error || 'Failed to stop stream'); return; }
    toast.success(`"${slot.name}" stopped`);
    await load();
    refreshUser?.();
  };

  const handleRenew = (slot) => navigate(`/dashboard/billings?renew=${slot.slot_id}`);

  const visible = filter === 'all' ? slots : slots.filter((s) => s.status === filter);

  return (
    <div className="space-y-6" data-testid="live-slot-page">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white mb-1">My Slots</h1>
          <p className="text-gray-400">Each slot = one 24/7 live stream. Give it a name, pick a video, paste a YouTube key, go live.</p>
        </div>
        <Button onClick={() => navigate('/dashboard/billings')} className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white font-semibold" data-testid="add-slot-btn">
          <Plus className="w-4 h-4 mr-1.5" /> Add Slot
        </Button>
      </div>

      {/* Summary + filter */}
      {summary.total > 0 && (
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex gap-2 flex-wrap" data-testid="slot-summary">
            <span className="px-3 py-1.5 rounded-full bg-gray-800 border border-gray-700 text-gray-300 text-sm">{summary.total} slot{summary.total !== 1 ? 's' : ''}</span>
            <span className="px-3 py-1.5 rounded-full bg-red-500/10 border border-red-500/30 text-red-300 text-sm flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />{summary.live} live</span>
            <span className="px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm">{summary.ready} ready</span>
            {summary.expired > 0 && <span className="px-3 py-1.5 rounded-full bg-gray-700/40 border border-gray-600 text-gray-400 text-sm">{summary.expired} expired</span>}
          </div>
          <select value={filter} onChange={(e) => setFilter(e.target.value)} className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm" data-testid="slot-filter">
            {FILTERS.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
          </select>
        </div>
      )}

      {/* Empty state */}
      {loaded && summary.total === 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-8 text-center" data-testid="live-slot-no-plan-warning">
          <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto mb-3" />
          <h3 className="text-white text-xl font-bold mb-1">You don't have any slots yet</h3>
          <p className="text-gray-400 mb-5">Buy your first slot to start streaming 24/7 on YouTube.</p>
          <Button onClick={() => navigate('/dashboard/billings')} className="bg-gradient-to-r from-emerald-500 to-emerald-600 text-white" data-testid="empty-add-slot-btn">
            <Plus className="w-4 h-4 mr-1.5" /> Buy a Slot
          </Button>
        </div>
      )}

      {/* Slot grid */}
      {visible.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="slot-grid">
          {visible.map((slot) => (
            <SlotCard key={slot.slot_id} slot={slot} videos={videos} busy={busySlot === slot.slot_id}
              onRename={handleRename} onGoLive={handleGoLive} onStop={handleStop} onRenew={handleRenew} />
          ))}
        </div>
      )}
      {loaded && summary.total > 0 && visible.length === 0 && (
        <p className="text-gray-500 text-sm text-center py-8" data-testid="slot-filter-empty">No {filter} slots right now.</p>
      )}

      {/* How it works */}
      {summary.total > 0 && (
        <div className="bg-gray-800/40 rounded-2xl p-5 border border-gray-700/60 text-sm text-gray-400" data-testid="slot-help">
          <p className="text-white font-semibold mb-2 flex items-center gap-2"><HelpCircle className="w-4 h-4 text-blue-400" /> How slots work</p>
          <ul className="space-y-1 list-disc list-inside">
            <li>Every slot streams one video on loop, 24/7, to one YouTube stream key. Use a different key for each slot.</li>
            <li>Click a slot's name to rename it (e.g. “Bhajan Channel”, “Lo-fi Beats”).</li>
            <li><b className="text-gray-300">Renew</b> extends that exact slot — the name stays. <b className="text-gray-300">Add Slot</b> buys a brand-new one.</li>
            <li>Expired slots stay here for 30 days so you can renew them. Their stream stops and the video is removed on expiry.</li>
          </ul>
        </div>
      )}
      {!loaded && <div className="flex items-center justify-center py-16 text-gray-500"><Radio className="w-5 h-5 mr-2 animate-pulse" /> Loading your slots…</div>}
    </div>
  );
};

export default LiveSlot;

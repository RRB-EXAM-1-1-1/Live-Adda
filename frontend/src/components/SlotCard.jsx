import React, { useState } from 'react';
import { Pencil, Check, X, PlayCircle, StopCircle, RefreshCw, Clock, Film, Radio } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';

const STATUS = {
  live: { label: 'LIVE', pill: 'bg-red-500/15 text-red-300 border-red-500/40', dot: 'bg-red-500 animate-pulse', ring: 'border-red-500/40' },
  ready: { label: 'Ready to go live', pill: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40', dot: 'bg-emerald-400', ring: 'border-gray-700 hover:border-emerald-500/40' },
  expired: { label: 'Expired', pill: 'bg-gray-600/30 text-gray-400 border-gray-600', dot: 'bg-gray-500', ring: 'border-gray-800 opacity-80' },
};

const timeLeft = (slot) => {
  if (slot.plan_id === 'lifetime') return 'Never expires';
  if (slot.status === 'expired') return `Expired ${new Date(slot.expires_at).toLocaleDateString()}`;
  const h = slot.hours_left;
  if (h >= 48) return `${Math.floor(h / 24)} days left`;
  if (h >= 1) return `${Math.floor(h)}h ${Math.round((h % 1) * 60)}m left`;
  return `${Math.max(1, Math.round(h * 60))} min left`;
};

export const SlotCard = ({ slot, videos, onRename, onGoLive, onStop, onRenew, busy }) => {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(slot.name);
  const [videoId, setVideoId] = useState(videos[0]?.video_id || '');
  const [streamKey, setStreamKey] = useState('');
  const st = STATUS[slot.status];

  const saveName = async () => {
    const ok = await onRename(slot.slot_id, name.trim());
    if (ok) setEditing(false); else setName(slot.name);
  };

  return (
    <div className={`bg-gray-800/60 backdrop-blur rounded-2xl border ${st.ring} p-5 transition-colors`} data-testid={`slot-card-${slot.slot_id}`}>
      {/* Header: number, name, status */}
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-gray-900 border border-gray-700 flex items-center justify-center text-gray-300 font-bold shrink-0" data-testid={`slot-number-${slot.slot_id}`}>
          {slot.number}
        </div>
        <div className="min-w-0 flex-1">
          {editing ? (
            <div className="flex items-center gap-2">
              <Input value={name} maxLength={40} autoFocus onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') saveName(); if (e.key === 'Escape') { setEditing(false); setName(slot.name); } }}
                className="h-8 bg-gray-900 border-gray-600 text-white" data-testid={`slot-name-input-${slot.slot_id}`} />
              <Button size="icon" className="h-8 w-8 bg-emerald-600 hover:bg-emerald-700" onClick={saveName} data-testid={`slot-name-save-${slot.slot_id}`}><Check className="w-4 h-4" /></Button>
              <Button size="icon" variant="ghost" className="h-8 w-8 text-gray-400" onClick={() => { setEditing(false); setName(slot.name); }}><X className="w-4 h-4" /></Button>
            </div>
          ) : (
            <button onClick={() => setEditing(true)} className="group flex items-center gap-2 text-left max-w-full" data-testid={`slot-name-${slot.slot_id}`} title="Click to rename">
              <h3 className="text-white font-bold text-lg truncate">{slot.name}</h3>
              <Pencil className="w-3.5 h-3.5 text-gray-500 group-hover:text-white shrink-0" />
            </button>
          )}
          <p className="text-gray-400 text-xs mt-0.5 flex items-center gap-1.5 flex-wrap">
            <span className="px-1.5 py-0.5 rounded bg-gray-900 border border-gray-700 text-gray-300">{slot.plan_name}</span>
            <Clock className="w-3 h-3" />
            <span className={slot.expiring_soon ? 'text-amber-400 font-medium' : ''} data-testid={`slot-expiry-${slot.slot_id}`}>{timeLeft(slot)}</span>
          </p>
        </div>
        <span className={`shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-semibold ${st.pill}`} data-testid={`slot-status-${slot.slot_id}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />{st.label}
        </span>
      </div>

      {/* Body */}
      <div className="mt-4">
        {slot.status === 'live' && (
          <div className="bg-gray-900/70 rounded-xl p-4 border border-gray-700" data-testid={`slot-live-info-${slot.slot_id}`}>
            <p className="text-[11px] uppercase tracking-wider text-gray-500 mb-1 flex items-center gap-1"><Film className="w-3 h-3" /> Now streaming</p>
            <p className="text-white font-semibold truncate" data-testid={`slot-video-title-${slot.slot_id}`}>{slot.stream?.video_title || 'Live stream'}</p>
            <p className="text-gray-500 text-xs mt-1">Started {slot.stream?.started_at ? new Date(slot.stream.started_at).toLocaleString() : '—'}</p>
          </div>
        )}

        {slot.status === 'ready' && (
          <div className="space-y-3" data-testid={`slot-golive-form-${slot.slot_id}`}>
            <div>
              <Label className="text-gray-300 text-xs">1. Choose the video for this slot</Label>
              <select value={videoId} onChange={(e) => setVideoId(e.target.value)}
                className="mt-1 w-full bg-gray-900 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm"
                data-testid={`slot-video-select-${slot.slot_id}`}>
                {videos.length === 0 && <option value="">No videos yet — upload one in Video Manager</option>}
                {videos.map((v) => <option key={v.video_id} value={v.video_id}>{v.title}</option>)}
              </select>
            </div>
            <div>
              <Label className="text-gray-300 text-xs">2. Paste this slot's YouTube stream key</Label>
              <Input type="password" placeholder="xxxx-xxxx-xxxx-xxxx-xxxx" value={streamKey} onChange={(e) => setStreamKey(e.target.value)}
                className="mt-1 bg-gray-900 border-gray-600 text-white placeholder:text-gray-600 text-sm" data-testid={`slot-key-input-${slot.slot_id}`} />
            </div>
          </div>
        )}

        {slot.status === 'expired' && (
          <p className="text-gray-400 text-sm bg-gray-900/50 rounded-xl p-3 border border-gray-800">
            This slot has ended and its stream was stopped. Renew it to keep the name <b className="text-gray-200">“{slot.name}”</b> and start again.
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="mt-4 flex gap-2 flex-wrap">
        {slot.status === 'ready' && (
          <Button className="flex-1 bg-red-600 hover:bg-red-700 text-white font-semibold" disabled={busy || !videoId || !streamKey.trim()}
            onClick={() => onGoLive(slot, videoId, streamKey.trim()).then((ok) => ok && setStreamKey(''))}
            data-testid={`slot-golive-${slot.slot_id}`}>
            <PlayCircle className="w-4 h-4 mr-1.5" />{busy ? 'Starting…' : '3. Go Live'}
          </Button>
        )}
        {slot.status === 'live' && (
          <Button variant="outline" className="flex-1 border-red-500/50 text-red-300 hover:bg-red-500/10" disabled={busy}
            onClick={() => onStop(slot)} data-testid={`slot-stop-${slot.slot_id}`}>
            <StopCircle className="w-4 h-4 mr-1.5" />Stop stream
          </Button>
        )}
        {slot.plan_id !== 'lifetime' && (
          <Button variant={slot.status === 'expired' ? 'default' : 'outline'}
            className={slot.status === 'expired' ? 'flex-1 bg-amber-500 hover:bg-amber-600 text-black font-semibold' : 'border-gray-600 text-gray-300 hover:bg-gray-700'}
            onClick={() => onRenew(slot)} data-testid={`slot-renew-${slot.slot_id}`}>
            <RefreshCw className="w-4 h-4 mr-1.5" />Renew
          </Button>
        )}
      </div>
      {slot.status === 'live' && <p className="text-gray-500 text-[11px] mt-2 flex items-center gap-1"><Radio className="w-3 h-3" /> Stopping deletes the streamed video from storage.</p>}
    </div>
  );
};

import React, { useEffect, useState } from 'react';
import { X, Info, AlertTriangle, CheckCircle2 } from 'lucide-react';
import api from '../services/api';

const DISMISSED_KEY = 'liveadda:dismissed_notifications';

const readDismissed = () => {
  try { return new Set(JSON.parse(localStorage.getItem(DISMISSED_KEY) || '[]')); }
  catch { return new Set(); }
};
const writeDismissed = (set) => {
  try { localStorage.setItem(DISMISSED_KEY, JSON.stringify([...set])); } catch {}
};

/**
 * Renders active admin broadcasts at the top of every dashboard page.
 * Each notification is dismissible; dismissals persist in localStorage
 * so a user doesn't see the same banner on every page load.
 */
const NotificationBanner = () => {
  const [notes, setNotes] = useState([]);
  const [dismissed, setDismissed] = useState(readDismissed);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get('/notifications');
        if (!cancelled) setNotes(data?.notifications || []);
      } catch { /* silent */ }
    })();
    return () => { cancelled = true; };
  }, []);

  const dismiss = (id) => {
    const next = new Set(dismissed); next.add(id);
    setDismissed(next); writeDismissed(next);
  };

  const visible = notes.filter((n) => !dismissed.has(n.notification_id));
  if (visible.length === 0) return null;

  const tone = {
    info:    { cls: 'bg-blue-500/10 border-blue-500/30 text-blue-200', Icon: Info },
    warning: { cls: 'bg-amber-500/10 border-amber-500/30 text-amber-200', Icon: AlertTriangle },
    success: { cls: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200', Icon: CheckCircle2 },
  };

  return (
    <div className="space-y-2 mb-4" data-testid="notification-banner">
      {visible.map((n) => {
        const t = tone[n.severity] || tone.info;
        const { Icon } = t;
        return (
          <div key={n.notification_id} className={`flex items-start gap-3 rounded-xl border p-3 ${t.cls}`}
            data-testid={`notification-${n.notification_id}`}>
            <Icon className="w-5 h-5 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-white font-semibold text-sm">{n.title}</p>
              <p className="text-xs opacity-90 whitespace-pre-wrap">{n.body}</p>
            </div>
            <button onClick={() => dismiss(n.notification_id)}
              className="text-white/60 hover:text-white flex-shrink-0"
              data-testid={`notification-dismiss-${n.notification_id}`}>
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};

export default NotificationBanner;

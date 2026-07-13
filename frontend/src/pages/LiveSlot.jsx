import React, { useState, useEffect } from 'react';
import { Radio, Settings as SettingsIcon, PlayCircle, StopCircle, AlertTriangle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '../components/ui/dialog';
import { liveSlotAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

const LiveSlot = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [streamStatus, setStreamStatus] = useState(null);
  const [isLive, setIsLive] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);
  const [loopVideos, setLoopVideos] = useState(true);
  const [loading, setLoading] = useState(false);
  const [showPlanDialog, setShowPlanDialog] = useState(false);

  const hasActivePlan = user?.plan && user?.plan_expires_at;

  useEffect(() => {
    if (hasActivePlan) {
      loadStreamStatus();
    }
  }, []);

  const loadStreamStatus = async () => {
    const { data, error } = await liveSlotAPI.getStatus();
    if (data) {
      setStreamStatus(data);
      setIsLive(data.is_live || false);
      if (data.settings) {
        setAutoRotate(data.settings.auto_rotate ?? true);
        setLoopVideos(data.settings.loop_videos ?? true);
      }
    }
  };

  const handleToggleLive = async () => {
    if (!hasActivePlan) {
      setShowPlanDialog(true);
      return;
    }

    setLoading(true);
    if (!isLive) {
      const { data, error } = await liveSlotAPI.start();
      if (data) {
        setIsLive(true);
        toast.success('🔴 Streaming started successfully!');
        await loadStreamStatus();
      } else {
        toast.error(error || 'Failed to start streaming');
      }
    } else {
      const { data, error } = await liveSlotAPI.stop();
      if (data) {
        setIsLive(false);
        toast.success('Streaming stopped successfully');
        await loadStreamStatus();
      } else {
        toast.error(error || 'Failed to stop streaming');
      }
    }
    setLoading(false);
  };

  const handleSettingChange = async (setting, value) => {
    if (setting === 'auto_rotate') setAutoRotate(value);
    if (setting === 'loop_videos') setLoopVideos(value);

    await liveSlotAPI.updateSettings({
      auto_rotate: setting === 'auto_rotate' ? value : autoRotate,
      loop_videos: setting === 'loop_videos' ? value : loopVideos
    });
    toast.success('Settings updated');
  };

  return (
    <div className="space-y-8" data-testid="live-slot-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Live Slot Management</h1>
        <p className="text-gray-400">Configure and manage your live streaming slots</p>
      </div>

      {/* No Plan Warning */}
      {!hasActivePlan && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-6" data-testid="live-slot-no-plan-warning">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <AlertTriangle className="w-6 h-6 text-amber-500" />
              <div>
                <h3 className="text-white font-semibold">No Active Plan</h3>
                <p className="text-gray-400 text-sm">Purchase a plan to start streaming</p>
              </div>
            </div>
            <Button 
              onClick={() => navigate('/dashboard/billings')}
              className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
            >
              View Plans
            </Button>
          </div>
        </div>
      )}

      {/* Live Status Card */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
              isLive ? 'bg-emerald-500/20' : 'bg-gray-700'
            }`}>
              <Radio className={`w-6 h-6 ${isLive ? 'text-emerald-500' : 'text-gray-500'}`} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Live Slot #1</h2>
              <p className={`text-sm ${isLive ? 'text-emerald-400' : 'text-gray-500'}`}>
                {isLive ? 'Currently Live' : 'Offline'}
              </p>
            </div>
          </div>
          {isLive && (
            <span className="flex items-center space-x-2 px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-sm font-medium">
              <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
              <span>Broadcasting</span>
            </span>
          )}
        </div>

        {isLive && streamStatus && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-gray-700/50 rounded-xl p-4">
              <p className="text-gray-400 text-sm mb-1">Current Video</p>
              <p className="text-white font-medium">{streamStatus.current_video || 'N/A'}</p>
            </div>
            <div className="bg-gray-700/50 rounded-xl p-4">
              <p className="text-gray-400 text-sm mb-1">Next Video</p>
              <p className="text-white font-medium">{streamStatus.next_video || 'N/A'}</p>
            </div>
            <div className="bg-gray-700/50 rounded-xl p-4">
              <p className="text-gray-400 text-sm mb-1">Viewers</p>
              <p className="text-white font-medium">{streamStatus.viewers || 0}</p>
            </div>
          </div>
        )}

        <Button 
          onClick={handleToggleLive}
          disabled={loading}
          data-testid="toggle-stream-button"
          className={`w-full py-6 text-lg font-semibold ${
            isLive 
              ? 'bg-red-600 hover:bg-red-700 text-white' 
              : 'bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white'
          }`}
        >
          {loading ? (
            'Processing...'
          ) : isLive ? (
            <>
              <StopCircle className="w-5 h-5 mr-2" />
              Stop Streaming
            </>
          ) : (
            <>
              <PlayCircle className="w-5 h-5 mr-2" />
              Start Streaming
            </>
          )}
        </Button>
      </div>

      {/* Stream Settings */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-6 flex items-center">
          <SettingsIcon className="w-5 h-5 mr-2 text-blue-500" />
          Stream Settings
        </h2>

        <div className="space-y-6">
          <div className="flex items-center justify-between p-4 bg-gray-700/30 rounded-xl">
            <div>
              <Label htmlFor="auto-rotate" className="text-white font-medium">Auto Video Rotation</Label>
              <p className="text-sm text-gray-400 mt-1">Automatically play next video when current ends</p>
            </div>
            <Switch 
              id="auto-rotate"
              checked={autoRotate}
              onCheckedChange={(v) => handleSettingChange('auto_rotate', v)}
              data-testid="auto-rotate-switch"
            />
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-700/30 rounded-xl">
            <div>
              <Label htmlFor="loop-videos" className="text-white font-medium">Loop Videos</Label>
              <p className="text-sm text-gray-400 mt-1">Replay videos when playlist ends</p>
            </div>
            <Switch 
              id="loop-videos"
              checked={loopVideos}
              onCheckedChange={(v) => handleSettingChange('loop_videos', v)}
              data-testid="loop-videos-switch"
            />
          </div>

          <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-xl">
            <h3 className="text-white font-medium mb-2">YouTube Connection</h3>
            <p className="text-gray-400 text-sm mb-4">Connect your YouTube channel to start streaming</p>
            <Button variant="outline" className="border-blue-500 text-blue-400 hover:bg-blue-500/10">
              Connect YouTube
            </Button>
          </div>
        </div>
      </div>

      {/* No Plan Dialog */}
      <Dialog open={showPlanDialog} onOpenChange={setShowPlanDialog}>
        <DialogContent className="bg-gray-800 border-gray-700" data-testid="live-slot-plan-dialog">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center">
              <AlertTriangle className="w-6 h-6 mr-2 text-amber-500" />
              Plan Required
            </DialogTitle>
            <DialogDescription className="text-gray-400 pt-4 text-base">
              ⚠️ Please purchase a slot/plan first to proceed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button 
              variant="outline"
              onClick={() => setShowPlanDialog(false)}
              className="border-gray-600 text-gray-300 hover:bg-gray-700"
            >
              Cancel
            </Button>
            <Button 
              onClick={() => navigate('/dashboard/billings')}
              className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
            >
              View Plans
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default LiveSlot;

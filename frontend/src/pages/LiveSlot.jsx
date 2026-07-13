import React, { useState, useEffect } from 'react';
import { Radio, Settings as SettingsIcon, PlayCircle, StopCircle, AlertTriangle, Youtube, Check, ExternalLink } from 'lucide-react';
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
import { liveSlotAPI, youtubeAPI, videoAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

const LiveSlot = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [streamStatus, setStreamStatus] = useState(null);
  const [isLive, setIsLive] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);
  const [loopVideos, setLoopVideos] = useState(true);
  const [loading, setLoading] = useState(false);
  const [showPlanDialog, setShowPlanDialog] = useState(false);
  const [ytStatus, setYtStatus] = useState({ configured: false, connected: false, channel: null });
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState('');
  const [ytLoading, setYtLoading] = useState(false);

  const hasActivePlan = user?.plan && user?.plan_expires_at;

  useEffect(() => {
    if (hasActivePlan) {
      loadStreamStatus();
      loadVideos();
    }
    loadYoutubeStatus();

    // Handle OAuth redirect result
    const ytResult = searchParams.get('youtube');
    if (ytResult === 'connected') {
      toast.success('YouTube channel connected successfully!');
      setSearchParams({});
    } else if (ytResult === 'error') {
      toast.error('Failed to connect YouTube channel. Please try again.');
      setSearchParams({});
    }
  }, []);

  const loadYoutubeStatus = async () => {
    const { data } = await youtubeAPI.getStatus();
    if (data) setYtStatus(data);
  };

  const loadVideos = async () => {
    const { data } = await videoAPI.getAll();
    if (data) {
      setVideos(data);
      if (data.length > 0) setSelectedVideo(data[0].video_id);
    }
  };

  const handleConnectYoutube = async () => {
    setYtLoading(true);
    const { data, error } = await youtubeAPI.getAuthUrl();
    setYtLoading(false);
    if (data?.authorization_url) {
      window.location.href = data.authorization_url;
    } else {
      toast.error(error || 'YouTube integration not configured yet.');
    }
  };

  const handleDisconnectYoutube = async () => {
    await youtubeAPI.disconnect();
    toast.success('YouTube channel disconnected');
    loadYoutubeStatus();
  };

  const handleGoLiveYoutube = async () => {
    if (!selectedVideo) {
      toast.error('Please select a video to stream');
      return;
    }
    setYtLoading(true);
    const { data, error } = await youtubeAPI.createBroadcast(selectedVideo);
    setYtLoading(false);
    if (data) {
      toast.success('Broadcast started! Opening YouTube...');
      setIsLive(true);
      loadStreamStatus();
      if (data.watch_url) window.open(data.watch_url, '_blank');
    } else {
      toast.error(error || 'Failed to start YouTube broadcast');
    }
  };

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

          <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-xl" data-testid="youtube-connection-block">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-white font-medium flex items-center">
                <Youtube className="w-5 h-5 mr-2 text-red-500" />
                YouTube Connection
              </h3>
              {ytStatus.connected && (
                <span className="flex items-center text-emerald-400 text-sm font-medium">
                  <Check className="w-4 h-4 mr-1" /> Connected
                </span>
              )}
            </div>

            {!ytStatus.configured ? (
              <p className="text-amber-400/80 text-sm" data-testid="youtube-not-configured">
                YouTube integration is not configured yet. Add your OAuth credentials to enable channel connection.
              </p>
            ) : ytStatus.connected ? (
              <div>
                <p className="text-gray-300 text-sm mb-3">
                  Channel: <span className="font-semibold text-white">{ytStatus.channel?.channel_title || 'Connected'}</span>
                </p>
                {hasActivePlan && videos.length > 0 && (
                  <div className="mb-3">
                    <Label className="text-gray-400 text-sm">Select video to stream</Label>
                    <select
                      value={selectedVideo}
                      onChange={(e) => setSelectedVideo(e.target.value)}
                      className="mt-1 w-full bg-gray-700 border border-gray-600 text-white rounded-lg px-3 py-2"
                      data-testid="youtube-video-select"
                    >
                      {videos.map((v) => (
                        <option key={v.video_id} value={v.video_id}>{v.title}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="flex gap-2">
                  <Button
                    onClick={handleGoLiveYoutube}
                    disabled={ytLoading || !hasActivePlan || videos.length === 0}
                    className="bg-red-600 hover:bg-red-700 text-white"
                    data-testid="youtube-go-live-button"
                  >
                    <Youtube className="w-4 h-4 mr-2" />
                    {ytLoading ? 'Starting...' : 'Go Live on YouTube'}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleDisconnectYoutube}
                    className="border-gray-600 text-gray-300 hover:bg-gray-700"
                    data-testid="youtube-disconnect-button"
                  >
                    Disconnect
                  </Button>
                </div>
                {videos.length === 0 && hasActivePlan && (
                  <p className="text-gray-500 text-xs mt-2">Upload a video first to stream it.</p>
                )}
              </div>
            ) : (
              <div>
                <p className="text-gray-400 text-sm mb-4">Connect your YouTube channel to start streaming</p>
                <Button
                  onClick={handleConnectYoutube}
                  disabled={ytLoading}
                  variant="outline"
                  className="border-blue-500 text-blue-400 hover:bg-blue-500/10"
                  data-testid="connect-youtube-button"
                >
                  <Youtube className="w-4 h-4 mr-2" />
                  {ytLoading ? 'Connecting...' : 'Connect YouTube'}
                </Button>
              </div>
            )}
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

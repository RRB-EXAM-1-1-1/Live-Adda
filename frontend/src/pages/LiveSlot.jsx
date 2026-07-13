import React, { useState } from 'react';
import { Radio, Settings as SettingsIcon, PlayCircle, StopCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { mockStreamStatus } from '../mock';

const LiveSlot = () => {
  const [isLive, setIsLive] = useState(mockStreamStatus.isLive);
  const [autoRotate, setAutoRotate] = useState(true);
  const [loopVideos, setLoopVideos] = useState(true);

  const handleToggleLive = () => {
    setIsLive(!isLive);
    if (!isLive) {
      alert('Starting live stream...');
    } else {
      alert('Stopping live stream...');
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Live Slot Management</h1>
        <p className="text-gray-400">Configure and manage your live streaming slots</p>
      </div>

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

        {isLive && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-gray-700/50 rounded-xl p-4">
              <p className="text-gray-400 text-sm mb-1">Current Video</p>
              <p className="text-white font-medium">{mockStreamStatus.currentVideo}</p>
            </div>
            <div className="bg-gray-700/50 rounded-xl p-4">
              <p className="text-gray-400 text-sm mb-1">Uptime</p>
              <p className="text-white font-medium">{mockStreamStatus.uptime}</p>
            </div>
            <div className="bg-gray-700/50 rounded-xl p-4">
              <p className="text-gray-400 text-sm mb-1">Viewers</p>
              <p className="text-white font-medium">{mockStreamStatus.viewers}</p>
            </div>
          </div>
        )}

        <Button 
          onClick={handleToggleLive}
          className={`w-full py-6 text-lg font-semibold ${
            isLive 
              ? 'bg-red-600 hover:bg-red-700 text-white' 
              : 'bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white'
          }`}
        >
          {isLive ? (
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
              onCheckedChange={setAutoRotate}
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
              onCheckedChange={setLoopVideos}
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
    </div>
  );
};

export default LiveSlot;

import React, { useState, useEffect, useRef } from 'react';
import { Upload, Play, Trash2, Clock, HardDrive, Edit2, X, Check, AlertTriangle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Progress } from '../components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '../components/ui/dialog';
import { videoAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useUpload } from '../contexts/UploadContext';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Thumbnail that falls back to a Play icon if the JPEG isn't ready yet.
const VideoThumbnail = ({ videoId, title }) => {
  const [failed, setFailed] = React.useState(false);
  const src = `${BACKEND_URL}/api/videos/${videoId}/thumbnail`;
  if (failed) {
    return <Play className="w-16 h-16 text-gray-600" data-testid={`video-thumb-fallback-${videoId}`} />;
  }
  return (
    <img
      src={src}
      alt={title || 'Video preview'}
      loading="lazy"
      onError={() => setFailed(true)}
      className="w-full h-full object-cover"
      data-testid={`video-thumb-${videoId}`}
    />
  );
};

const MAX_STORAGE_GB = 2;
const MAX_STORAGE_BYTES = MAX_STORAGE_GB * 1024 * 1024 * 1024;

const formatBytes = (bytes) => {
  if (bytes === 0) return '0 MB';
  const mb = bytes / (1024 * 1024);
  if (mb < 1024) return `${mb.toFixed(0)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
};

const VideoManager = () => {
  const { user, refreshUser } = useAuth();
  const { startUpload, isUploading, progress, onComplete } = useUpload();
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showPlanDialog, setShowPlanDialog] = useState(false);
  const [renameDialog, setRenameDialog] = useState({ open: false, videoId: null, currentTitle: '' });
  const [newTitle, setNewTitle] = useState('');
  const fileInputRef = useRef(null);

  const hasActivePlan = user?.plan && user?.plan_expires_at;
  const storageUsed = user?.storage_used || 0;
  const storagePercent = Math.min((storageUsed / MAX_STORAGE_BYTES) * 100, 100);

  useEffect(() => {
    loadVideos();
  }, []);

  // When ANY upload (started from this page or elsewhere) completes, refresh
  // the video list + user's storage counters. This runs even if the upload
  // finished while the user was on a different page.
  useEffect(() => {
    const off = onComplete(async () => {
      // Refresh both in parallel so the Storage Usage widget updates immediately
      await Promise.all([loadVideos(), refreshUser()]);
    });
    return off;
  }, [onComplete, refreshUser]);

  const loadVideos = async () => {
    setLoading(true);
    const { data } = await videoAPI.getAll();
    if (data) {
      // Defensive de-dupe: if any legacy duplicates exist in DB, only show the
      // first per (upload_id) or video_id.
      const seen = new Set();
      const deduped = [];
      for (const v of data) {
        const key = v.upload_id || v.video_id;
        if (seen.has(key)) continue;
        seen.add(key);
        deduped.push(v);
      }
      setVideos(deduped);
    }
    setLoading(false);
  };

  const handleUploadClick = () => {
    if (!hasActivePlan) {
      setShowPlanDialog(true);
      return;
    }
    if (isUploading) {
      toast.info('An upload is already in progress.');
      return;
    }
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;

    if ((storageUsed + file.size) > MAX_STORAGE_BYTES) {
      toast.error(`Storage limit exceeded! You have ${MAX_STORAGE_GB}GB limit.`);
      return;
    }

    const title = file.name.replace(/\.[^/.]+$/, '');
    // Fire-and-forget: the global UploadContext owns the promise, so it
    // survives navigation away from this page.
    const result = await startUpload(file, title);
    if (result?.error) {
      if (typeof result.error === 'string' && result.error.includes('purchase')) {
        setShowPlanDialog(true);
      }
    }
  };

  const handleDelete = async (videoId) => {
    if (!window.confirm('Are you sure you want to delete this video?')) return;

    const { error } = await videoAPI.delete(videoId);
    if (!error) {
      toast.success('Video deleted successfully');
      await loadVideos();
      await refreshUser();
    } else {
      toast.error(error);
    }
  };

  const openRenameDialog = (video) => {
    setRenameDialog({ open: true, videoId: video.video_id, currentTitle: video.title });
    setNewTitle(video.title);
  };

  const handleRename = async () => {
    if (!newTitle.trim()) {
      toast.error('Title cannot be empty');
      return;
    }

    const { data, error } = await videoAPI.rename(renameDialog.videoId, newTitle.trim());
    if (data) {
      toast.success('Video renamed successfully');
      setRenameDialog({ open: false, videoId: null, currentTitle: '' });
      await loadVideos();
    } else {
      toast.error(error);
    }
  };

  return (
    <div className="space-y-8" data-testid="video-manager-page">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*"
        onChange={handleFileSelect}
        className="hidden"
        data-testid="video-file-input"
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Video Manager</h1>
          <p className="text-gray-400">Upload and manage your streaming videos</p>
        </div>
        <Button 
          onClick={handleUploadClick}
          disabled={isUploading}
          data-testid="upload-video-button"
          className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
        >
          <Upload className="w-4 h-4 mr-2" />
          {isUploading ? 'Uploading...' : 'Upload Video'}
        </Button>
      </div>

      {/* Upload Progress */}
      {isUploading && (
        <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-blue-500/50" data-testid="upload-progress-container">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold text-white flex items-center">
              <Upload className="w-5 h-5 mr-2 text-blue-500 animate-pulse" />
              Uploading & Processing...
            </h3>
            <span className="text-2xl font-bold text-blue-400" data-testid="upload-progress-percent">{progress}%</span>
          </div>
          <Progress value={progress} className="h-3" />
          <p className="text-gray-400 text-sm mt-2">Uploading in the background — you can navigate to other pages, the upload will not stop.</p>
        </div>
      )}

      {/* Storage Info */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center">
            <HardDrive className="w-5 h-5 mr-2 text-blue-500" />
            Storage Usage
          </h3>
          <span className="text-gray-400" data-testid="storage-usage-text">
            {formatBytes(storageUsed)} / {MAX_STORAGE_GB} GB
          </span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-3">
          <div 
            className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all" 
            style={{ width: `${storagePercent}%` }}
          ></div>
        </div>
      </div>

      {/* Videos Grid */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-400">Loading videos...</p>
        </div>
      ) : videos.length === 0 ? (
        <div className="text-center py-12" data-testid="no-videos-message">
          <Upload className="w-16 h-16 mx-auto text-gray-600 mb-4" />
          <h3 className="text-xl font-semibold text-gray-400 mb-2">No videos uploaded yet</h3>
          <p className="text-gray-500 mb-6">Upload your first video to start streaming</p>
          <Button 
            onClick={handleUploadClick}
            className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
          >
            <Upload className="w-4 h-4 mr-2" />
            Upload Video
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="videos-grid">
          {videos.map((video) => (
            <div key={video.video_id} className="bg-gray-800/50 backdrop-blur-lg rounded-2xl overflow-hidden border border-gray-700 hover:border-gray-600 transition-all group">
              {/* Thumbnail */}
              <div className="relative aspect-video bg-gradient-to-br from-gray-900 to-gray-800 flex items-center justify-center overflow-hidden">
                <VideoThumbnail videoId={video.video_id} title={video.title} />
                {/* Duration + Resolution chips */}
                <div className="absolute bottom-2 right-2 flex gap-1.5">
                  {video.duration && video.duration !== '00:00' && (
                    <span
                      className="px-2 py-0.5 bg-black/80 text-white text-[11px] font-medium rounded"
                      data-testid={`video-duration-${video.video_id}`}
                    >
                      {video.duration}
                    </span>
                  )}
                  {video.height ? (
                    <span
                      className="px-2 py-0.5 bg-blue-500/85 text-white text-[11px] font-semibold rounded"
                      data-testid={`video-resolution-${video.video_id}`}
                    >
                      {video.height}p
                    </span>
                  ) : null}
                </div>
              </div>

              {/* Info */}
              <div className="p-4">
                <h3 className="text-white font-semibold mb-2 truncate" data-testid={`video-title-${video.video_id}`}>{video.title}</h3>
                <div className="flex items-center justify-between text-sm text-gray-400 mb-4">
                  <span>{formatBytes(video.size)}</span>
                  <span className="flex items-center">
                    <Clock className="w-3 h-3 mr-1" />
                    {new Date(video.uploaded_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex gap-2">
                  <Button 
                    variant="outline"
                    size="sm" 
                    className="flex-1 border-gray-600 text-gray-300 hover:bg-gray-700"
                    onClick={() => openRenameDialog(video)}
                    data-testid={`rename-video-${video.video_id}`}
                  >
                    <Edit2 className="w-4 h-4 mr-1" />
                    Rename
                  </Button>
                  <Button 
                    variant="destructive" 
                    size="sm" 
                    className="flex-1"
                    onClick={() => handleDelete(video.video_id)}
                    data-testid={`delete-video-${video.video_id}`}
                  >
                    <Trash2 className="w-4 h-4 mr-1" />
                    Delete
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* No Plan Dialog */}
      <Dialog open={showPlanDialog} onOpenChange={setShowPlanDialog}>
        <DialogContent className="bg-gray-800 border-gray-700" data-testid="no-plan-dialog">
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
              onClick={() => window.location.href = '/dashboard/billings'}
              className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
              data-testid="go-to-billings-button"
            >
              View Plans
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename Dialog */}
      <Dialog open={renameDialog.open} onOpenChange={(open) => setRenameDialog({ ...renameDialog, open })}>
        <DialogContent className="bg-gray-800 border-gray-700" data-testid="rename-dialog">
          <DialogHeader>
            <DialogTitle className="text-white">Rename Video</DialogTitle>
            <DialogDescription className="text-gray-400">
              Enter a new name for your video
            </DialogDescription>
          </DialogHeader>
          <Input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Video title"
            className="bg-gray-700 border-gray-600 text-white"
            data-testid="rename-input"
          />
          <DialogFooter>
            <Button 
              variant="outline"
              onClick={() => setRenameDialog({ open: false, videoId: null, currentTitle: '' })}
              className="border-gray-600 text-gray-300 hover:bg-gray-700"
            >
              Cancel
            </Button>
            <Button 
              onClick={handleRename}
              className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
              data-testid="confirm-rename-button"
            >
              <Check className="w-4 h-4 mr-2" />
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default VideoManager;

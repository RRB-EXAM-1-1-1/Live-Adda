import React, { useState } from 'react';
import { mockVideos } from '../mock';
import { Upload, Play, Trash2, Clock, HardDrive } from 'lucide-react';
import { Button } from '../components/ui/button';

const VideoManager = () => {
  const [videos, setVideos] = useState(mockVideos);

  const handleUpload = () => {
    alert('Video upload feature will be implemented with backend integration');
  };

  const handleDelete = (id) => {
    if (window.confirm('Are you sure you want to delete this video?')) {
      setVideos(videos.filter(v => v.id !== id));
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Video Manager</h1>
          <p className="text-gray-400">Upload and manage your streaming videos</p>
        </div>
        <Button 
          onClick={handleUpload}
          className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
        >
          <Upload className="w-4 h-4 mr-2" />
          Upload Video
        </Button>
      </div>

      {/* Storage Info */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center">
            <HardDrive className="w-5 h-5 mr-2 text-blue-500" />
            Storage Usage
          </h3>
          <span className="text-gray-400">1.65 GB / 25 GB</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-3">
          <div className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full" style={{ width: '6.6%' }}></div>
        </div>
      </div>

      {/* Videos Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {videos.map((video) => (
          <div key={video.id} className="bg-gray-800/50 backdrop-blur-lg rounded-2xl overflow-hidden border border-gray-700 hover:border-gray-600 transition-all group">
            {/* Thumbnail */}
            <div className="relative aspect-video bg-gray-900">
              <img 
                src={video.thumbnail} 
                alt={video.title}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <Button size="icon" className="bg-white/90 hover:bg-white text-gray-900 rounded-full w-12 h-12">
                  <Play className="w-6 h-6" />
                </Button>
              </div>
              <div className="absolute bottom-2 right-2 px-2 py-1 bg-black/80 text-white text-xs rounded">
                {video.duration}
              </div>
            </div>

            {/* Info */}
            <div className="p-4">
              <h3 className="text-white font-semibold mb-2 truncate">{video.title}</h3>
              <div className="flex items-center justify-between text-sm text-gray-400 mb-4">
                <span>{video.size}</span>
                <span className="flex items-center">
                  <Clock className="w-3 h-3 mr-1" />
                  {video.uploadedAt}
                </span>
              </div>
              <Button 
                variant="destructive" 
                size="sm" 
                className="w-full"
                onClick={() => handleDelete(video.id)}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </Button>
            </div>
          </div>
        ))}
      </div>

      {videos.length === 0 && (
        <div className="text-center py-12">
          <Upload className="w-16 h-16 mx-auto text-gray-600 mb-4" />
          <h3 className="text-xl font-semibold text-gray-400 mb-2">No videos uploaded yet</h3>
          <p className="text-gray-500 mb-6">Upload your first video to start streaming</p>
          <Button 
            onClick={handleUpload}
            className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
          >
            <Upload className="w-4 h-4 mr-2" />
            Upload Video
          </Button>
        </div>
      )}
    </div>
  );
};

export default VideoManager;

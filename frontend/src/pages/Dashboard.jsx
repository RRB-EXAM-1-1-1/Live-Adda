import React, { useState, useEffect } from 'react';
import { Activity, DollarSign, Radio, Video, TrendingUp, Clock, AlertTriangle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { useNavigate } from 'react-router-dom';
import { dashboardAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

const formatBytes = (bytes) => {
  if (!bytes || bytes === 0) return '0 MB';
  const mb = bytes / (1024 * 1024);
  if (mb < 1024) return `${mb.toFixed(0)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
};

const Dashboard = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const hasActivePlan = user?.plan && user?.plan_expires_at;

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    setLoading(true);
    const { data } = await dashboardAPI.getStats();
    if (data) {
      setStats(data);
    }
    setLoading(false);
  };

  const getRemainingDays = () => {
    if (!user?.plan_expires_at) return null;
    const expiry = new Date(user.plan_expires_at);
    const now = new Date();
    const days = Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
    return days > 0 ? days : 0;
  };

  const statCards = [
    {
      title: 'Active Live Slots',
      value: stats?.active_live_slots ?? 0,
      icon: Radio,
      iconColor: 'text-blue-400',
      bgColor: 'bg-blue-500/10'
    },
    {
      title: 'Total Videos',
      value: stats?.total_videos ?? 0,
      icon: Video,
      iconColor: 'text-emerald-400',
      bgColor: 'bg-emerald-500/10'
    },
    {
      title: 'Storage Used',
      value: formatBytes(stats?.storage_used ?? 0),
      icon: DollarSign,
      iconColor: 'text-amber-400',
      bgColor: 'bg-amber-500/10'
    },
    {
      title: 'Plan Validity',
      value: hasActivePlan ? `${getRemainingDays()} days` : 'No Plan',
      icon: Clock,
      iconColor: 'text-purple-400',
      bgColor: 'bg-purple-500/10'
    }
  ];

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
        <p className="text-gray-400">Welcome back, {user?.name || 'User'}</p>
      </div>

      {/* No Plan Warning */}
      {!hasActivePlan && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-6" data-testid="no-plan-warning">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <AlertTriangle className="w-6 h-6 text-amber-500" />
              <div>
                <h3 className="text-white font-semibold">No Active Plan</h3>
                <p className="text-gray-400 text-sm">Purchase a plan to start uploading videos and streaming</p>
              </div>
            </div>
            <Button 
              onClick={() => navigate('/dashboard/billings')}
              className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
              data-testid="dashboard-buy-plan-button"
            >
              View Plans
            </Button>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <div
              key={index}
              className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700 hover:border-gray-600 transition-all hover:transform hover:scale-105"
              data-testid={`stat-card-${index}`}
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`w-12 h-12 rounded-xl ${stat.bgColor} flex items-center justify-center`}>
                  <Icon className={`w-6 h-6 ${stat.iconColor}`} />
                </div>
              </div>
              <h3 className="text-gray-400 text-sm mb-1">{stat.title}</h3>
              <p className="text-3xl font-bold text-white">{stat.value}</p>
            </div>
          );
        })}
      </div>

      {/* Stream Status */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-white flex items-center">
            <Radio className="w-5 h-5 mr-2 text-emerald-500" />
            Live Stream Status
          </h2>
          {stats?.active_live_slots > 0 && (
            <span className="flex items-center space-x-2 px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-sm font-medium">
              <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
              <span>Live</span>
            </span>
          )}
        </div>

        <div className="text-center py-8">
          {stats?.active_live_slots > 0 ? (
            <p className="text-gray-300">Your stream is currently live!</p>
          ) : (
            <p className="text-gray-400">No active stream. Start streaming from the Live Slot page.</p>
          )}
        </div>

        <div className="flex space-x-3">
          <Button 
            onClick={() => navigate('/dashboard/videos')}
            className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
            data-testid="manage-videos-button"
          >
            Manage Videos
          </Button>
          <Button 
            variant="outline"
            onClick={() => navigate('/dashboard/live-slot')}
            className="border-gray-600 text-gray-300 hover:bg-gray-700"
            data-testid="configure-stream-button"
          >
            Configure Stream
          </Button>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-6 flex items-center">
          <Activity className="w-5 h-5 mr-2 text-blue-500" />
          Recent Activity
        </h2>
        
        {stats?.recent_activity && stats.recent_activity.length > 0 ? (
          <div className="space-y-4">
            {stats.recent_activity.map((activity, index) => (
              <div key={index} className="flex items-start space-x-4 p-4 rounded-xl bg-gray-700/30 hover:bg-gray-700/50 transition-colors">
                <div className="w-2 h-2 mt-2 rounded-full bg-emerald-500"></div>
                <div className="flex-1">
                  <p className="text-white font-medium">{activity.action}</p>
                  <p className="text-gray-400 text-sm">{activity.description}</p>
                </div>
                <span className="text-gray-500 text-sm whitespace-nowrap">
                  {new Date(activity.timestamp).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-400 text-center py-4">No recent activity yet</p>
        )}
      </div>
    </div>
  );
};

export default Dashboard;

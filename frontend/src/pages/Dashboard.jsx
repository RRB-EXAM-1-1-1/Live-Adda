import React from 'react';
import { mockUserData, mockStreamStatus, mockRecentActivity } from '../mock';
import { Activity, DollarSign, Radio, Video, TrendingUp, Clock } from 'lucide-react';
import { Button } from '../components/ui/button';
import { useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const navigate = useNavigate();

  const stats = [
    {
      title: 'Active Live Slots',
      value: mockUserData.activeLiveSlots,
      icon: Radio,
      color: 'from-blue-500 to-blue-600',
      bgColor: 'bg-blue-500/10'
    },
    {
      title: 'Total Videos',
      value: mockUserData.totalVideos,
      icon: Video,
      color: 'from-emerald-500 to-emerald-600',
      bgColor: 'bg-emerald-500/10'
    },
    {
      title: 'Account Balance',
      value: `$${mockUserData.balance.toFixed(2)}`,
      icon: DollarSign,
      color: 'from-amber-500 to-amber-600',
      bgColor: 'bg-amber-500/10'
    },
    {
      title: 'Current Viewers',
      value: mockStreamStatus.viewers,
      icon: TrendingUp,
      color: 'from-purple-500 to-purple-600',
      bgColor: 'bg-purple-500/10'
    }
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
        <p className="text-gray-400">Welcome back, {mockUserData.name}</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <div
              key={index}
              className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700 hover:border-gray-600 transition-all hover:transform hover:scale-105"
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`w-12 h-12 rounded-xl ${stat.bgColor} flex items-center justify-center`}>
                  <Icon className={`w-6 h-6 bg-gradient-to-r ${stat.color} bg-clip-text text-transparent`} style={{ WebkitTextFillColor: 'transparent', WebkitBackgroundClip: 'text', backgroundClip: 'text' }} />
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
          {mockStreamStatus.isLive && (
            <span className="flex items-center space-x-2 px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-sm font-medium">
              <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
              <span>Live</span>
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <p className="text-gray-400 text-sm mb-2">Current Video</p>
            <p className="text-white font-medium mb-4">{mockStreamStatus.currentVideo}</p>
            
            <p className="text-gray-400 text-sm mb-2">Next Video</p>
            <p className="text-white font-medium mb-4">{mockStreamStatus.nextVideo}</p>
          </div>
          
          <div>
            <p className="text-gray-400 text-sm mb-2">Stream Uptime</p>
            <div className="flex items-center space-x-2 mb-4">
              <Clock className="w-4 h-4 text-blue-400" />
              <p className="text-white font-medium">{mockStreamStatus.uptime}</p>
            </div>
            
            <p className="text-gray-400 text-sm mb-2">Current Viewers</p>
            <div className="flex items-center space-x-2 mb-4">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <p className="text-white font-medium">{mockStreamStatus.viewers}</p>
            </div>
          </div>
        </div>

        <div className="mt-6 flex space-x-3">
          <Button 
            onClick={() => navigate('/dashboard/videos')}
            className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
          >
            Manage Videos
          </Button>
          <Button 
            variant="outline"
            onClick={() => navigate('/dashboard/live-slot')}
            className="border-gray-600 text-gray-300 hover:bg-gray-700"
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
        
        <div className="space-y-4">
          {mockRecentActivity.map((activity) => (
            <div key={activity.id} className="flex items-start space-x-4 p-4 rounded-xl bg-gray-700/30 hover:bg-gray-700/50 transition-colors">
              <div className="w-2 h-2 mt-2 rounded-full bg-emerald-500"></div>
              <div className="flex-1">
                <p className="text-white font-medium">{activity.action}</p>
                <p className="text-gray-400 text-sm">{activity.description}</p>
              </div>
              <span className="text-gray-500 text-sm whitespace-nowrap">{activity.timestamp}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;

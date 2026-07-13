import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from './ui/button';
import { Play, TrendingUp, Clock } from 'lucide-react';

export const Hero = () => {
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-emerald-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-pulse" style={{ animationDelay: '2s' }}></div>
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 sm:py-32 text-center">
        {/* Badge */}
        <div className="inline-flex items-center space-x-2 bg-blue-100 text-blue-700 px-4 py-2 rounded-full text-xs sm:text-sm font-medium mb-8 animate-fade-in">
          <TrendingUp className="w-4 h-4 flex-shrink-0" />
          <span>Trusted by 10,000+ Content Creators</span>
        </div>

        {/* Main Headline */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold text-gray-900 mb-6 leading-tight">
          Stream Your Videos
          <span className="block mt-2 bg-gradient-to-r from-blue-600 via-blue-700 to-blue-800 bg-clip-text text-transparent">
            24/7 on YouTube
          </span>
        </h1>

        <p className="text-lg sm:text-xl md:text-2xl text-gray-600 mb-4 max-w-3xl mx-auto">
          No PC/Laptop Required!
        </p>

        <p className="text-base sm:text-lg text-gray-500 mb-12 max-w-2xl mx-auto">
          Keep your channel live around the clock with our automated streaming platform. Upload once, stream forever.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <Button 
            size="lg"
            onClick={() => navigate('/register')}
            className="w-full sm:w-auto bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white text-lg px-8 py-6 rounded-xl shadow-xl hover:shadow-2xl transition-all transform hover:scale-105"
          >
            <Play className="w-5 h-5 mr-2" />
            Start Streaming Now
          </Button>
          <Button 
            size="lg"
            variant="outline"
            onClick={() => document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' })}
            className="w-full sm:w-auto text-lg px-8 py-6 rounded-xl border-2 border-gray-300 hover:border-blue-500 hover:bg-blue-50 transition-all"
          >
            View Pricing
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          <div className="bg-white/60 backdrop-blur-sm rounded-2xl p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="flex items-center justify-center mb-2">
              <Clock className="w-8 h-8 text-blue-600" />
            </div>
            <div className="text-3xl font-bold text-gray-900 mb-1">24/7</div>
            <div className="text-gray-600">Continuous Streaming</div>
          </div>
          <div className="bg-white/60 backdrop-blur-sm rounded-2xl p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="flex items-center justify-center mb-2">
              <Play className="w-8 h-8 text-emerald-600" />
            </div>
            <div className="text-3xl font-bold text-gray-900 mb-1">10K+</div>
            <div className="text-gray-600">Active Streams</div>
          </div>
          <div className="bg-white/60 backdrop-blur-sm rounded-2xl p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="flex items-center justify-center mb-2">
              <TrendingUp className="w-8 h-8 text-blue-600" />
            </div>
            <div className="text-3xl font-bold text-gray-900 mb-1">99.9%</div>
            <div className="text-gray-600">Uptime Guarantee</div>
          </div>
        </div>
      </div>
    </div>
  );
};

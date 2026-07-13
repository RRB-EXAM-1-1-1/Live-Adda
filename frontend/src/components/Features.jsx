import React from 'react';
import { Radio, Upload, Settings, Shield, BarChart3, Headphones } from 'lucide-react';
import { mockFeatures } from '../mock';

const iconMap = {
  Radio: Radio,
  Upload: Upload,
  Settings: Settings,
  Shield: Shield,
  BarChart3: BarChart3,
  Headphones: Headphones
};

export const Features = () => {
  return (
    <section id="features" className="py-24 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Everything You Need to
            <span className="block mt-2 bg-gradient-to-r from-blue-600 to-blue-700 bg-clip-text text-transparent">
              Stream Like a Pro
            </span>
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Powerful features designed to make your streaming experience seamless and professional.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {mockFeatures.map((feature, index) => {
            const IconComponent = iconMap[feature.icon];
            return (
              <div 
                key={feature.id}
                className="group relative bg-gradient-to-br from-slate-50 to-blue-50 rounded-2xl p-8 hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-emerald-500/5 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity"></div>
                
                <div className="relative">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center mb-6 transform group-hover:scale-110 group-hover:rotate-3 transition-transform">
                    <IconComponent className="w-7 h-7 text-white" />
                  </div>
                  
                  <h3 className="text-xl font-bold text-gray-900 mb-3">
                    {feature.title}
                  </h3>
                  <p className="text-gray-600 leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

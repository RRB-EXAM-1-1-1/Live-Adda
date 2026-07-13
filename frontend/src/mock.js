// Mock data for Live Adda streaming service

export const mockPlans = [
  {
    id: 'daily',
    name: 'Daily',
    price: 4.99,
    duration: '24 Hours',
    badge: null,
    features: [
      '1 Active Live Slot',
      '24/7 Continuous Stream',
      '2GB Video Storage',
      'Standard Support'
    ]
  },
  {
    id: 'weekly',
    name: 'Weekly',
    price: 24.99,
    duration: '7 Days',
    badge: 'Popular',
    features: [
      '1 Active Live Slot',
      '24/7 Continuous Stream',
      '2GB Video Storage',
      'Priority Support'
    ]
  },
  {
    id: 'monthly',
    name: 'Monthly',
    price: 79.99,
    duration: '30 Days',
    badge: 'Best Value',
    features: [
      '1 Active Live Slot',
      '24/7 Continuous Stream',
      '2GB Video Storage',
      'Priority Support',
      'Advanced Analytics'
    ]
  }
];

export const mockFeatures = [
  {
    id: 1,
    title: 'Stream 24/7',
    description: 'Keep your YouTube channel live around the clock without any PC or laptop.',
    icon: 'Radio'
  },
  {
    id: 2,
    title: 'Easy Upload',
    description: 'Upload your videos once and let our system handle the continuous streaming.',
    icon: 'Upload'
  },
  {
    id: 3,
    title: 'Auto Management',
    description: 'Automatic video rotation and stream management keeps your channel active.',
    icon: 'Settings'
  },
  {
    id: 4,
    title: 'Secure & Reliable',
    description: 'Enterprise-grade infrastructure ensures your stream never goes down.',
    icon: 'Shield'
  },
  {
    id: 5,
    title: 'Analytics Dashboard',
    description: 'Track your stream performance with real-time analytics and insights.',
    icon: 'BarChart3'
  },
  {
    id: 6,
    title: 'Priority Support',
    description: 'Get help when you need it with our dedicated support team.',
    icon: 'Headphones'
  }
];

export const mockUserData = {
  name: 'John Doe',
  email: 'john@example.com',
  picture: 'https://ui-avatars.com/api/?name=John+Doe&background=0ea5e9&color=fff',
  plan: 'monthly',
  balance: 79.99,
  activeLiveSlots: 1,
  totalVideos: 12
};

export const mockStreamStatus = {
  isLive: true,
  currentVideo: 'Introduction to Live Streaming',
  viewers: 342,
  uptime: '48h 23m',
  nextVideo: 'Advanced Streaming Techniques'
};

export const mockVideos = [
  {
    id: 1,
    title: 'Introduction to Live Streaming',
    duration: '15:32',
    size: '450 MB',
    uploadedAt: '2024-01-15',
    thumbnail: 'https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=400&h=225&fit=crop'
  },
  {
    id: 2,
    title: 'Advanced Streaming Techniques',
    duration: '22:18',
    size: '680 MB',
    uploadedAt: '2024-01-14',
    thumbnail: 'https://images.unsplash.com/photo-1614332287897-cdc485fa562d?w=400&h=225&fit=crop'
  },
  {
    id: 3,
    title: 'Setting Up Your Channel',
    duration: '18:45',
    size: '520 MB',
    uploadedAt: '2024-01-13',
    thumbnail: 'https://images.unsplash.com/photo-1626814026160-2237a95fc5a0?w=400&h=225&fit=crop'
  }
];

export const mockRecentActivity = [
  {
    id: 1,
    action: 'Video uploaded',
    description: 'Introduction to Live Streaming',
    timestamp: '2 hours ago'
  },
  {
    id: 2,
    action: 'Stream started',
    description: 'Live slot 1 activated',
    timestamp: '5 hours ago'
  },
  {
    id: 3,
    action: 'Plan upgraded',
    description: 'Upgraded to Monthly plan',
    timestamp: '1 day ago'
  },
  {
    id: 4,
    action: 'Payment successful',
    description: '$79.99 charged',
    timestamp: '1 day ago'
  }
];

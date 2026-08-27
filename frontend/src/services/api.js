import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

// Create axios instance with credentials
const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Auto-refresh: on a 401, try refreshing the access token once, then retry.
let isRefreshing = false;
let refreshPromise = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const url = original?.url || '';

    // Don't try to refresh for the auth endpoints themselves
    const isAuthCall = url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/refresh');

    if (status === 401 && !original._retry && !isAuthCall) {
      original._retry = true;
      try {
        if (!isRefreshing) {
          isRefreshing = true;
          refreshPromise = api.post('/auth/refresh');
        }
        await refreshPromise;
        isRefreshing = false;
        refreshPromise = null;
        return api(original); // retry original request with new cookie
      } catch (refreshErr) {
        isRefreshing = false;
        refreshPromise = null;
        return Promise.reject(refreshErr);
      }
    }
    return Promise.reject(error);
  }
);

// Helper to format API errors
const formatApiError = (error) => {
  if (error.response?.data?.detail) {
    const detail = error.response.data.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map(e => e.msg || JSON.stringify(e)).join(' ');
    }
    if (detail.msg) return detail.msg;
  }
  return error.message || 'Something went wrong';
};

// Auth APIs
export const authAPI = {
  register: async (email, password, name, mobileNumber) => {
    try {
      const { data } = await api.post('/auth/register', { email, password, name, mobile_number: mobileNumber });
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  login: async (email, password) => {
    try {
      const { data } = await api.post('/auth/login', { email, password });
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  logout: async () => {
    try {
      await api.post('/auth/logout');
      return { error: null };
    } catch (error) {
      return { error: formatApiError(error) };
    }
  },

  getMe: async () => {
    try {
      const { data } = await api.get('/auth/me');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  }
};

// Video APIs
export const videoAPI = {
  // Chunked upload: splits the file into small parts so it never trips proxy
  // body-size limits (413), survives flaky connections, and keeps a smooth
  // progress bar. Each chunk is retried once on transient failure.
  upload: async (file, title, onProgress) => {
    const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB per chunk
    const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE));
    const uploadId = `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

    try {
      let lastData = null;
      for (let index = 0; index < totalChunks; index++) {
        const start = index * CHUNK_SIZE;
        const blob = file.slice(start, Math.min(start + CHUNK_SIZE, file.size));

        const formData = new FormData();
        formData.append('upload_id', uploadId);
        formData.append('chunk_index', index);
        formData.append('total_chunks', totalChunks);
        formData.append('filename', file.name);
        formData.append('title', title);
        formData.append('file', blob, file.name);

        // Retry a chunk once if it fails transiently
        let attempt = 0;
        while (true) {
          try {
            const { data } = await api.post('/videos/upload/chunk', formData, {
              headers: { 'Content-Type': 'multipart/form-data' },
              timeout: 0, // no client timeout for uploads
              onUploadProgress: (evt) => {
                if (!onProgress) return;
                const chunkLoaded = evt.total ? (evt.loaded / evt.total) * blob.size : 0;
                const overall = Math.min(99, Math.round(((start + chunkLoaded) / file.size) * 100));
                onProgress(overall);
              }
            });
            lastData = data;
            break;
          } catch (err) {
            attempt += 1;
            if (attempt >= 2) throw err;
          }
        }
      }
      if (onProgress) onProgress(100);
      return { data: lastData, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  getAll: async () => {
    try {
      const { data } = await api.get('/videos');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  rename: async (videoId, title) => {
    try {
      const { data } = await api.put(`/videos/${videoId}/rename`, { title });
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  delete: async (videoId) => {
    try {
      await api.delete(`/videos/${videoId}`);
      return { error: null };
    } catch (error) {
      return { error: formatApiError(error) };
    }
  }
};

// Live Slot APIs
export const liveSlotAPI = {
  getStatus: async () => {
    try {
      const { data } = await api.get('/live-slot');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  start: async () => {
    try {
      const { data } = await api.post('/live-slot/start');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  stop: async () => {
    try {
      const { data } = await api.post('/live-slot/stop');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  updateSettings: async (settings) => {
    try {
      const { data } = await api.put('/live-slot/settings', settings);
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  }
};

// Payment APIs
export const paymentAPI = {
  createCheckout: async (planId) => {
    try {
      const originUrl = window.location.origin;
      const { data } = await api.post('/payments/checkout-session', {
        plan_id: planId,
        origin_url: originUrl
      });
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  getCheckoutStatus: async (sessionId) => {
    try {
      const { data } = await api.get(`/payments/checkout-status/${sessionId}`);
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  }
};

// Billing APIs
export const billingAPI = {
  getCurrentPlan: async () => {
    try {
      const { data } = await api.get('/billings/current-plan');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  getTransactions: async () => {
    try {
      const { data } = await api.get('/billings/transactions');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  }
};

// Support APIs
export const supportAPI = {
  createTicket: async (subject, message) => {
    try {
      const { data } = await api.post('/support/ticket', { subject, message });
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  }
};

// Razorpay APIs
export const razorpayAPI = {
  createOrder: async (planId) => {
    try {
      const { data } = await api.post('/razorpay/create-order', { plan_id: planId });
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  verifyPayment: async (payload) => {
    try {
      const { data } = await api.post('/razorpay/verify-payment', payload);
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  }
};

// Dashboard APIs
export const dashboardAPI = {
  getStats: async () => {
    try {
      const { data } = await api.get('/dashboard/stats');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  }
};

// YouTube APIs
export const youtubeAPI = {
  getStatus: async () => {
    try {
      const { data } = await api.get('/youtube/status');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  getAuthUrl: async () => {
    try {
      const { data } = await api.get('/youtube/oauth/authorize');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  disconnect: async () => {
    try {
      await api.delete('/youtube/disconnect');
      return { error: null };
    } catch (error) {
      return { error: formatApiError(error) };
    }
  },

  createBroadcast: async (videoId, title) => {
    try {
      const { data } = await api.post('/youtube/broadcast/create', { video_id: videoId, title });
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  stopBroadcast: async () => {
    try {
      const { data } = await api.post('/youtube/broadcast/stop');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  startWithKey: async (videoId, streamKey, loop = true) => {
    try {
      const { data } = await api.post('/stream/start-with-key', {
        video_id: videoId,
        stream_key: streamKey,
        loop
      });
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  stopStream: async (streamId) => {
    try {
      const body = streamId ? { stream_id: streamId } : {};
      const { data } = await api.post('/stream/stop', body);
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  },

  listStreams: async () => {
    try {
      const { data } = await api.get('/streams');
      return { data, error: null };
    } catch (error) {
      return { data: null, error: formatApiError(error) };
    }
  }
};

export default api;

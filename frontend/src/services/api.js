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
  register: async (email, password, name) => {
    try {
      const { data } = await api.post('/auth/register', { email, password, name });
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
  upload: async (file, title, onProgress) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', title);

      const { data } = await api.post('/videos/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          if (onProgress) onProgress(percentCompleted);
        }
      });
      return { data, error: null };
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

export default api;

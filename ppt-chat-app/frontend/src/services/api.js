import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Session Management
export const sessionAPI = {
  create: () => api.post('/api/session/create'),
  get: (sessionId) => api.get(`/api/session/${sessionId}`),
  delete: (sessionId) => api.delete(`/api/session/${sessionId}`),
};

// Template Management
export const templateAPI = {
  upload: async (sessionId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    return api.post(`/api/template/upload?session_id=${sessionId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};

// Chat API
export const chatAPI = {
  sendMessage: (sessionId, message, context = []) => 
    api.post('/api/chat', {
      session_id: sessionId,
      message,
      context,
    }),
};

// Preview API
export const previewAPI = {
  getPreview: (sessionId) => api.get(`/api/preview/${sessionId}`),
  getSlideImage: (sessionId, slideNumber) => 
    `${API_BASE_URL}/static/previews/${sessionId}_slide_${slideNumber}.png`,
};

// Download API
export const downloadAPI = {
  getDownloadUrl: (sessionId) => `${API_BASE_URL}/api/download/${sessionId}`,
  downloadPresentation: async (sessionId) => {
    const response = await api.get(`/api/download/${sessionId}`, {
      responseType: 'blob',
    });
    
    // Create download link
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `presentation_${sessionId}.pptx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};

export default api;
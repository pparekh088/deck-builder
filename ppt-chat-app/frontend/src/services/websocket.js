import { reactive } from 'vue';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8001';

class WebSocketService {
  constructor() {
    this.ws = null;
    this.sessionId = null;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.state = reactive({
      connected: false,
      connecting: false,
      error: null,
    });
  }

  connect(sessionId) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      if (this.sessionId === sessionId) {
        return Promise.resolve();
      }
      this.disconnect();
    }

    this.sessionId = sessionId;
    this.state.connecting = true;
    this.state.error = null;

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(`${WS_BASE_URL}/ws/${sessionId}`);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.state.connected = true;
          this.state.connecting = false;
          this.reconnectAttempts = 0;
          // Ask server for initial status
          this.sendMessage({ type: 'get_status' });
          // Also request a preview snapshot in case we missed an earlier push
          this.sendMessage({ type: 'get_preview' });
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.state.error = 'Connection error';
          this.state.connecting = false;
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('WebSocket disconnected');
          this.state.connected = false;
          this.state.connecting = false;
          this.attemptReconnect();
        };
      } catch (error) {
        this.state.connecting = false;
        this.state.error = error.message;
        reject(error);
      }
    });
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.sessionId = null;
    this.state.connected = false;
    this.listeners.clear();
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.state.error = 'Connection lost. Please refresh the page.';
      return;
    }

    this.reconnectAttempts++;
    console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

    setTimeout(() => {
      if (this.sessionId && !this.state.connected) {
        this.connect(this.sessionId);
      }
    }, this.reconnectDelay * this.reconnectAttempts);
  }

  sendMessage(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.error('WebSocket is not connected');
    }
  }

  handleMessage(message) {
    const { type, data } = message;
    
    // Notify all listeners for this message type
    const listeners = this.listeners.get(type) || [];
    listeners.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error(`Error in WebSocket listener for ${type}:`, error);
      }
    });

    // Also notify wildcard listeners
    const wildcardListeners = this.listeners.get('*') || [];
    wildcardListeners.forEach(callback => {
      try {
        callback(message);
      } catch (error) {
        console.error('Error in wildcard WebSocket listener:', error);
      }
    });
  }

  on(type, callback) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type).push(callback);

    // Return unsubscribe function
    return () => {
      const listeners = this.listeners.get(type);
      if (listeners) {
        const index = listeners.indexOf(callback);
        if (index > -1) {
          listeners.splice(index, 1);
        }
      }
    };
  }

  off(type, callback) {
    const listeners = this.listeners.get(type);
    if (listeners) {
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  // Convenience methods for common message types
  onTemplateUploaded(callback) {
    return this.on('template_uploaded', callback);
  }

  onPreviewUpdate(callback) {
    return this.on('preview_update', callback);
  }

  onStatus(callback) {
    return this.on('status', callback);
  }

  onError(callback) {
    return this.on('error', callback);
  }

  // Send ping to keep connection alive
  startHeartbeat() {
    setInterval(() => {
      if (this.state.connected) {
        this.sendMessage({ type: 'ping' });
      }
    }, 30000); // Ping every 30 seconds
  }
}

// Create singleton instance
const wsService = new WebSocketService();
wsService.startHeartbeat();

export default wsService;
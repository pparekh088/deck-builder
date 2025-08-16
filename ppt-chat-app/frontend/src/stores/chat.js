import { defineStore } from 'pinia';
import { sessionAPI, templateAPI, chatAPI, downloadAPI, previewAPI } from '../services/api';
import wsService from '../services/websocket';

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessionId: null,
    messages: [],
    currentTemplate: null,
    presentationPreview: null,
    isLoading: false,
    error: null,
    statusMessage: '',
    wsConnected: false,
  }),

  getters: {
    hasTemplate: (state) => !!state.currentTemplate,
    hasPresentation: (state) => !!state.presentationPreview,
    sortedMessages: (state) => [...state.messages].sort((a, b) => 
      new Date(a.timestamp) - new Date(b.timestamp)
    ),
  },

  actions: {
    async initializeSession() {
      try {
        this.isLoading = true;
        this.error = null;

        // Create new session
        const response = await sessionAPI.create();
        this.sessionId = response.data.session_id;

        // Connect WebSocket
        await wsService.connect(this.sessionId);
        this.wsConnected = true;

        // Setup WebSocket listeners
        this.setupWebSocketListeners();

        return this.sessionId;
      } catch (error) {
        console.error('Failed to initialize session:', error);
        this.error = 'Failed to start session. Please try again.';
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    setupWebSocketListeners() {
      // Template uploaded
      wsService.onTemplateUploaded((data) => {
        this.currentTemplate = data;
        this.addSystemMessage(`Template "${data.template_name}" uploaded successfully`);
      });

      // Preview update
      wsService.onPreviewUpdate((data) => {
        // WebSocket push wins
        this.presentationPreview = data;
        this.statusMessage = 'Presentation updated';
      });

      // Status updates
      wsService.onStatus((data) => {
        this.statusMessage = data.message;
        if (data.has_template !== undefined) {
          this.currentTemplate = data.has_template ? this.currentTemplate : null;
        }
      });

      // Error handling
      wsService.onError((data) => {
        this.error = data.message;
        this.addSystemMessage(`Error: ${data.message}`, 'error');
      });
    },

    async uploadTemplate(file) {
      try {
        this.isLoading = true;
        this.error = null;

        const response = await templateAPI.upload(this.sessionId, file);
        
        this.currentTemplate = {
          id: response.data.template_id,
          name: response.data.template_name,
          thumbnail: response.data.thumbnail_url,
        };

        this.addSystemMessage(`Template "${file.name}" uploaded successfully`);
        
        return response.data;
      } catch (error) {
        console.error('Failed to upload template:', error);
        this.error = error.response?.data?.detail || 'Failed to upload template';
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    async sendMessage(message) {
      try {
        this.isLoading = true;
        this.error = null;

        // Add user message to chat
        this.addMessage('user', message);

        // Send to backend
        const response = await chatAPI.sendMessage(
          this.sessionId,
          message,
          this.messages.slice(-10) // Send last 10 messages as context
        );

        // Add AI response
        this.addMessage('assistant', response.data.response);

        // Update preview if available (fallback in case WS update is missed)
        if (response.data.preview_available) {
          try {
            const previewResp = await previewAPI.getPreview(this.sessionId);
            this.presentationPreview = previewResp.data;
            this.statusMessage = 'Presentation updated';
          } catch (e) {
            // ignore; WS may still deliver the update
          }
        }

        return response.data;
      } catch (error) {
        console.error('Failed to send message:', error);
        this.error = error.response?.data?.detail || 'Failed to send message';
        this.addSystemMessage('Failed to process message. Please try again.', 'error');
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    async downloadPresentation() {
      try {
        this.isLoading = true;
        this.error = null;
        this.statusMessage = 'Preparing download...';

        await downloadAPI.downloadPresentation(this.sessionId);
        
        this.statusMessage = 'Download complete';
        this.addSystemMessage('Presentation downloaded successfully');
      } catch (error) {
        console.error('Failed to download presentation:', error);
        this.error = 'Failed to download presentation';
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    addMessage(role, content) {
      this.messages.push({
        id: Date.now(),
        role,
        content,
        timestamp: new Date().toISOString(),
      });
    },

    addSystemMessage(content, type = 'info') {
      this.messages.push({
        id: Date.now(),
        role: 'system',
        content,
        type,
        timestamp: new Date().toISOString(),
      });
    },

    clearMessages() {
      this.messages = [];
    },

    resetSession() {
      this.sessionId = null;
      this.messages = [];
      this.currentTemplate = null;
      this.presentationPreview = null;
      this.error = null;
      this.statusMessage = '';
      wsService.disconnect();
      this.wsConnected = false;
    },

    async endSession() {
      try {
        if (this.sessionId) {
          await sessionAPI.delete(this.sessionId);
        }
      } catch (error) {
        console.error('Failed to end session:', error);
      } finally {
        this.resetSession();
      }
    },
  },
});
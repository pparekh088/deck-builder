<template>
  <div class="flex flex-col h-full bg-white rounded-lg shadow-lg">
    <!-- Header -->
    <div class="flex items-center justify-between p-4 border-b">
      <div>
        <h2 class="text-xl font-semibold text-gray-800">PowerPoint Chat</h2>
        <p class="text-sm text-gray-500">
          {{ currentTemplate ? `Using: ${currentTemplate.name}` : 'No template selected' }}
        </p>
      </div>
      <div class="flex items-center space-x-2">
        <span v-if="wsConnected" class="flex items-center text-green-600">
          <span class="w-2 h-2 bg-green-600 rounded-full mr-2 animate-pulse"></span>
          Connected
        </span>
        <span v-else class="flex items-center text-red-600">
          <span class="w-2 h-2 bg-red-600 rounded-full mr-2"></span>
          Disconnected
        </span>
      </div>
    </div>

    <!-- Messages Area -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
      <div v-if="messages.length === 0" class="text-center text-gray-500 mt-8">
        <DocumentTextIcon class="w-16 h-16 mx-auto mb-4 text-gray-300" />
        <p class="text-lg font-medium">Start a conversation</p>
        <p class="text-sm mt-2">Upload a template and begin creating your presentation</p>
      </div>

      <div v-for="message in sortedMessages" :key="message.id" 
           :class="getMessageClass(message.role)">
        <div :class="getMessageContentClass(message.role)">
          <div v-if="message.role === 'user'" class="flex items-start space-x-2">
            <UserCircleIcon class="w-6 h-6 text-blue-600 mt-1" />
            <div class="flex-1">
              <p class="text-sm font-medium text-gray-700">You</p>
              <p class="text-gray-800 whitespace-pre-wrap">{{ message.content }}</p>
            </div>
          </div>
          
          <div v-else-if="message.role === 'assistant'" class="flex items-start space-x-2">
            <SparklesIcon class="w-6 h-6 text-purple-600 mt-1" />
            <div class="flex-1">
              <p class="text-sm font-medium text-gray-700">AI Assistant</p>
              <p class="text-gray-800 whitespace-pre-wrap">{{ message.content }}</p>
            </div>
          </div>
          
          <div v-else-if="message.role === 'system'" 
               :class="['flex items-center space-x-2', message.type === 'error' ? 'text-red-600' : 'text-gray-600']">
            <InformationCircleIcon v-if="message.type !== 'error'" class="w-5 h-5" />
            <ExclamationCircleIcon v-else class="w-5 h-5" />
            <p class="text-sm">{{ message.content }}</p>
          </div>
        </div>
      </div>

      <div v-if="isLoading" class="flex items-center space-x-2 text-gray-500">
        <div class="flex space-x-1">
          <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
        </div>
        <span class="text-sm">{{ statusMessage || 'Processing...' }}</span>
      </div>
    </div>

    <!-- Input Area -->
    <div class="border-t p-4">
      <!-- Template Upload -->
      <div v-if="!currentTemplate" class="mb-4">
        <label class="flex items-center justify-center w-full p-4 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-500 transition-colors">
          <input type="file" 
                 accept=".pptx" 
                 @change="handleTemplateUpload" 
                 class="hidden">
          <div class="text-center">
            <DocumentArrowUpIcon class="w-8 h-8 mx-auto mb-2 text-gray-400" />
            <p class="text-sm text-gray-600">Click to upload PowerPoint template (.pptx)</p>
          </div>
        </label>
      </div>

      <!-- Message Input -->
      <form @submit.prevent="handleSendMessage" class="flex space-x-2">
        <div class="flex-1 relative">
          <input v-model="messageInput"
                 :disabled="isLoading || !sessionId"
                 type="text"
                 placeholder="Type your message..."
                 class="w-full px-4 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed">
          
          <!-- Change Template Button -->
          <button v-if="currentTemplate"
                  @click="showTemplateUpload = true"
                  type="button"
                  class="absolute right-2 top-1/2 transform -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600">
            <PaperClipIcon class="w-5 h-5" />
          </button>
        </div>
        
        <button type="submit"
                :disabled="!messageInput.trim() || isLoading || !sessionId"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors">
          <PaperAirplaneIcon class="w-5 h-5" />
        </button>
      </form>

      <!-- Template Change Modal -->
      <div v-if="showTemplateUpload && currentTemplate" 
           class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white rounded-lg p-6 max-w-md w-full">
          <h3 class="text-lg font-semibold mb-4">Change Template</h3>
          <p class="text-sm text-gray-600 mb-4">Current template: {{ currentTemplate.name }}</p>
          <label class="flex items-center justify-center w-full p-4 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-500 transition-colors">
            <input type="file" 
                   accept=".pptx" 
                   @change="handleTemplateChange" 
                   class="hidden">
            <div class="text-center">
              <DocumentArrowUpIcon class="w-8 h-8 mx-auto mb-2 text-gray-400" />
              <p class="text-sm text-gray-600">Click to upload new template</p>
            </div>
          </label>
          <button @click="showTemplateUpload = false"
                  class="mt-4 w-full px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors">
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useChatStore } from '../stores/chat';
import {
  DocumentTextIcon,
  UserCircleIcon,
  SparklesIcon,
  InformationCircleIcon,
  ExclamationCircleIcon,
  DocumentArrowUpIcon,
  PaperAirplaneIcon,
  PaperClipIcon,
} from '@heroicons/vue/24/outline';

const chatStore = useChatStore();
const {
  sessionId,
  messages,
  sortedMessages,
  currentTemplate,
  isLoading,
  statusMessage,
  wsConnected,
} = storeToRefs(chatStore);

const messageInput = ref('');
const messagesContainer = ref(null);
const showTemplateUpload = ref(false);

const getMessageClass = (role) => {
  return {
    'user': 'flex justify-end',
    'assistant': 'flex justify-start',
    'system': 'flex justify-center',
  }[role] || '';
};

const getMessageContentClass = (role) => {
  const baseClass = 'max-w-lg px-4 py-2 rounded-lg';
  const roleClass = {
    'user': 'bg-blue-100 text-gray-800',
    'assistant': 'bg-gray-100 text-gray-800',
    'system': 'bg-yellow-50 text-gray-600 text-sm',
  }[role] || '';
  
  return `${baseClass} ${roleClass}`;
};

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
};

const handleSendMessage = async () => {
  if (!messageInput.value.trim() || isLoading.value) return;
  
  const message = messageInput.value;
  messageInput.value = '';
  
  try {
    await chatStore.sendMessage(message);
    scrollToBottom();
  } catch (error) {
    console.error('Failed to send message:', error);
  }
};

const handleTemplateUpload = async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  
  try {
    await chatStore.uploadTemplate(file);
    scrollToBottom();
  } catch (error) {
    console.error('Failed to upload template:', error);
  }
  
  event.target.value = '';
};

const handleTemplateChange = async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  
  try {
    await chatStore.uploadTemplate(file);
    showTemplateUpload.value = false;
    scrollToBottom();
  } catch (error) {
    console.error('Failed to change template:', error);
  }
  
  event.target.value = '';
};

onMounted(async () => {
  if (!sessionId.value) {
    await chatStore.initializeSession();
  }
});

onUnmounted(() => {
  // Keep session alive when component unmounts
  // Session will be cleared when user explicitly ends it or closes the app
});
</script>
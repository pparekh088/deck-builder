<script setup>
import { onMounted, onUnmounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useChatStore } from './stores/chat';
import ChatInterface from './components/ChatInterface.vue';
import PreviewPanel from './components/PreviewPanel.vue';
import {
  SparklesIcon,
  ExclamationTriangleIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline';

const chatStore = useChatStore();
const { sessionId, error } = storeToRefs(chatStore);

const handleNewSession = async () => {
  if (confirm('Are you sure you want to start a new session? Current progress will be lost.')) {
    await chatStore.endSession();
    await chatStore.initializeSession();
  }
};

const clearError = () => {
  chatStore.error = null;
};

// Auto-clear errors after 5 seconds
watch(error, (newError) => {
  if (newError) {
    setTimeout(() => {
      chatStore.error = null;
    }, 5000);
  }
});

onMounted(async () => {
  // Initialize session on app mount
  if (!sessionId.value) {
    await chatStore.initializeSession();
  }
});

onUnmounted(() => {
  // Clean up when app unmounts
  // Note: We don't end the session here to allow page refreshes
});
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
    <!-- Header -->
    <header class="bg-white shadow-sm border-b">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center space-x-3">
            <SparklesIcon class="w-8 h-8 text-indigo-600" />
            <h1 class="text-2xl font-bold text-gray-900">PowerPoint AI Generator</h1>
          </div>
          <div class="flex items-center space-x-4">
            <span v-if="sessionId" class="text-sm text-gray-500">
              Session: {{ sessionId.slice(0, 8) }}...
            </span>
            <button v-if="sessionId"
                    @click="handleNewSession"
                    class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              New Session
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[calc(100vh-8rem)]">
        <!-- Chat Interface -->
        <ChatInterface />
        
        <!-- Preview Panel -->
        <PreviewPanel />
      </div>
    </main>

    <!-- Error Toast -->
    <Teleport to="body">
      <Transition name="toast">
        <div v-if="error" 
             class="fixed bottom-4 right-4 bg-red-600 text-white px-6 py-3 rounded-lg shadow-lg z-50">
          <div class="flex items-center space-x-2">
            <ExclamationTriangleIcon class="w-5 h-5" />
            <span>{{ error }}</span>
            <button @click="clearError" class="ml-4 hover:text-red-200">
              <XMarkIcon class="w-5 h-5" />
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  transform: translateX(100%);
  opacity: 0;
}

.toast-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>

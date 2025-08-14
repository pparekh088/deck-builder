<template>
  <div class="flex flex-col h-full bg-white rounded-lg shadow-lg">
    <!-- Header -->
    <div class="flex items-center justify-between p-4 border-b">
      <h2 class="text-xl font-semibold text-gray-800">Presentation Preview</h2>
      <div class="flex items-center space-x-2">
        <button v-if="hasPresentation"
                @click="handleDownload"
                :disabled="isLoading"
                class="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors">
          <ArrowDownTrayIcon class="w-5 h-5" />
          <span>Download</span>
        </button>
      </div>
    </div>

    <!-- Preview Content -->
    <div class="flex-1 overflow-y-auto p-4">
      <div v-if="!presentationPreview" class="flex flex-col items-center justify-center h-full text-gray-500">
        <PresentationChartBarIcon class="w-24 h-24 mb-4 text-gray-300" />
        <p class="text-lg font-medium">No presentation yet</p>
        <p class="text-sm mt-2">Start chatting to generate slides</p>
      </div>

      <div v-else class="space-y-6">
        <!-- Slide Count -->
        <div class="text-sm text-gray-600">
          Total slides: {{ presentationPreview.total_slides }}
        </div>

        <!-- Slides Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div v-for="slide in presentationPreview.slides" 
               :key="slide.slide_number"
               class="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:shadow-md transition-shadow">
            <!-- Slide Number -->
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm font-medium text-gray-600">
                Slide {{ slide.slide_number }}
              </span>
              <button @click="selectedSlide = slide"
                      class="text-blue-600 hover:text-blue-700 text-sm">
                <EyeIcon class="w-4 h-4" />
              </button>
            </div>

            <!-- Slide Content Preview -->
            <div class="bg-white rounded p-3 min-h-[150px]">
              <h3 class="font-semibold text-gray-800 mb-2">{{ slide.title }}</h3>
              <div class="text-sm text-gray-600 space-y-1">
                <p v-for="(line, idx) in getContentLines(slide.content)" 
                   :key="idx"
                   class="truncate">
                  {{ line }}
                </p>
              </div>
            </div>

            <!-- Slide Image Preview (if available) -->
            <div v-if="slide.image_url" class="mt-2">
              <img :src="slide.image_url" 
                   :alt="`Slide ${slide.slide_number}`"
                   class="w-full rounded border border-gray-200">
            </div>
          </div>
        </div>

        <!-- Last Updated -->
        <div class="text-xs text-gray-500 text-center mt-4">
          Last updated: {{ formatDate(presentationPreview.generated_at) }}
        </div>
      </div>
    </div>

    <!-- Slide Detail Modal -->
    <Teleport to="body">
      <div v-if="selectedSlide" 
           @click="selectedSlide = null"
           class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div @click.stop 
             class="bg-white rounded-lg max-w-3xl w-full max-h-[90vh] overflow-y-auto">
          <!-- Modal Header -->
          <div class="flex items-center justify-between p-4 border-b">
            <h3 class="text-lg font-semibold">
              Slide {{ selectedSlide.slide_number }}: {{ selectedSlide.title }}
            </h3>
            <button @click="selectedSlide = null"
                    class="p-1 hover:bg-gray-100 rounded">
              <XMarkIcon class="w-6 h-6 text-gray-600" />
            </button>
          </div>

          <!-- Modal Content -->
          <div class="p-6">
            <!-- Slide Image (if available) -->
            <div v-if="selectedSlide.image_url" class="mb-4">
              <img :src="selectedSlide.image_url" 
                   :alt="`Slide ${selectedSlide.slide_number}`"
                   class="w-full rounded border border-gray-200">
            </div>

            <!-- Slide Text Content -->
            <div class="bg-gray-50 rounded-lg p-4">
              <h4 class="font-semibold text-gray-800 mb-3">{{ selectedSlide.title }}</h4>
              <div class="text-gray-700 whitespace-pre-wrap">{{ selectedSlide.content }}</div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useChatStore } from '../stores/chat';
import {
  PresentationChartBarIcon,
  ArrowDownTrayIcon,
  EyeIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline';

const chatStore = useChatStore();
const { presentationPreview, hasPresentation, isLoading } = storeToRefs(chatStore);

const selectedSlide = ref(null);

const getContentLines = (content) => {
  if (!content) return [];
  const lines = content.split('\n').filter(line => line.trim());
  return lines.slice(0, 3); // Show first 3 lines
};

const formatDate = (dateString) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const handleDownload = async () => {
  try {
    await chatStore.downloadPresentation();
  } catch (error) {
    console.error('Failed to download presentation:', error);
  }
};
</script>
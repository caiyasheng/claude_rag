<template>
  <div class="rag-platform">
    <iframe
      :src="ragUrl"
      class="rag-iframe"
      @load="iframeLoaded"
      ref="iframeRef"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'

const RAG_FRONTEND_URL = import.meta.env.VITE_RAG_URL || 'http://localhost:5175'

const ragUrl = ref(RAG_FRONTEND_URL)
const iframeRef = ref()

function iframeLoaded() {
  console.log('RAG iframe loaded')
}
</script>

<style scoped>
.rag-platform {
  height: calc(100vh - var(--topbar-h) - 48px);
  width: 100%;
}

.rag-iframe {
  width: 100%;
  height: 100%;
  border: none;
  background: var(--bg-primary);
  border-radius: var(--radius);
}
</style>

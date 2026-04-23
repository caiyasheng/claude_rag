<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <el-button @click="$router.push('/')" link>
          <el-icon><ArrowLeft /></el-icon> 返回问答
        </el-button>
        <h1 class="page-title">文档管理</h1>
        <p class="page-sub">查看和管理知识库中的所有文档</p>
      </div>
      <div class="header-right">
        <el-button @click="loadDocuments" :loading="loading">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </header>

    <!-- Stats -->
    <div class="stats-row">
      <div class="stat-card">
        <el-icon class="stat-icon"><Document /></el-icon>
        <div class="stat-info">
          <span class="stat-val">{{ documentsData.total_files || 0 }}</span>
          <span class="stat-label">文档总数</span>
        </div>
      </div>
      <div class="stat-card">
        <el-icon class="stat-icon"><Files /></el-icon>
        <div class="stat-info">
          <span class="stat-val">{{ documentsData.total_chunks || 0 }}</span>
          <span class="stat-label">索引块总数</span>
        </div>
      </div>
    </div>

    <!-- Document List -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">文档列表</span>
      </div>
      
      <div v-if="loading" class="loading-center">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>

      <div v-else-if="documentsData.total_files === 0" class="empty-state">
        <el-icon class="empty-icon"><FolderOpened /></el-icon>
        <p>知识库中还没有文档</p>
        <el-button type="primary" @click="$router.push('/')">去上传文档</el-button>
      </div>

      <div v-else class="documents-container">
        <div v-for="(chunks, filename) in documentsData.chunks_by_file" :key="filename" class="document-card">
          <div class="document-header" @click="toggleExpand(filename)">
            <div class="document-info">
              <el-icon class="doc-icon"><Document /></el-icon>
              <div>
                <div class="doc-name">{{ getFileName(filename) }}</div>
                <div class="doc-meta">
                  <span>{{ chunks.length }} 个索引块</span>
                  <span>•</span>
                  <span>{{ getTotalChars(chunks) }} 字符</span>
                </div>
              </div>
            </div>
            <el-icon class="expand-icon" :class="{ expanded: expandedFiles.includes(filename) }">
              <ArrowDown />
            </el-icon>
          </div>

          <div v-if="expandedFiles.includes(filename)" class="chunks-panel">
            <div class="chunks-list">
              <div v-for="(chunk, idx) in chunks" :key="chunk.id" class="chunk-item">
                <div class="chunk-header">
                  <el-tag size="small">块 {{ idx + 1 }}</el-tag>
                  <span v-if="chunk.metadata.page_number" class="chunk-meta">第 {{ chunk.metadata.page_number }} 页</span>
                </div>
                <div class="chunk-content">{{ chunk.content }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  ArrowLeft, Refresh, Document, Files, Loading, 
  FolderOpened, ArrowDown 
} from '@element-plus/icons-vue'
import { getAllChunks } from '../utils/api.js'

const loading = ref(false)
const documentsData = ref({})
const expandedFiles = ref([])

async function loadDocuments() {
  loading.value = true
  try {
    documentsData.value = await getAllChunks()
  } catch (e) {
    ElMessage.error('加载文档列表失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

function toggleExpand(filename) {
  const idx = expandedFiles.value.indexOf(filename)
  if (idx > -1) {
    expandedFiles.value.splice(idx, 1)
  } else {
    expandedFiles.value.push(filename)
  }
}

function getFileName(path) {
  if (!path) return '未知文件'
  const parts = path.split(/[/\\]/)
  const filename = parts[parts.length - 1]
  if (filename.match(/^[0-9a-f-]{36}\./i)) {
    const ext = filename.split('.').pop()
    return `文档_${filename.slice(0, 8)}.${ext}`
  }
  return filename
}

function getTotalChars(chunks) {
  return chunks.reduce((sum, c) => sum + (c.content?.length || 0), 0).toLocaleString()
}

onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
.page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
}
.page-sub {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}
.header-right {
  display: flex;
  gap: 10px;
}

/* Stats */
.stats-row {
  display: flex;
  gap: 16px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.stat-icon {
  font-size: 24px;
  color: var(--accent);
}
.stat-info {
  display: flex;
  flex-direction: column;
}
.stat-val {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}
.stat-label {
  font-size: 12px;
  color: var(--text-muted);
}

/* Card */
.card {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.card-header {
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-raised);
}
.card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.loading-center, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 12px;
  color: var(--text-muted);
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 8px;
}

.documents-container {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.document-card {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.document-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: var(--bg-raised);
  cursor: pointer;
  transition: background 0.2s;
}
.document-header:hover {
  background: var(--bg-hover);
}
.document-info {
  display: flex;
  align-items: center;
  gap: 12px;
}
.doc-icon {
  font-size: 24px;
  color: var(--accent);
}
.doc-name {
  font-weight: 500;
  color: var(--text-primary);
  font-size: 14px;
}
.doc-meta {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  gap: 8px;
  margin-top: 2px;
}
.expand-icon {
  color: var(--text-muted);
  transition: transform 0.2s;
}
.expand-icon.expanded {
  transform: rotate(180deg);
}

.chunks-panel {
  border-top: 1px solid var(--border);
  padding: 16px 20px;
  background: var(--bg-body);
}
.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.chunk-item {
  padding: 14px;
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
}
.chunk-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.chunk-meta {
  font-size: 12px;
  color: var(--text-muted);
}
.chunk-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}
</style>

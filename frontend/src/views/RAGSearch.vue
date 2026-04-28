<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <h1 class="page-title">RAG 文档检索</h1>
        <p class="page-sub">上传文档，基于知识库进行智能问答</p>
      </div>
      <div class="header-right">
        <el-button @click="$router.push('/eval')">
          <el-icon><DataAnalysis /></el-icon> RAG评测
        </el-button>
        <el-button @click="$router.push('/documents')">
          <el-icon><Document /></el-icon> 文档管理
        </el-button>
        <el-button @click="loadStats" :loading="statsLoading">
          <el-icon><Refresh /></el-icon> 刷新统计
        </el-button>
        <el-button type="danger" @click="handleReset" :loading="resetting">
          <el-icon><Delete /></el-icon> 重置索引
        </el-button>
      </div>
    </header>

    <!-- Stats -->
    <div class="stats-row">
      <div class="stat-card clickable" @click="$router.push('/documents')">
        <el-icon class="stat-icon"><Document /></el-icon>
        <div class="stat-info">
          <span class="stat-val">{{ stats.total_chunks || 0 }}</span>
          <span class="stat-label">索引块数（点击管理文档）</span>
        </div>
        <el-icon class="arrow-icon"><Right /></el-icon>
      </div>
    </div>

    <!-- Upload Area -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">文档上传</span>
      </div>
      <el-upload
        ref="uploadRef"
        class="upload-area"
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :file-list="fileList"
        multiple
        accept=".pdf,.docx,.txt,.md"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">
          <span>拖拽文件到此处，或 <em>点击上传</em></span>
          <span class="upload-tip">支持 PDF, DOCX, TXT, MD 文件</span>
        </div>
      </el-upload>
      <div class="upload-actions">
        <el-button type="primary" @click="handleUpload" :loading="uploading" :disabled="fileList.length === 0">
          <el-icon><Upload /></el-icon> 上传并索引
        </el-button>
        <el-button @click="clearFiles">清空</el-button>
      </div>
    </div>

    <!-- Search Area -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">智能问答</span>
      </div>
      <div class="search-box">
        <el-input
          v-model="question"
          placeholder="输入你的问题..."
          size="large"
          @keyup.enter="handleQuery"
        >
          <template #append>
            <el-button @click="handleQuery" :loading="querying" :disabled="!question.trim()">
              <el-icon><Search /></el-icon> 搜索
            </el-button>
          </template>
        </el-input>
      </div>

      <!-- Loading State -->
      <div v-if="querying" class="loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在检索和生成答案...</span>
      </div>

      <!-- Answer -->
      <div v-if="answer && !querying" class="answer-section">
        <div class="answer-header">
          <span class="answer-label">答案</span>
        </div>
        <div class="answer-content">{{ answer }}</div>

        <!-- Retrieved Docs -->
        <div v-if="retrievedDocs.length > 0" class="docs-section">
          <div class="docs-header">
            <span class="docs-label">参考文档</span>
            <span class="docs-count">{{ retrievedDocs.length }} 条</span>
          </div>
          <div v-for="(doc, idx) in retrievedDocs" :key="idx" class="doc-item">
            <div class="doc-source">{{ doc.source }}</div>
            <div class="doc-content">{{ doc.content }}...</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Upload, Search, Delete, Refresh, Document, Right, DataAnalysis } from '@element-plus/icons-vue'
import { uploadDocuments, getStats, queryRAG, resetIndex } from '../utils/api.js'

const uploadRef = ref()
const fileList = ref([])
const question = ref('')
const stats = ref({})
const statsLoading = ref(false)
const uploading = ref(false)
const querying = ref(false)
const resetting = ref(false)
const answer = ref('')
const retrievedDocs = ref([])

async function loadStats() {
  statsLoading.value = true
  try {
    stats.value = await getStats()
  } catch (e) {
    ElMessage.error('加载统计失败: ' + e.message)
  } finally {
    statsLoading.value = false
  }
}

function handleFileChange(file, files) {
  fileList.value = files
}

function clearFiles() {
  fileList.value = []
  uploadRef.value?.clearFiles()
}

async function handleUpload() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }
  uploading.value = true
  try {
    const files = fileList.value.map((f) => f.raw)
    const result = await uploadDocuments(files)
    ElMessage.success(`上传成功！已索引 ${result.chunks} 个文档块`)
    clearFiles()
    loadStats()
  } catch (e) {
    ElMessage.error('上传失败: ' + e.message)
  } finally {
    uploading.value = false
  }
}

async function handleQuery() {
  if (!question.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  querying.value = true
  answer.value = ''
  retrievedDocs.value = []
  try {
    const result = await queryRAG(question.value, 4, true)
    answer.value = result.answer
    retrievedDocs.value = result.docs || []
  } catch (e) {
    ElMessage.error('查询失败: ' + e.message)
  } finally {
    querying.value = false
  }
}

async function handleReset() {
  resetting.value = true
  try {
    await resetIndex()
    ElMessage.success('索引已重置')
    stats.value = {}
  } catch (e) {
    ElMessage.error('重置失败: ' + e.message)
  } finally {
    resetting.value = false
  }
}

// 初始化
loadStats()
</script>

<style scoped>
.page {
  max-width: 900px;
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
  align-items: flex-start;
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
.stat-card.clickable {
  cursor: pointer;
  transition: all 0.2s;
}
.stat-card.clickable:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.arrow-icon {
  color: var(--text-muted);
  margin-left: auto;
  font-size: 16px;
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

/* Upload */
.upload-area {
  padding: 32px;
}
.upload-icon {
  font-size: 40px;
  color: var(--text-muted);
  margin-bottom: 12px;
}
.upload-text {
  color: var(--text-secondary);
  font-size: 14px;
}
.upload-text em {
  color: var(--accent);
  font-style: normal;
}
.upload-tip {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}
.upload-actions {
  padding: 14px 18px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 10px;
}

/* Search */
.search-box {
  padding: 18px;
}
.answer-section {
  padding: 18px;
  border-top: 1px solid var(--border);
}
.loading-state {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px;
  color: var(--text-muted);
  font-size: 13px;
}
.answer-header {
  margin-bottom: 12px;
}
.answer-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.answer-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
}

/* Docs */
.docs-section {
  margin-top: 20px;
}
.docs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.docs-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.docs-count {
  font-size: 11px;
  color: var(--text-muted);
}
.doc-item {
  padding: 12px;
  background: var(--bg-raised);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
}
.doc-source {
  font-size: 11px;
  color: var(--accent);
  margin-bottom: 6px;
  font-family: monospace;
}
.doc-content {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}
</style>

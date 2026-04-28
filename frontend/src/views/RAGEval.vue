<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <el-button @click="$router.push('/')" link>
          <el-icon><ArrowLeft /></el-icon> 返回问答
        </el-button>
        <h1 class="page-title">RAG 评测</h1>
        <p class="page-sub">评测 RAG 系统的检索和生成质量</p>
      </div>
    </header>

    <!-- Stats -->
    <div class="stats-row">
      <div class="stat-card">
        <el-icon class="stat-icon"><Collection /></el-icon>
        <div class="stat-info">
          <span class="stat-val">{{ stats.total_chunks || 0 }}</span>
          <span class="stat-label">知识库块数</span>
        </div>
      </div>
      <div class="stat-card">
        <el-icon class="stat-icon"><Document /></el-icon>
        <div class="stat-info">
          <span class="stat-val">{{ stats.total_files || 0 }}</span>
          <span class="stat-label">文档数</span>
        </div>
      </div>
      <div class="stat-card">
        <el-icon class="stat-icon"><List /></el-icon>
        <div class="stat-info">
          <span class="stat-val">{{ stats.dataset_count || 0 }}</span>
          <span class="stat-label">测试集数量</span>
        </div>
      </div>
    </div>

    <!-- Dataset Card -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">测试集管理</span>
      </div>

      <div class="card-body">
        <div class="action-row">
          <el-button type="primary" :loading="generating" @click="handleGenerate">
            <el-icon><MagicStick /></el-icon>
            从知识库生成
          </el-button>
          <el-button @click="showUploadDialog = true">
            <el-icon><Upload /></el-icon>
            上传测试集
          </el-button>
          <span class="action-hint">支持 JSON 格式，包含 question 和 golden_answer 字段</span>
        </div>

        <div v-if="dataset.length > 0" class="dataset-preview">
          <div class="preview-header">
            <span class="preview-title">测试集预览（前5条）</span>
          </div>
          <div class="preview-list">
            <div v-for="(item, idx) in dataset.slice(0, 5)" :key="idx" class="preview-item">
              <div class="preview-q">{{ idx + 1 }}. {{ item.question }}</div>
              <div class="preview-a">标准答案: {{ item.golden_answer?.slice(0, 50) }}...</div>
            </div>
          </div>
        </div>

        <div v-else class="empty-hint">
          <el-icon><Warning /></el-icon>
          暂无测试集，请先生成或上传
        </div>
      </div>
    </div>

    <!-- Eval Control -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">评测控制</span>
      </div>

      <div class="card-body">
        <div class="action-row">
          <el-button type="success" :loading="evaluating" :disabled="dataset.length === 0" @click="handleRunEval">
            <el-icon><VideoPlay /></el-icon>
            开始评测
          </el-button>
          <el-input-number v-model="maxSamples" :min="1" :max="100" size="default" />
          <span class="action-hint">条数据（默认全部）</span>
        </div>
      </div>
    </div>

    <!-- Results -->
    <div v-if="evalResult" class="card">
      <div class="card-header">
        <span class="card-title">评测结果</span>
        <el-button v-if="evalResult.report_id" type="primary" size="small" link @click="openReport">
          📊 打开 HTML 报告
        </el-button>
        <el-tag type="success" v-if="evalResult.success">成功</el-tag>
        <el-tag type="danger" v-else>失败</el-tag>
      </div>

      <div class="card-body">
        <!-- Score Cards -->
        <div class="scores-row">
          <div class="score-card" :class="getScoreClass(evalResult.avg_scores?.faithfulness)">
            <div class="score-val">{{ formatScore(evalResult.avg_scores?.faithfulness) }}</div>
            <div class="score-label">Faithfulness</div>
            <div class="score-desc">答案忠诚度</div>
          </div>
          <div class="score-card" :class="getScoreClass(evalResult.avg_scores?.answer_relevancy)">
            <div class="score-val">{{ formatScore(evalResult.avg_scores?.answer_relevancy) }}</div>
            <div class="score-label">Answer Relevancy</div>
            <div class="score-desc">回答相关性</div>
          </div>
          <div class="score-card" :class="getScoreClass(evalResult.avg_scores?.context_precision)">
            <div class="score-val">{{ formatScore(evalResult.avg_scores?.context_precision) }}</div>
            <div class="score-label">Context Precision</div>
            <div class="score-desc">上下文精确度</div>
          </div>
          <div class="score-card" :class="getScoreClass(evalResult.avg_scores?.context_recall)">
            <div class="score-val">{{ formatScore(evalResult.avg_scores?.context_recall) }}</div>
            <div class="score-label">Context Recall</div>
            <div class="score-desc">上下文召回率</div>
          </div>
        </div>

        <!-- Summary -->
        <div class="summary-row">
          <div class="summary-item">
            <span class="summary-label">总计</span>
            <span class="summary-val">{{ evalResult.total }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">成功</span>
            <span class="summary-val success">{{ evalResult.success_count }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">失败</span>
            <span class="summary-val danger">{{ evalResult.failed_count }}</span>
          </div>
        </div>

        <!-- Issue Distribution -->
        <div v-if="Object.keys(evalResult.issue_distribution || {}).length > 0" class="issues-section">
          <div class="issues-title">问题分布</div>
          <div class="issues-tags">
            <el-tag v-for="(count, issue) in evalResult.issue_distribution" :key="issue" :type="getIssueTagType(issue)">
              {{ issue }}: {{ count }}
            </el-tag>
          </div>
        </div>

        <!-- Records Table -->
        <div class="records-section">
          <div class="records-title">评测明细</div>
          <el-table :data="evalResult.records" style="width: 100%" stripe>
            <el-table-column type="expand">
              <template #default="props">
                <div class="record-detail">
                  <div class="detail-item">
                    <span class="detail-label">问题:</span>
                    <span class="detail-val">{{ props.row.question }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">标准答案:</span>
                    <span class="detail-val">{{ props.row.golden_answer }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">模型回答:</span>
                    <span class="detail-val">{{ props.row.answer || '(无)' }}</span>
                  </div>
                  <div v-if="props.row.scores && Object.keys(props.row.scores).length > 0" class="detail-scores">
                    <el-tag size="small">Faithfulness: {{ props.row.scores.faithfulness?.toFixed(3) }}</el-tag>
                    <el-tag size="small">Relevancy: {{ props.row.scores.answer_relevancy?.toFixed(3) }}</el-tag>
                    <el-tag size="small">Precision: {{ props.row.scores.context_precision?.toFixed(3) }}</el-tag>
                    <el-tag size="small">Recall: {{ props.row.scores.context_recall?.toFixed(3) }}</el-tag>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="question" label="问题" width="400" show-overflow-tooltip />
            <el-table-column label="分数" width="200">
              <template #default="props">
                <template v-if="props.row.scores && Object.keys(props.row.scores).length > 0">
                  <span class="score-inline">
                    F: {{ props.row.scores.faithfulness?.toFixed(2) }}
                    R: {{ props.row.scores.answer_relevancy?.toFixed(2) }}
                  </span>
                </template>
                <el-tag v-else type="warning" size="small">无分数</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="问题诊断" width="150">
              <template #default="props">
                <el-tag v-for="issue in props.row.issues" :key="issue" :type="getIssueTagType(issue)" size="small">
                  {{ issue }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="延迟" width="80">
              <template #default="props">
                <span v-if="props.row.latency">{{ props.row.latency.toFixed(2) }}s</span>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>

    <!-- Upload Dialog -->
    <el-dialog v-model="showUploadDialog" title="上传测试集" width="500px">
      <el-upload
        ref="uploadRef"
        class="upload-demo"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".json"
        :on-change="handleFileChange"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件或点击上传 <em>JSON 格式</em></div>
        <template #tip>
          <div class="el-upload__tip">JSON 数组，每项包含 question 和 golden_answer 字段</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">上传</el-button>
      </template>
    </el-dialog>
  </div>

  <!-- ✅ 评测运行中固定提示，滚动不丢失 -->
  <div v-if="evaluating" class="eval-running-badge">
    <el-icon class="spinner"><Loading /></el-icon>
    评测正在后台运行中，请勿关闭页面...
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, Collection, Document, List, MagicStick, Upload,
  Warning, VideoPlay, UploadFilled
} from '@element-plus/icons-vue'
import {
  getEvalStats, generateDataset, uploadDataset, getDataset, runEvaluation
} from '../utils/api.js'

const stats = ref({})
const dataset = ref([])
const generating = ref(false)
const evaluating = ref(false)
const uploading = ref(false)
const maxSamples = ref(4)
const showUploadDialog = ref(false)
const uploadRef = ref(null)
const uploadFile = ref(null)
const evalResult = ref(null)

async function loadStats() {
  try {
    stats.value = await getEvalStats()
  } catch (e) {
    console.error('加载统计失败', e)
  }
}

async function loadDataset() {
  try {
    const res = await getDataset()
    dataset.value = res.samples || []
  } catch (e) {
    console.error('加载测试集失败', e)
  }
}

async function handleGenerate() {
  generating.value = true
  try {
    const res = await generateDataset(maxSamples.value)
    ElMessage.success(res.message)
    await loadDataset()
    await loadStats()
  } catch (e) {
    ElMessage.error('生成失败: ' + e.message)
  } finally {
    generating.value = false
  }
}

function handleFileChange(file) {
  uploadFile.value = file.raw
}

async function handleUpload() {
  if (!uploadFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  uploading.value = true
  try {
    const res = await uploadDataset(uploadFile.value)
    ElMessage.success(res.message)
    showUploadDialog.value = false
    uploadFile.value = null
    await loadDataset()
    await loadStats()
  } catch (e) {
    ElMessage.error('上传失败: ' + e.message)
  } finally {
    uploading.value = false
  }
}

async function handleRunEval() {
  evaluating.value = true
  evalResult.value = null

  // ✅ 防误关：评测运行中离开页面提示
  const unloadHandler = (e) => {
    e.preventDefault()
    e.returnValue = '评测正在运行中，确定要离开吗？'
    return '评测正在运行中，确定要离开吗？'
  }
  window.addEventListener('beforeunload', unloadHandler)

  try {
    evalResult.value = await runEvaluation(maxSamples.value)
    ElMessage.success('评测完成')
  } catch (e) {
    ElMessage.error('评测失败: ' + e.message)
  } finally {
    evaluating.value = false
    window.removeEventListener('beforeunload', unloadHandler)
  }
}

function getScoreClass(score) {
  if (score === undefined || score === null) return 'score-na'
  if (score >= 0.8) return 'score-good'
  if (score >= 0.6) return 'score-medium'
  return 'score-bad'
}

function formatScore(score) {
  if (score === undefined || score === null) return 'N/A'
  return score.toFixed(3)
}

function openReport() {
  window.open(`http://localhost:8002/eval/report/view/${evalResult.value.report_id}`, '_blank')
}

function getIssueTagType(issue) {
  switch (issue) {
    case 'retrieval': return 'danger'
    case 'hallucination': return 'warning'
    case 'relevance': return 'info'
    case 'ok': return 'success'
    default: return ''
  }
}

onMounted(() => {
  loadStats()
  loadDataset()
})
</script>

<style scoped>
.page {
  max-width: 1200px;
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
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-raised);
}
.card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.card-body {
  padding: 18px;
}

/* Action Row */
.action-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.action-hint {
  font-size: 12px;
  color: var(--text-muted);
}

/* Dataset Preview */
.dataset-preview {
  margin-top: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.preview-header {
  padding: 10px 14px;
  background: var(--bg-raised);
  border-bottom: 1px solid var(--border);
}
.preview-title {
  font-size: 12px;
  color: var(--text-muted);
}
.preview-list {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.preview-item {
  padding: 10px;
  background: var(--bg-raised);
  border-radius: var(--radius-sm);
}
.preview-q {
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.preview-a {
  font-size: 12px;
  color: var(--text-muted);
}

.empty-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  font-size: 13px;
  color: var(--text-muted);
}

/* Scores */
.scores-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.score-card {
  flex: 1;
  padding: 16px;
  border-radius: var(--radius);
  text-align: center;
  border: 1px solid var(--border);
}
.score-card.score-good {
  background: rgba(34, 197, 94, 0.1);
  border-color: #22c55e;
}
.score-card.score-medium {
  background: rgba(234, 179, 8, 0.1);
  border-color: #eab308;
}
.score-card.score-bad {
  background: rgba(239, 68, 68, 0.1);
  border-color: #ef4444;
}
.score-card.score-na {
  background: rgba(156, 163, 175, 0.1);
  border-color: #9ca3af;
}
.score-card.score-na .score-val {
  color: #9ca3af;
}
.score-val {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}
.score-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-top: 4px;
}
.score-desc {
  font-size: 11px;
  color: var(--text-muted);
}

/* Summary */
.summary-row {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
}
.summary-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.summary-label {
  font-size: 13px;
  color: var(--text-muted);
}
.summary-val {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.summary-val.success {
  color: #22c55e;
}
.summary-val.danger {
  color: #ef4444;
}

/* Issues */
.issues-section {
  margin-bottom: 20px;
}
.issues-title {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.issues-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* Records */
.records-section {
  margin-top: 16px;
}
.records-title {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.score-inline {
  font-size: 12px;
  color: var(--text-muted);
}

.record-detail {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.detail-item {
  display: flex;
  gap: 8px;
}
.detail-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  min-width: 70px;
}
.detail-val {
  font-size: 13px;
  color: var(--text-primary);
}
.detail-scores {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

/* ✅ 评测运行中悬浮提示 */
.eval-running-badge {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50px;
  font-weight: 500;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
}
.spinner {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>

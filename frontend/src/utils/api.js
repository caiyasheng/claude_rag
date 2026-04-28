/**
 * RAG Platform API Client
 */
import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002'

export const http = axios.create({
  baseURL: BASE_URL,
  timeout: 300_000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Unknown error'
    return Promise.reject(new Error(msg))
  }
)

/**
 * 上传文档
 * @param {File[]} files
 * @returns {Promise}
 */
export const uploadDocuments = (files) => {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  return http.post('/rag/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/**
 * 获取索引统计
 * @returns {Promise}
 */
export const getStats = () => http.get('/rag/documents/stats')

/**
 * RAG 问答
 * @param {string} question
 * @param {number} k
 * @param {boolean} returnDocs
 * @returns {Promise}
 */
export const queryRAG = (question, k = 4, returnDocs = true) =>
  http.post('/rag/query', { question, k, return_docs: returnDocs })

/**
 * 重置索引
 * @returns {Promise}
 */
export const resetIndex = () => http.delete('/rag/documents/reset')

/**
 * 获取所有索引块内容
 * @param {number} limit
 * @returns {Promise}
 */
export const getAllChunks = (limit = 1000) => http.get('/rag/documents/chunks', { params: { limit } })

/**
 * 按文档名称删除索引
 * @param {string} source - 文档名称
 * @returns {Promise}
 */
export const deleteDocument = (source) =>
  http.delete('/rag/documents/delete', { params: { source } })

// ============== 评测相关 ==============

/**
 * 获取评测统计
 */
export const getEvalStats = () => http.get('/eval/stats')

/**
 * 生成测试集
 * @param {number} maxSamples
 */
export const generateDataset = (maxSamples = 50) =>
  http.post('/eval/dataset/generate', null, { params: { max_samples: maxSamples } })

/**
 * 上传测试集
 * @param {File} file
 */
export const uploadDataset = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return http.post('/eval/dataset/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/**
 * 获取当前测试集
 */
export const getDataset = () => http.get('/eval/dataset')

/**
 * 运行评测
 * @param {number} maxSamples
 */
export const runEvaluation = (maxSamples) =>
  http.post('/eval/run', null, { params: { max_samples: maxSamples } })

/**
 * 获取报告列表
 */
export const getReports = () => http.get('/eval/reports')

/**
 * 获取报告内容
 * @param {'csv'|'json'} reportType
 */
export const getReport = (reportType) => http.get(`/eval/report/${reportType}`)

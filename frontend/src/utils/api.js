/**
 * RAG Platform API Client
 */
import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002'

export const http = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
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

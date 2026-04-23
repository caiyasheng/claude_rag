# RAG Platform

基于 `claude_rag` 核心功能构建的独立 RAG 检索平台，支持文档上传和智能问答。

---

## 快速启动

### 1. 启动后端 (端口 8002)

```bash
cd /Users/shengjia/PycharmProjects/claude_rag
conda activate claude_rag_env                   # 如有虚拟环境
cd backend
pip install -r requirements.txt              # 首次运行
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

### 2. 启动前端 (端口 5175)

```bash
cd /Users/shengjia/PycharmProjects/claude_rag/frontend
npm install                                   # 首次运行
npm run dev
```

访问 http://localhost:5175

### 3. 集成到 testplat

testplat 已配置 iframe 嵌入 RAG 平台。

```bash
cd /Users/shengjia/PycharmProjects/claude_testplat/frontend
npm run dev
```

访问 http://localhost:5173，侧边栏有 **RAG检索** 入口。

---

## 项目结构

```
claude_rag/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI 入口
│       ├── config.py            # 后端配置 (如端口、CORS)
│       ├── core/                # RAG 核心实现
│       │   ├── __init__.py      # 模块导出
│       │   ├── loader.py        # 文档加载
│       │   ├── chunker.py       # 文本分块
│       │   ├── embedding.py     # 向量嵌入
│       │   ├── vectorstore.py   # 向量存储
│       │   ├── retriever.py     # 检索器
│       │   ├── chain.py         # RAG 链
│       │   └── config.py        # RAG 业务配置
│       ├── services/
│       │   └── rag_service.py   # 服务封装层
│       └── api/
│           └── rag.py           # API 路由
├── frontend/                    # Vue3 前端 (端口 5175)
│   └── ...
└── README.md
```

**层级关系：**
- `core/` - 底层实现（文档加载、分块、嵌入、存储、检索、生成）
- `services/` - 封装层（统一初始化、调用管理）
- `api/` - 接口层（HTTP 路由）

## 环境要求

- Python 3.10+
- Node.js 18+

## 配置

创建 `backend/.env` 文件：

```env
# LLM 配置
LLM_PROVIDER=openai          # openai / deepseek / ollama
LLM_MODEL=gpt-3.5-turbo
OPENAI_API_KEY=your-api-key
LLM_BASE_URL=

# DeepSeek (如使用)
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat

# Ollama (如使用)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5

# Embedding 配置
EMBEDDING_PROVIDER=openai    # openai / huggingface
EMBEDDING_MODEL=BAAI/bge-small-zh

# 向量存储
VECTORSTORE_PATH=./vectorstore

# 分块配置
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# 检索配置
TOP_K=4
```

## API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/rag/query` | RAG 问答 |
| POST | `/rag/documents/upload` | 上传并索引文档 |
| GET | `/rag/documents/stats` | 获取索引统计 |
| DELETE | `/rag/documents/reset` | 重置索引 |
| GET | `/health` | 健康检查 |

### 问答示例

```bash
curl -X POST http://localhost:8002/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "你的问题", "k": 4, "return_docs": true}'
```

### 上传文档示例

```bash
curl -X POST http://localhost:8002/rag/documents/upload \
  -F "files=@/path/to/document.pdf"
```

## 端口说明

| 服务 | 端口 |
|------|------|
| RAG 后端 | 8002 |
| RAG 前端 | 5175 |
| testplat 前端 | 5173 |

## 目录说明

- `backend/app/core/` - RAG 核心实现（从根目录迁移）
- `vectorstore/` - ChromaDB 向量存储（自动创建）
- `uploads/` - 上传文档临时存储（自动创建）

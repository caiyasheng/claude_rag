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

---

## 🧪 RAG 评测系统 (RAGEval)

### 核心设计思路

**检索层 + 生成层分离评测** - 独立评估检索质量和生成质量，结果真实可信。

| 环节 | 说明 | 评测框架 |
|------|------|---------|
| ✅ **检索层评测** | 评测检索出的文档块质量 | DeepEval + 自研指标 |
| ✅ **生成层评测** | 评测 LLM 生成答案质量 | DeepEval |
| ✅ **测试集生成** | 自动生成三元组测试集 | RAGAS |

---

### 架构特性

| 特性 | 说明 |
|------|------|
| **分离评测** | 检索层和生成层独立评测，定位问题更精准 |
| **DeepEval 驱动** | 生成层使用 DeepEval 官方指标 |
| **RAGAS 测试集** | 支持 multi-hop、跨文档场景，三元组 (question + golden_context + golden_answer) |
| **完整异常防护** | 单条样本失败不影响整体，NaN/None 全链路过滤 |
| **永久历史存档** | 每次评测自动生成报告，永不覆盖 |
| **可视化报告** | Chart.js 图表 + 明细表格，一键分享 |

---

### 评测流水线

```
┌─────────────────────────────────────────────────────────────┐
│              RAG 评测流水线（检索层 + 生成层分离）            │
├─────────────────────────────────────────────────────────────┤
│  1. 测试集生成                                              │
│      └─ RAGAS 生成三元组 (question + golden_context + answer)│
│         golden_context 来自真实知识库（非生成），支持 multi-hop │
├─────────────────────────────────────────────────────────────┤
│  2. RAG 检索 + 生成                                         │
│      └─ 复用 rag_service → 真实检索 + 真实 LLM 生成         │
│         ✅ 和前端对话页面参数、代码、模型 100% 一致          │
├─────────────────────────────────────────────────────────────┤
│  3. 检索层评测（使用 RAGAS golden_context）                  │
│      ├─ HitRate@K        → 命中率                           │
│      ├─ Recall / Precision / F1                             │
│      └─ MAP@K / NDCG@K   → 排序质量                        │
│      ✅ 支持 multi-hop 多片段命中                           │
│      ⚠️ golden_context 来自测试集，不自行生成               │
├─────────────────────────────────────────────────────────────┤
│  4. 生成层评测 (DeepEval)                                   │
│      ├─ AnswerCorrectness   → 答案正确性                    │
│      ├─ Faithfulness       → 答案忠实度（幻觉检测）          │
│      ├─ AnswerRelevancy    → 回答相关性（答非所问检测）      │
│      ├─ ContextualPrecision → 检索精度                       │
│      └─ ContextualRecall   → 检索召回率                      │
├─────────────────────────────────────────────────────────────┤
│  5. 归因诊断                                                │
│      └─ 根据阈值自动标注：[检索质量低 / 召回不足 / 幻觉 / 答非所问] │
├─────────────────────────────────────────────────────────────┤
│  6. 自动生成报告                                            │
│      ├─ HTML 可视化报告（Chart.js 图表）                    │
│      ├─ CSV 明细表格                                        │
│      └─ JSON 统计摘要                                       │
└─────────────────────────────────────────────────────────────┘
```

---

### 模块结构

```
backend/app/rag_eval/
├── main.py                  # 评测引擎入口（分离评测流程）
├── api.py                   # API 路由
├── config.py                # 评测配置
├── schemas.py               # 数据模型
│
├── dataset/                 # 测试集管理
│   ├── ragas_generator.py   # RAGAS 测试集生成（三元组）
│   └── loader.py            # JSON 数据集导入导出
│
├── pipeline/
│   └── runner.py            # RAG 调用封装（复用 rag_service）
│
├── evaluator/
│   ├── deep_eval.py         # DeepEval 生成层评测
│   └── retrieval_eval.py    # 检索层评测（基于 RAGAS golden_context）
│
├── analyzer/
│   └── diagnose.py          # 归因诊断
│
└── report/
    └── generator.py         # HTML/CSV/JSON 三格式报告生成
```

---

### 核心最佳实践

#### ✅ 1. DeepEval 生成层评测（通义千问优先）

```python
# deep_eval.py - 通义千问优先，自动复用 Embedding Key
_setup_deepeval_openai_env()  # 自动配置 OPENAI_API_KEY/OpenAI_BASE_URL
```

#### ✅ 2. 检索层多跳支持

```python
# retrieval_eval.py - multi-hop 多片段命中
_is_similar(chunk1, chunk2)  # 词汇重叠 + 语义相似度组合判断
# hit_rate_at_k = 任何一个片段被命中即算命中
# recall = 命中的片段数 / 总片段数
```

#### ✅ 3. 报告永久存档

每次评测自动生成 3 个文件，时间戳命名永不覆盖：
```
data/eval/reports/
├── eval_20260503_143022.html    # 带图表的可视化报告
├── eval_20260503_143022.csv     # 明细表格
└── eval_20260503_143022.json    # 统计摘要
```

在线查看：`http://localhost:8002/eval/report/view/{report_id}`

---

### API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/eval/dataset/generate?max_samples=50` | 生成测试集（RAGAS） |
| POST | `/eval/run?max_samples=10&k=4` | 运行分离评测 |
| GET  | `/eval/reports` | 历史报告列表 |
| GET  | `/eval/report/view/{report_id}` | 在线查看 HTML 报告 |
| GET  | `/eval/stats` | 评测统计概览 |
| GET  | `/eval/dataset` | 获取当前测试集 |

---

### 前端使用说明

访问 http://localhost:5175/#/rageval

1. **生成测试集** → 使用 RAGAS 自动生成三元组测试集（支持 multi-hop）
2. **运行评测** → 检索层（HitRate@K 等）+ 生成层（DeepEval 5项指标）
3. **查看报告** → 点击「📊 打开 HTML 报告」查看可视化结果

💡 **评测运行中不要刷新页面**：顶部永久悬浮提示 + 浏览器关闭确认双重保护

"""
RAG系统配置
"""
import os
from dotenv import load_dotenv

# 基于当前文件路径计算绝对路径基准
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv()

# LLM通用配置
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "minimax")
LLM_MODEL = os.getenv("LLM_MODEL", "minimax-m2.7")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")

# MiniMax配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_API_URL = os.getenv("MINIMAX_API_URL", "https://api.minimax.chat/v1")

# 通义千问配置（专门用于 RAGAS 评测，兼容性 100%）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL = "qwen-max-1201"

# ✅ RAGAS 评测专用 LLM （推荐 qwen，零失败）
RAG_EVAL_LLM = os.getenv("RAG_EVAL_LLM", "qwen")

# DeepSeek配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Ollama配置
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5")

# Embedding配置
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "custom")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# 向量存储路径
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", os.path.join(BASE_DIR, "vectorstore"))

# 分块配置
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# 检索配置
TOP_K = int(os.getenv("TOP_K", "4"))

# 上传文件目录
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))

# 确保目录存在
os.makedirs(VECTORSTORE_PATH, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

import sys
config = sys.modules[__name__]

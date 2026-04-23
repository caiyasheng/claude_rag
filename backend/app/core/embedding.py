"""
嵌入模型模块 - 支持OpenAI, HuggingFace等多种嵌入模型
"""
from typing import List, Optional, Union
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    HuggingFaceEmbeddings = None

from config import config
import logging
import time

logger = logging.getLogger(__name__)


class EmbeddingConfig:
    """嵌入配置"""

    def __init__(
        self,
        provider: str = None,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        **kwargs,
    ):
        self.provider = provider or config.EMBEDDING_PROVIDER
        self.model = model or config.EMBEDDING_MODEL
        self.api_key = api_key
        self.base_url = base_url
        logger.info(f"[嵌入配置] provider={self.provider}, model={self.model}")


def get_embedding_model(
    provider: str = None,
    model: str = None,
    api_key: str = None,
    base_url: str = None,
    **kwargs,
) -> Embeddings:
    provider = provider or config.EMBEDDING_PROVIDER
    logger.info(f"[嵌入模型] 创建嵌入模型: provider={provider}, model={model or config.EMBEDDING_MODEL}")
    print(f"🔗 [嵌入模型] 使用 {provider.upper()} 提供者, 模型: {model or config.EMBEDDING_MODEL}")

    if provider == "openai":
        api_key = api_key or config.LLM_API_KEY
        base_url = base_url or config.LLM_BASE_URL

        return OpenAIEmbeddings(
            model=model or "text-embedding-3-small",
            api_key=api_key,
            base_url=base_url if base_url else None,
            timeout=120,
            max_retries=5,
            **kwargs,
        )

    elif provider == "huggingface":
        if HuggingFaceEmbeddings is None:
            raise ImportError("langchain-huggingface 未安装，请运行: pip install langchain-huggingface")
        return HuggingFaceEmbeddings(
            model_name=model or config.EMBEDDING_MODEL,
            **kwargs,
        )

    elif provider == "custom":
        print(f"⚙️  [嵌入模型] DashScope 兼容模式, 分批大小=5, 超时=120s")
        return OpenAIEmbeddings(
            model=model or config.EMBEDDING_MODEL,
            api_key=api_key or config.EMBEDDING_API_KEY,
            base_url=base_url or config.EMBEDDING_BASE_URL,
            embedding_ctx_length=4096,
            chunk_size=5,
            check_embedding_ctx_length=False,
            timeout=120,
            max_retries=5,
            **kwargs,
        )

    else:
        raise ValueError(f"不支持的嵌入提供者: {provider}")


class BGEEmbeddings(Embeddings):
    """BGE中文嵌入模型"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh",
        encode_kwargs: dict = None,
        query_instruction: str = "为这个句子生成表示以用于检索相关文章：",
        document_instruction: str = "",
    ):
        if HuggingFaceEmbeddings is None:
            raise ImportError("langchain-huggingface 未安装，请运行: pip install langchain-huggingface")
        encode_kwargs = encode_kwargs or {"normalize_embeddings": True}
        self._hf = HuggingFaceEmbeddings(
            model_name=model_name,
            encode_kwargs=encode_kwargs,
            query_instruction=query_instruction,
            document_instruction=document_instruction,
        )

    def embed_query(self, text: str) -> List[float]:
        return self._hf.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._hf.embed_documents(texts)


class MultiProviderEmbeddings:
    """多提供者嵌入模型，支持回退"""

    def __init__(
        self,
        providers: List[tuple] = None,
    ):
        """
        初始化多提供者嵌入

        Args:
            providers: [(provider, model, api_key, base_url), ...]
        """
        self.providers = providers or [
            ("openai", "text-embedding-3-small", None, None),
            ("huggingface", "BAAI/bge-small-zh", None, None),
        ]
        self._embeddings = None
        self._current_idx = 0

    def _init_current(self):
        """初始化当前提供者"""
        if self._current_idx < len(self.providers):
            provider, model, api_key, base_url = self.providers[self._current_idx]
            try:
                self._embeddings = get_embedding_model(
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                )
                # 测试连接
                self._embeddings.embed_query("test")
            except Exception as e:
                print(f"提供者 {provider} 初始化失败: {e}")
                self._current_idx += 1
                self._init_current()

    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        if not self._embeddings:
            self._init_current()
        return self._embeddings.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入多个文档"""
        if not self._embeddings:
            self._init_current()
        return self._embeddings.embed_documents(texts)


def create_embeddings(
    provider: str = None,
    model: str = None,
    **kwargs,
) -> Embeddings:
    provider = provider or config.EMBEDDING_PROVIDER

    if provider == "bge":
        logger.info(f"[嵌入模型] 创建 BGE 嵌入模型")
        print(f"🇨🇳 [嵌入模型] 使用 BGE 中文嵌入模型")
        return BGEEmbeddings(model_name=model or "BAAI/bge-small-zh", **kwargs)

    base_embeddings = get_embedding_model(provider=provider, model=model, **kwargs)
    return LoggedEmbeddings(base_embeddings)


class LoggedEmbeddings(Embeddings):
    """带日志的嵌入包装器"""

    def __init__(self, base_embeddings: Embeddings):
        self.base_embeddings = base_embeddings

    def embed_query(self, text: str) -> List[float]:
        start = time.time()
        logger.info(f"[嵌入模型] 开始嵌入查询: {text[:50]}...")
        result = self.base_embeddings.embed_query(text)
        elapsed = time.time() - start
        logger.info(f"[嵌入模型] 查询嵌入完成，维度={len(result)}，耗时={elapsed:.2f}s")
        print(f"⌛ [嵌入] 查询向量化完成，耗时 {elapsed:.2f}s，维度 {len(result)}")
        return result

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        start = time.time()
        total_chars = sum(len(t) for t in texts)
        logger.info(f"[嵌入模型] 开始嵌入 {len(texts)} 个文档块，总计 {total_chars} 字符")
        print(f"🔢 [嵌入] 开始向量化 {len(texts)} 个文档块 ({total_chars} 字符)...")
        result = self.base_embeddings.embed_documents(texts)
        elapsed = time.time() - start
        logger.info(f"[嵌入模型] 文档嵌入完成，数量={len(result)}，耗时={elapsed:.2f}s，速度={len(result)/elapsed:.1f} 块/秒")
        print(f"✅ [嵌入] 向量化完成！{len(result)} 个向量，耗时 {elapsed:.2f}s ({len(result)/elapsed:.1f} 块/秒)")
        return result


if __name__ == "__main__":
    # 测试
    emb = create_embeddings(provider="huggingface", model="BAAI/bge-small-zh")
    vec = emb.embed_query("你好世界")
    print(f"嵌入维度: {len(vec)}")

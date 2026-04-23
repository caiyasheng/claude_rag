"""
检索模块 - 支持多种检索策略
"""
from typing import List, Optional, Union, Callable
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore

try:
    from langchain.retrievers import EnsembleRetriever, MergerRetriever
    from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
    from langchain.retrievers.document_compressors import (
        DocumentCompressorPipeline,
        EmbeddingsFilter,
    )
except (ImportError, ModuleNotFoundError):
    from langchain_classic.retrievers import EnsembleRetriever, MergerRetriever
    from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
    from langchain_classic.retrievers.document_compressors import (
        DocumentCompressorPipeline,
        EmbeddingsFilter,
    )

try:
    from langchain_cohere import CohereRerank
except ImportError:
    CohereRerank = None

from config import config
import logging

logger = logging.getLogger(__name__)


class CompressionRetriever(ContextualCompressionRetriever):
    """压缩检索器 - 使用LLM压缩检索结果"""

    def __init__(
        self,
        vectorstore: VectorStore,
        compressors: List = None,
        search_kwargs: dict = None,
        **kwargs,
    ):
        base_compressor = DocumentCompressorPipeline(
            transformers=compressors or [
                EmbeddingsFilter(embeddings=kwargs.get("embeddings")),
            ]
        )
        base_retriever = vectorstore.as_retriever(
            search_kwargs=search_kwargs or {"k": config.TOP_K}
        )
        super().__init__(
            base_compressor=base_compressor,
            base_retriever=base_retriever,
        )


class EnsembleRetrieverWrapper(EnsembleRetriever):
    """集成检索器 - 结合多种检索结果"""

    def __init__(
        self,
        retrievers: List[BaseRetriever],
        weights: List[float] = None,
    ):
        """
        初始化集成检索器

        Args:
            retrievers: 检索器列表
            weights: 权重列表
        """
        weights = weights or [1.0] * len(retrievers)
        super().__init__(retrievers=retrievers, weights=weights)


class KeywordRetriever(BaseRetriever):
    """关键词检索器（BM25）"""

    def __init__(
        self,
        documents: List[Document] = None,
        k: int = 10,
        **kwargs,
    ):
        from langchain_community.retrievers import BM25Retriever
        import rank_bm25

        self.documents = documents or []
        self.k = k
        self._retriever = None

    def _get_relevant_documents(self, query: str) -> List[Document]:
        if not self._retriever:
            texts = [doc.page_content for doc in self.documents]
            self._retriever = BM25Retriever.from_texts(
                texts, k=self.k
            )
        return self._retriever.get_relevant_documents(query)


def create_retriever(
    vectorstore: VectorStore,
    retriever_type: str = "similarity",
    search_kwargs: dict = None,
    **kwargs,
) -> BaseRetriever:
    search_kwargs = search_kwargs or {"k": config.TOP_K}
    logger.info(f"[检索器] 创建检索器: type={retriever_type}, k={search_kwargs.get('k')}")
    print(f"🔎 [检索器] 创建 {retriever_type.upper()} 检索器，Top K = {search_kwargs.get('k')}")

    if retriever_type == "similarity":
        return vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs=search_kwargs
        )

    elif retriever_type == "mmr":
        return vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs=search_kwargs
        )

    elif retriever_type == "compression":
        return CompressionRetriever(
            vectorstore=vectorstore,
            search_kwargs=search_kwargs,
            **kwargs,
        )

    elif retriever_type == "ensemble":
        retrievers = kwargs.get("retrievers", [])
        weights = kwargs.get("weights")
        return EnsembleRetrieverWrapper(retrievers=retrievers, weights=weights)

    else:
        raise ValueError(f"未知的检索器类型: {retriever_type}")


def get_retriever_with_rerank(
    vectorstore: VectorStore,
    reranker_model: str = None,
    top_n: int = 10,
    **kwargs,
) -> BaseRetriever:
    """
    创建带重排序的检索器

    Args:
        vectorstore: 向量存储
        reranker_model: 重排序模型
        top_n: 返回前N个
        **kwargs: 其他参数

    Returns:
        带重排序的检索器
    """
    from langchain_community.retrievers import ContextualCompressionRetriever

    if CohereRerank is None:
        raise ImportError("langchain-cohere 未安装，请运行: pip install langchain-cohere")

    compressor = CohereRerank(
        model=reranker_model or "rerank-multilingual-v2.0",
        top_n=top_n,
    )

    base_retriever = vectorstore.as_retriever(
        search_kwargs={"k": top_n * 2}  # 多检索一些再重排
    )

    return ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=base_retriever,
    )


if __name__ == "__main__":
    print("Retriever模块已就绪")

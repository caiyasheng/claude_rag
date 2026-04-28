"""
向量存储模块 - 支持Chroma, Milvus等向量数据库
"""
from typing import List, Optional, Union, Callable
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_chroma import Chroma

try:
    from langchain_milvus import Milvus
except ImportError:
    Milvus = None

from langchain_core.embeddings import Embeddings
from config import config
import os
import shutil
import logging
import time

try:
    from langchain_community.vectorstores.utils import filter_complex_metadata
except ImportError:
    def filter_complex_metadata(documents: List[Document]) -> List[Document]:
        filtered = []
        for doc in documents:
            simple_meta = {}
            for k, v in doc.metadata.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    simple_meta[k] = v
            filtered.append(Document(page_content=doc.page_content, metadata=simple_meta))
        return filtered

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """向量存储管理器"""

    def __init__(
        self,
        provider: str = "chroma",
        embeddings: Embeddings = None,
        persist_directory: str = None,
        collection_name: str = "rag_documents",
        **kwargs,
    ):
        self.provider = provider.lower()
        self.embeddings = embeddings
        self.persist_directory = persist_directory or config.VECTORSTORE_PATH
        self.collection_name = collection_name
        self.kwargs = kwargs
        self._vectorstore = None
        logger.info(f"[向量存储] 初始化: provider={provider}, persist_dir={self.persist_directory}")
        print(f"💾 [向量存储] 初始化 {provider.upper()}, 路径: {self.persist_directory}")

    def _create_chroma(
        self,
        embeddings: Embeddings,
        persist_directory: str,
        collection_name: str,
    ) -> Chroma:
        """创建Chroma向量存储"""
        return Chroma(
            embedding_function=embeddings,
            persist_directory=persist_directory,
            collection_name=collection_name,
        )

    def _create_milvus(
        self,
        embeddings: Embeddings,
        collection_name: str,
        **kwargs,
    ):
        if Milvus is None:
            raise ImportError("langchain-milvus 未安装，请运行: pip install langchain-milvus")
        return Milvus(
            embedding_function=embeddings,
            collection_name=collection_name,
            connection_args={
                "uri": kwargs.get("milvus_uri", "./milvus.db"),
            },
            consistency_zone=kwargs.get("consistency_zone", "langchain"),
        )

    def get_vectorstore(self) -> VectorStore:
        """获取或创建向量存储"""
        if self._vectorstore is None:
            if self.provider == "chroma":
                self._vectorstore = self._create_chroma(
                    embeddings=self.embeddings,
                    persist_directory=self.persist_directory,
                    collection_name=self.collection_name,
                )
            elif self.provider == "milvus":
                self._vectorstore = self._create_milvus(
                    embeddings=self.embeddings,
                    collection_name=self.collection_name,
                    **self.kwargs,
                )
            else:
                raise ValueError(f"不支持的向量存储提供者: {self.provider}")

        return self._vectorstore

    def add_documents(
        self,
        documents: List[Document],
        **kwargs,
    ) -> List[str]:
        start = time.time()
        vs = self.get_vectorstore()
        logger.info(f"[向量存储] 开始添加 {len(documents)} 个文档")
        print(f"📥 [向量存储] 开始存储 {len(documents)} 个文档块...")

        logger.info(f"[向量存储] 过滤复杂元数据...")
        documents = filter_complex_metadata(documents)
        print(f"🧹 [向量存储] 已过滤复杂元数据")

        try:
            ids = vs.add_documents(documents, **kwargs)
            elapsed = time.time() - start
            logger.info(f"[向量存储] 添加文档完成: {len(ids)} 个, 耗时 {elapsed:.2f}s")
            print(f"✅ [向量存储] 存储完成！{len(ids)} 个向量已保存，耗时 {elapsed:.2f}s")
            return ids
        except Exception as e:
            elapsed = time.time() - start
            error_msg = f"[向量存储] 添加文档失败: {type(e).__name__}: {str(e)[:200]}"
            logger.error(error_msg, exc_info=True)
            print(f"❌ [向量存储] 错误 ({elapsed:.2f}s): {type(e).__name__}")
            print(f"   提示: 请检查网络连接或 API Key，已自动重试 5 次")
            if "Connection" in str(e) or "timeout" in str(e).lower():
                print(f"   → 这是网络问题，请:")
                print(f"     1. 检查网络是否稳定")
                print(f"     2. 或切换到本地 embedding 模型 (huggingface)")
            raise

    def search(
        self,
        query: str,
        k: int = None,
        filter: dict = None,
        **kwargs,
    ) -> List[Document]:
        start = time.time()
        vs = self.get_vectorstore()
        k = k or config.TOP_K
        logger.info(f"[向量存储] 开始检索: {query[:50]}..., k={k}")
        print(f"🔍 [检索] 开始搜索: {query[:50]}...")
        results = vs.similarity_search(query, k=k, filter=filter, **kwargs)
        elapsed = time.time() - start
        total_chars = sum(len(doc.page_content) for doc in results)
        logger.info(f"[向量存储] 检索完成: {len(results)} 个结果, 耗时 {elapsed:.2f}s")
        print(f"🎯 [检索] 找到 {len(results)} 个相关片段，总字符 {total_chars}，耗时 {elapsed:.2f}s")
        return results

    def search_with_score(
        self,
        query: str,
        k: int = None,
        filter: dict = None,
        **kwargs,
    ) -> List[tuple]:
        """
        搜索相似文档并返回分数

        Args:
            query: 查询字符串
            k: 返回数量
            filter: 过滤条件
            **kwargs: 其他参数

        Returns:
            (Document, score)元组列表
        """
        vs = self.get_vectorstore()
        k = k or config.TOP_K
        return vs.similarity_search_with_score(query, k=k, filter=filter, **kwargs)

    def as_retriever(self, **kwargs):
        """转换为检索器"""
        vs = self.get_vectorstore()
        return vs.as_retriever(**kwargs)

    def delete(self, **kwargs):
        """删除向量存储"""
        vs = self.get_vectorstore()
        vs.delete(**kwargs)

    def delete_by_source(self, source: str) -> int:
        """按文档名称(source)删除对应所有索引块

        Args:
            source: 文档名称

        Returns:
            删除的块数量
        """
        vs = self.get_vectorstore()

        if self.provider == "chroma":
            collection = vs._collection
            result = collection.get(where={"source": source})
            ids_to_delete = result.get("ids", [])

            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"[向量存储] 已删除文档 '{source}' 的 {len(ids_to_delete)} 个索引块")
                print(f"🗑️  [删除] 已删除文档 '{source}' 的 {len(ids_to_delete)} 个索引块")
                return len(ids_to_delete)
            else:
                logger.info(f"[向量存储] 未找到文档 '{source}' 的索引块")
                print(f"ℹ️  [删除] 未找到文档 '{source}' 的索引块")
                return 0
        else:
            raise NotImplementedError(f"按 source 删除暂不支持 {self.provider} 提供者")

    def clear(self):
        """清空向量存储"""
        if self.provider == "chroma" and os.path.exists(self.persist_directory):
            shutil.rmtree(self.persist_directory)
            self._vectorstore = None

    @classmethod
    def from_documents(
        cls,
        documents: List[Document],
        embeddings: Embeddings,
        provider: str = "chroma",
        **kwargs,
    ) -> "VectorStoreManager":
        """
        从文档创建向量存储

        Args:
            documents: Document列表
            embeddings: 嵌入模型
            provider: 向量存储提供者
            **kwargs: 其他参数

        Returns:
            VectorStoreManager实例
        """
        manager = cls(provider=provider, embeddings=embeddings, **kwargs)
        documents = filter_complex_metadata(documents)
        manager.add_documents(documents)
        return manager


# 便捷函数
def create_vectorstore(
    provider: str = "chroma",
    embeddings: Embeddings = None,
    documents: List[Document] = None,
    persist_directory: str = None,
    collection_name: str = "rag_documents",
    **kwargs,
) -> VectorStoreManager:
    logger.info(f"[向量存储] 创建管理器: provider={provider}, collection={collection_name}")
    print(f"🗄️  [向量存储] 创建 {provider.upper()} 管理器，集合: {collection_name}")
    manager = VectorStoreManager(
        provider=provider,
        embeddings=embeddings,
        persist_directory=persist_directory,
        collection_name=collection_name,
        **kwargs,
    )

    if documents:
        logger.info(f"[向量存储] 初始化时添加 {len(documents)} 个文档")
        documents = filter_complex_metadata(documents)
        manager.add_documents(documents)

    return manager


if __name__ == "__main__":
    from langchain_core.documents import Document
    from embedding import create_embeddings

    # 测试
    emb = create_embeddings(provider="huggingface", model="BAAI/bge-small-zh")

    docs = [
        Document(page_content="人工智能是计算机科学的一个分支", metadata={"source": "test"}),
        Document(page_content="机器学习是人工智能的子领域", metadata={"source": "test"}),
    ]

    vs = create_vectorstore(
        provider="chroma",
        embeddings=emb,
        documents=docs,
        persist_directory="./test_vectorstore",
    )

    results = vs.search("人工智能", k=2)
    print(f"搜索结果: {len(results)} 个")

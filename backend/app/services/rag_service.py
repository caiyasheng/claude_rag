"""
RAG Service - 封装层
核心逻辑在 app.core 模块
"""
from typing import List, Optional, Union

from app.core import (
    DocumentLoader,
    load_documents,
    chunk_documents,
    create_embeddings,
    VectorStoreManager,
    create_vectorstore,
    create_retriever,
    RAGChain,
    create_rag_chain,
    config,
)


class RAGService:
    """RAG服务封装"""

    def __init__(self):
        self.vectorstore_manager: Optional[VectorStoreManager] = None
        self.chain: Optional[RAGChain] = None
        self.embeddings = None
        self._init_system()

    def _init_system(self):
        """初始化系统"""
        self.embeddings = create_embeddings(provider=config.EMBEDDING_PROVIDER)
        self.vectorstore_manager = VectorStoreManager(
            provider="chroma",
            embeddings=self.embeddings,
            persist_directory=config.VECTORSTORE_PATH,
            collection_name="rag_documents",
        )

    def index_documents(self, source: Union[str, List[str]], source_type: str = "file") -> int:
        """索引文档

        Args:
            source: 文件路径或路径列表
            source_type: 源类型

        Returns:
            索引的文档块数量
        """
        documents = load_documents(source, source_type=source_type)

        chunks = chunk_documents(
            documents,
            strategy="recursive",
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
        )

        vs = self.vectorstore_manager
        vs.add_documents(chunks)

        return len(chunks)

    def query(self, question: str, k: int = None, return_docs: bool = False) -> Union[str, tuple]:
        """查询

        Args:
            question: 问题
            k: 返回文档数
            return_docs: 是否返回文档

        Returns:
            答案，或 (答案, 文档列表)
        """
        k = k or config.TOP_K

        vs = self.vectorstore_manager
        retriever = create_retriever(
            vectorstore=vs.get_vectorstore(),
            retriever_type="similarity",
            search_kwargs={"k": k},
        )

        if self.chain is None:
            self.chain = create_rag_chain(
                retriever=retriever,
                llm_type=config.LLM_PROVIDER,
            )

        answer = self.chain.invoke(question)

        if return_docs:
            docs = self.chain.get_relevant_documents(question)
            return answer, docs
        return answer

    def get_indexed_files(self) -> dict:
        """获取已索引的文件列表"""
        try:
            vs = self.vectorstore_manager.get_vectorstore()
            collection = vs._collection
            count = collection.count()
            return {"total_chunks": count}
        except Exception as e:
            return {"total_chunks": 0, "error": str(e)}

    def get_all_chunks(self, limit: int = 1000) -> dict:
        """获取所有索引块内容（按文档分组）"""
        try:
            vs = self.vectorstore_manager.get_vectorstore()
            collection = vs._collection
            data = collection.get(limit=limit)
            
            # 处理空索引库情况
            if not data or not data.get("ids") or len(data["ids"]) == 0:
                return {
                    "total_chunks": 0,
                    "total_files": 0,
                    "chunks_by_file": {}
                }
            
            chunks_by_file = {}
            
            for i, doc_id in enumerate(data["ids"]):
                documents = data.get("documents", [])
                metadatas = data.get("metadatas", [])
                
                content = documents[i] if i < len(documents) else ""
                metadata = metadatas[i] if i < len(metadatas) else {}
                source = metadata.get("source", "unknown") if metadata else "unknown"
                
                if source not in chunks_by_file:
                    chunks_by_file[source] = []
                
                chunks_by_file[source].append({
                    "id": doc_id,
                    "content": content,
                    "metadata": metadata or {}
                })
            
            return {
                "total_chunks": len(data["ids"]),
                "total_files": len(chunks_by_file),
                "chunks_by_file": chunks_by_file
            }
        except Exception as e:
            return {"total_chunks": 0, "total_files": 0, "chunks_by_file": {}, "error": str(e)}

    def reset_index(self):
        """重置索引"""
        if self.vectorstore_manager:
            self.vectorstore_manager.clear()
        self.chain = None


# 全局单例
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service

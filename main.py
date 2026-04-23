"""
RAG系统主程序
整合文档加载、分块、嵌入、存储、检索和生成
"""
import os
import argparse
from typing import List, Optional, Union
from pathlib import Path

from langchain_core.documents import Document

from loader import DocumentLoader, load_documents
from chunker import RecursiveChunker, chunk_documents
from embedding import create_embeddings, BGEEmbeddings
from vectorstore import VectorStoreManager, create_vectorstore
from retriever import create_retriever, get_retriever_with_rerank
from chain import RAGChain, create_rag_chain
import config


class RAGSystem:
    """完整的RAG系统"""

    def __init__(
        self,
        vectorstore_provider: str = "chroma",
        embedding_provider: str = None,
        llm_provider: str = None,
        chunking_strategy: str = "recursive",
        chunk_size: int = None,
        chunk_overlap: int = None,
        persist_directory: str = None,
        collection_name: str = "rag_documents",
    ):
        """
        初始化RAG系统

        Args:
            vectorstore_provider: 向量存储提供者
            embedding_provider: 嵌入提供者
            llm_provider: LLM提供者
            chunking_strategy: 分块策略
            chunk_size: 块大小
            chunk_overlap: 块重叠
            persist_directory: 持久化目录
            collection_name: 集合名称
        """
        self.vectorstore_provider = vectorstore_provider
        self.embedding_provider = embedding_provider or config.EMBEDDING_PROVIDER
        self.llm_provider = llm_provider or config.LLM_PROVIDER
        self.chunking_strategy = chunking_strategy
        self.chunk_size = chunk_size or config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or config.CHUNK_OVERLAP
        self.persist_directory = persist_directory or config.VECTORSTORE_PATH
        self.collection_name = collection_name

        self.loader = DocumentLoader()
        self.embeddings = None
        self.vectorstore_manager = None
        self.chain = None

    def _init_embeddings(self):
        """初始化嵌入模型"""
        if self.embeddings is None:
            self.embeddings = create_embeddings(provider=self.embedding_provider)
        return self.embeddings

    def _init_vectorstore(self):
        """初始化向量存储"""
        if self.vectorstore_manager is None:
            self._init_embeddings()
            self.vectorstore_manager = VectorStoreManager(
                provider=self.vectorstore_provider,
                embeddings=self.embeddings,
                persist_directory=self.persist_directory,
                collection_name=self.collection_name,
            )
        return self.vectorstore_manager

    def load_and_index(
        self,
        source: Union[str, List[str]],
        source_type: str = "auto",
        chunking_strategy: str = None,
        verbose: bool = True,
    ) -> int:
        """
        加载文档并索引

        Args:
            source: 文件路径、URL或路径列表
            source_type: 源类型，"file", "web", "auto"
            chunking_strategy: 分块策略，覆盖初始化设置
            verbose: 是否输出详细信息

        Returns:
            索引的文档块数量
        """
        chunking_strategy = chunking_strategy or self.chunking_strategy

        if verbose:
            print(f"正在加载文档: {source}")

        # 1. 加载文档
        documents = load_documents(source, source_type=source_type)

        if verbose:
            print(f"加载了 {len(documents)} 个文档块")

        # 2. 分块
        if verbose:
            print(f"正在分块 (策略: {chunking_strategy})...")

        chunks = chunk_documents(
            documents,
            strategy=chunking_strategy,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        if verbose:
            print(f"分块完成: {len(chunks)} 个块")

        # 3. 索引
        if verbose:
            print("正在索引到向量存储...")

        vs = self._init_vectorstore()
        vs.add_documents(chunks)

        if verbose:
            print(f"索引完成! 向量存储: {self.persist_directory}")

        return len(chunks)

    def query(
        self,
        question: str,
        k: int = None,
        retriever_type: str = "similarity",
        use_rerank: bool = False,
        return_docs: bool = False,
        verbose: bool = False,
    ) -> Union[str, tuple]:
        """
        查询RAG系统

        Args:
            question: 问题
            k: 返回的文档数量
            retriever_type: 检索器类型
            use_rerank: 是否使用重排序
            return_docs: 是否返回相关文档
            verbose: 是否输出调试信息

        Returns:
            如果return_docs为True，返回(答案, 文档列表)；否则只返回答案
        """
        # 确保向量存储已初始化
        vs = self._init_vectorstore()

        # 创建检索器
        search_kwargs = {"k": k or config.TOP_K}

        if use_rerank:
            retriever = get_retriever_with_rerank(
                vectorstore=vs.get_vectorstore(),
                top_n=k or config.TOP_K,
            )
        else:
            retriever = create_retriever(
                vectorstore=vs.get_vectorstore(),
                retriever_type=retriever_type,
                search_kwargs=search_kwargs,
            )

        # 创建RAG链
        if self.chain is None:
            self.chain = create_rag_chain(
                retriever=retriever,
                llm_type=self.llm_provider,
            )

        # 更新检索器
        self.chain.retriever = retriever

        if verbose:
            docs = retriever.get_relevant_documents(question)
            print(f"检索到 {len(docs)} 个相关文档")
            for i, doc in enumerate(docs):
                print(f"\n--- 文档 {i+1} ---")
                print(doc.page_content[:200] + "...")

        # 查询
        answer = self.chain.invoke(question)

        if return_docs:
            docs = self.chain.get_relevant_documents(question)
            return answer, docs

        return answer

    def reset(self):
        """重置向量存储"""
        if self.vectorstore_manager:
            self.vectorstore_manager.clear()
        self.vectorstore_manager = None
        self.chain = None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="RAG系统")
    parser.add_argument("--source", "-s", help="文档路径或URL")
    parser.add_argument("--query", "-q", help="查询问题")
    parser.add_argument("--chunk-size", "-c", type=int, default=1000, help="块大小")
    parser.add_argument("--overlap", "-o", type=int, default=200, help="块重叠")
    parser.add_argument("--top-k", "-k", type=int, default=4, help="返回文档数")
    parser.add_argument("--reset", "-r", action="store_true", help="重置向量存储")
    parser.add_argument("--embedding", "-e", default="huggingface", help="嵌入提供者")
    parser.add_argument("--llm", "-l", default="openai", help="LLM提供者")
    parser.add_argument("--rerank", action="store_true", help="使用重排序")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 创建RAG系统
    rag = RAGSystem(
        embedding_provider=args.embedding,
        llm_provider=args.llm,
        chunk_size=args.chunk_size,
        chunk_overlap=args.overlap,
    )

    if args.reset:
        print("重置向量存储...")
        rag.reset()
        print("完成!")
        return

    if args.source:
        # 加载并索引文档
        rag.load_and_index(args.source, verbose=True)

    if args.query:
        # 查询
        answer = rag.query(
            args.query,
            k=args.top_k,
            use_rerank=args.rerank,
            verbose=args.verbose,
        )
        print(f"\n答案:\n{answer}")

    if not args.source and not args.query:
        parser.print_help()


if __name__ == "__main__":
    main()

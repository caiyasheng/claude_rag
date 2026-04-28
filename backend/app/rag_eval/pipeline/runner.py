"""
RAG Runner - T2
封装RAG调用，复用现有RAGService
"""
import time
from typing import Optional
from app.rag_eval.schemas import RagResult
from app.services.rag_service import get_rag_service


def run_rag(question: str, k: int = None) -> RagResult:
    """运行RAG获取答案

    Args:
        question: 问题
        k: 检索数量

    Returns:
        RagResult
    """
    rag_service = get_rag_service()

    start_time = time.time()

    try:
        # 调用现有RAGService查询
        answer, docs = rag_service.query(question, k=k, return_docs=True)

        elapsed = time.time() - start_time

        # 提取文档内容
        retrieved_chunks = [doc.page_content if hasattr(doc, 'page_content') else str(doc) for doc in docs]

        return RagResult(
            answer=answer,
            retrieved_chunks=retrieved_chunks,
            final_context="\n\n".join(retrieved_chunks),
            latency=elapsed,
            token_count=0,  # 暂不计算token
        )

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"RAG执行失败: {e}")
        return RagResult(
            answer="",
            retrieved_chunks=[],
            final_context="",
            latency=elapsed,
            token_count=0,
        )


def run_rag_with_context(question: str, golden_context: list[str], k: int = None) -> RagResult:
    """使用给定的golden_context运行RAG（用于测试）

    Args:
        question: 问题
        golden_context: 标准上下文
        k: 检索数量

    Returns:
        RagResult
    """
    # 直接使用golden_context作为检索结果（模拟检索）
    return RagResult(
        answer="",
        retrieved_chunks=golden_context,
        final_context="\n\n".join(golden_context),
        latency=0.0,
        token_count=0,
    )

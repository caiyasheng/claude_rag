"""
检索层评测模块
基于 RAGAS 生成的 golden_context 计算 HitRate@k, Recall, Precision, F1, MAP@k, NDCG@k
支持 multi-hop、跨文档场景
"""
import os
import json
from typing import List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

from app.rag_eval.schemas import EvalRecord, EvalSample
from app.rag_eval.config import eval_config


@dataclass
class RetrievalMetrics:
    """检索层评测指标"""
    hit_rate_at_k: float = 0.0
    recall: float = 0.0
    precision: float = 0.0
    f1: float = 0.0
    map_at_k: float = 0.0
    ndcg_at_k: float = 0.0


class RetrievalEvaluator:
    """检索层评测器"""

    def __init__(self, k: int = 4):
        self.k = k

    def calculate_retrieval_metrics(
        self,
        retrieved_chunks: List[str],
        golden_context: List[str],
        k: int = None,
    ) -> RetrievalMetrics:
        """计算检索层指标

        Args:
            retrieved_chunks: 检索到的文档块列表
            golden_context: 标准上下文列表（RAGAS 生成，来自真实知识库）
            k: Top-K

        Returns:
            RetrievalMetrics
        """
        k = k or self.k

        if not retrieved_chunks or not golden_context:
            return RetrievalMetrics()

        retrieved_chunks = retrieved_chunks[:k]
        golden_context = golden_context[:k] if golden_context else []

        # 计算 Hit@K（retrieved 中有多少在 golden 中）
        # multi-hop 场景：任何一个片段匹配即算命中
        hits = sum(1 for chunk in retrieved_chunks if any(self._is_similar(chunk, gc) for gc in golden_context))
        hit_rate_at_k = hits / k if k > 0 else 0

        # 计算 Recall（命中的片段数 / 总片段数）
        recall = hits / len(golden_context) if golden_context else 0

        # 计算 Precision
        precision = hits / k if k > 0 else 0

        # 计算 F1
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        # 计算 MAP@K
        map_score = self._calculate_map_at_k(retrieved_chunks, golden_context, k)

        # 计算 NDCG@K
        ndcg_score = self._calculate_ndcg_at_k(retrieved_chunks, golden_context, k)

        return RetrievalMetrics(
            hit_rate_at_k=hit_rate_at_k,
            recall=recall,
            precision=precision,
            f1=f1,
            map_at_k=map_score,
            ndcg_at_k=ndcg_score,
        )

    def _is_similar(self, chunk1: str, chunk2: str) -> bool:
        """判断两个 chunk 是否相似（用于跨文档多跳场景）

        多跳场景：golden_context 来自多个不同文档，只要有一个片段匹配即可
        使用简单的词汇重叠 + 语义相似度组合判断
        """
        words1 = set(chunk1.lower().split())
        words2 = set(chunk2.lower().split())

        if not words1 or not words2:
            return False

        # 词汇重叠率
        overlap = len(words1 & words2)
        overlap_ratio = overlap / min(len(words1), len(words2)) if min(len(words1), len(words2)) > 0 else 0

        # 重叠词数量阈值
        if overlap >= 3 and overlap_ratio >= 0.2:
            return True

        # 长文本额外检查：包含关键实体/术语
        if len(words1) > 20 and len(words2) > 20:
            # 取最重要的词（排除停用词）
            stopwords = {"的", "是", "在", "了", "和", "有", "我", "这", "个", "与", "或", "等", "及", "为", "以", "于", "上", "下", "中", "可", "能", "会"}
            key1 = words1 - stopwords
            key2 = words2 - stopwords
            if key1 and key2:
                key_overlap = len(key1 & key2)
                if key_overlap >= 2:
                    return True

        return False

    def _calculate_map_at_k(
        self,
        retrieved_chunks: List[str],
        golden_context: List[str],
        k: int,
    ) -> float:
        """计算 Mean Average Precision@K"""
        if not retrieved_chunks or not golden_context:
            return 0.0

        precisions = []
        num_hits = 0

        for i, chunk in enumerate(retrieved_chunks[:k]):
            if any(self._is_similar(chunk, gc) for gc in golden_context):
                num_hits += 1
                precisions.append(num_hits / (i + 1))

        if not precisions:
            return 0.0

        return sum(precisions) / min(len(golden_context), k)

    def _calculate_ndcg_at_k(
        self,
        retrieved_chunks: List[str],
        golden_context: List[str],
        k: int,
    ) -> float:
        """计算 NDCG@K"""
        if not retrieved_chunks or not golden_context:
            return 0.0

        # 计算 DCG
        dcg = 0.0
        for i, chunk in enumerate(retrieved_chunks[:k]):
            if any(self._is_similar(chunk, gc) for gc in golden_context):
                dcg += 1.0 / np.log2(i + 2)  # i+2 因为从1开始

        # 计算 IDCG（理想情况下的 DCG）
        ideal_hits = min(len(golden_context), k)
        idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_hits))

        return dcg / idcg if idcg > 0 else 0.0

    def evaluate_records(
        self,
        records: List[EvalRecord],
    ) -> List[EvalRecord]:
        """对记录列表进行检索层评测

        Args:
            records: EvalRecord 列表（RAGAS 生成的测试集包含 golden_context）

        Returns:
            更新后的记录列表（包含 retrieval_metrics）
        """
        valid_records = [r for r in records if r.is_success() and r.result]
        if not valid_records:
            return records

        print(f"🔍 检索层评测开始，共 {len(valid_records)} 条")

        for record in valid_records:
            try:
                # 获取检索到的 chunks
                retrieved_chunks = record.result.retrieved_chunks or []
                if not retrieved_chunks:
                    record.metadata["retrieval_metrics"] = RetrievalMetrics()
                    continue

                # 使用 RAGAS 生成的 golden_context（来自真实知识库）
                golden_context = record.sample.golden_context

                if golden_context:
                    metrics = self.calculate_retrieval_metrics(
                        retrieved_chunks,
                        golden_context,
                        k=self.k,
                    )
                    record.metadata["retrieval_metrics"] = metrics
                else:
                    # 没有 golden_context 时无法计算检索层指标
                    record.metadata["retrieval_metrics"] = RetrievalMetrics()

            except Exception as e:
                print(f"⚠️ 检索层评测失败: {e}")
                record.metadata["retrieval_metrics"] = RetrievalMetrics()

        print(f"✅ 检索层评测完成！")
        return records


# 全局实例
_retrieval_evaluator: Optional[RetrievalEvaluator] = None


def get_retrieval_evaluator(k: int = 4) -> RetrievalEvaluator:
    global _retrieval_evaluator
    if _retrieval_evaluator is None:
        _retrieval_evaluator = RetrievalEvaluator(k=k)
    return _retrieval_evaluator
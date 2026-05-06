"""
DeepEval 评测模块 - 生成层评估
使用 DeepEval 的 AnswerCorrectness, Faithfulness, AnswerRelevancy 等指标
✅ 通义千问优先，自动复用 Embedding Key，降级到 Minimax 兼容模式
✅ 延迟导入，不使用评测功能时服务可正常启动
"""
import os
import json
from typing import List, Optional
from dataclasses import dataclass, field

os.environ["DEEPEVAL_API_KEY"] = os.getenv("DEEPEVAL_API_KEY", "")

from app.rag_eval.schemas import EvalRecord
from config import config, EMBEDDING_API_KEY, EMBEDDING_BASE_URL, QWEN_MODEL


def _setup_deepeval_openai_env():
    """✅ 配置 DeepEval 的 OpenAI 兼容环境，通义千问优先，自动复用 Embedding Key"""

    DASHSCOPE_API_KEY = EMBEDDING_API_KEY
    DASHSCOPE_API_URL = EMBEDDING_BASE_URL

    if DASHSCOPE_API_KEY and len(DASHSCOPE_API_KEY.strip()) > 20:
        os.environ["OPENAI_API_KEY"] = DASHSCOPE_API_KEY
        os.environ["OPENAI_BASE_URL"] = DASHSCOPE_API_URL
        model = QWEN_MODEL
        print("✅ DeepEval 评测引擎: 通义千问 (自动复用 Embedding Key)")
        print(f"   - model = {QWEN_MODEL}")
        print(f"   - base_url = {DASHSCOPE_API_URL}")
    else:
        os.environ["OPENAI_API_KEY"] = config.MINIMAX_API_KEY
        os.environ["OPENAI_BASE_URL"] = config.MINIMAX_API_URL
        model = config.LLM_MODEL
        print("⚠️ DeepEval 评测引擎: Minimax (兼容模式)")
        print(f"   - model = {model}")
        print(f"   - base_url = {config.MINIMAX_API_URL}")

    return model


class DeepEvalEvaluator:
    """DeepEval 生成层评测器"""

    def __init__(self):
        model = _setup_deepeval_openai_env()

        from deepeval.metrics import (
            AnswerCorrectnessMetric,
            FaithfulnessMetric,
            AnswerRelevancyMetric,
            ContextualPrecisionMetric,
            ContextualRecallMetric,
        )

        self.answer_correctness = AnswerCorrectnessMetric(
            threshold=0.5,
            model=model,
            include_reason=True,
        )
        self.faithfulness = FaithfulnessMetric(
            threshold=0.5,
            model=model,
        )
        self.answer_relevancy = AnswerRelevancyMetric(
            threshold=0.5,
            model=model,
        )
        self.contextual_precision = ContextualPrecisionMetric(
            threshold=0.5,
            model=model,
        )
        self.contextual_recall = ContextualRecallMetric(
            threshold=0.5,
            model=model,
        )

    def evaluate(self, records: List[EvalRecord]) -> List[EvalRecord]:
        """对记录列表进行生成层评测

        Args:
            records: EvalRecord 列表

        Returns:
            更新后的记录列表（包含 scores）
        """
        from deepeval import evaluate as deepeval_evaluate, EvaluationDataset, TestCase

        valid_records = [r for r in records if r.is_success() and r.result]
        if not valid_records:
            return records

        print(f"🧪 DeepEval 开始生成层评测，共 {len(valid_records)} 条")

        # 构建测试用例
        test_cases = []
        for record in valid_records:
            retrieved_context = record.result.retrieved_chunks or []
            context_str = "\n\n".join(retrieved_context) if retrieved_context else ""

            test_case = TestCase(
                input=record.sample.question,
                actual_output=record.result.answer,
                expected_output=record.sample.golden_answer,
                retrieval_context=[retrieved_context] if retrieved_context else [],
            )
            test_cases.append(test_case)

        # 创建数据集
        dataset = EvaluationDataset(test_cases=test_cases)

        # 运行评测
        try:
            results = deepeval_evaluate(
                dataset,
                metrics=[
                    self.answer_correctness,
                    self.faithfulness,
                    self.answer_relevancy,
                    self.contextual_precision,
                    self.contextual_recall,
                ],
                show_progress=True,
            )

            # 解析结果
            for i, record in enumerate(valid_records):
                try:
                    test_result = results[i]
                    metrics = test_result.metrics

                    record.scores = {
                        "answer_correctness": self._get_metric_value(metrics, "answer_correctness"),
                        "faithfulness": self._get_metric_value(metrics, "faithfulness"),
                        "answer_relevancy": self._get_metric_value(metrics, "answer_relevancy"),
                        "contextual_precision": self._get_metric_value(metrics, "contextual_precision"),
                        "contextual_recall": self._get_metric_value(metrics, "contextual_recall"),
                    }

                    # 同时保留 RAGAS 兼容字段名
                    if "faithfulness" in record.scores:
                        record.scores["faithfulness_ragas"] = record.scores["faithfulness"]

                except Exception as e:
                    print(f"⚠️ 第 {i} 条评分失败: {e}")
                    record.scores = record.scores or {}

            print(f"✅ DeepEval 生成层评测完成！")

        except Exception as e:
            print(f"❌ DeepEval 评测失败: {e}")
            import traceback
            traceback.print_exc()

        return records

    def _get_metric_value(self, metrics: dict, key: str):
        """安全提取指标值"""
        try:
            metric = metrics.get(key)
            if metric is None:
                return None
            # DeepEval 返回的是 MetricResult 对象
            if hasattr(metric, "score"):
                return float(metric.score)
            if hasattr(metric, "value"):
                return float(metric.value)
            if isinstance(metric, (int, float)):
                return float(metric)
            return None
        except (ValueError, TypeError):
            return None


# 全局实例
_deepEval_evaluator: Optional[DeepEvalEvaluator] = None


def get_deepEval_evaluator() -> DeepEvalEvaluator:
    global _deepEval_evaluator
    if _deepEval_evaluator is None:
        _deepEval_evaluator = DeepEvalEvaluator()
    return _deepEval_evaluator
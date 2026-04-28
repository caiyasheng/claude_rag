"""
多标签归因 - T5
根据评测分数诊断问题类型
"""
from typing import List
from app.rag_eval.config import eval_config


def diagnose(scores: dict) -> List[str]:
    """根据分数诊断问题

    Args:
        scores: 评测分数 dict，包含 faithfulness, answer_relevancy, context_recall 等

    Returns:
        问题标签列表，如 ["retrieval", "hallucination"] 或 ["ok"]
    """
    issues = []

    if not scores:
        return ["评分失败"]

    def _safe(v):
        return v if v is not None and v == v else 0

    context_recall = _safe(scores.get("context_recall"))
    faithfulness = _safe(scores.get("faithfulness"))
    answer_relevancy = _safe(scores.get("answer_relevancy"))

    # retrieval 问题
    if context_recall < eval_config.CONTEXT_RECALL_THRESHOLD:
        issues.append("召回不足")

    # hallucination 问题
    if faithfulness < eval_config.FAITHFULNESS_THRESHOLD:
        issues.append("幻觉")

    # relevance 问题
    if answer_relevancy < eval_config.ANSWER_RELEVANCY_THRESHOLD:
        issues.append("答非所问")

    return issues or ["正常"]

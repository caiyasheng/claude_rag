"""
评测配置 - T8
"""
import os
from dataclasses import dataclass


@dataclass
class EvalConfig:
    """评测配置"""
    # 评测模型（用于RAGAS评判）
    EVAL_LLM_PROVIDER: str = "minimax"  # 默认minimax，可配置为openai等
    EVAL_LLM_MODEL: str = "minimax-m2.7"

    # 数据集配置
    MAX_SAMPLES: int = 100  # 最多评测样本数
    DATASET_DIR: str = os.path.join(os.path.dirname(__file__), "data")

    # 评测阈值
    CONTEXT_RECALL_THRESHOLD: float = 0.6
    FAITHFULNESS_THRESHOLD: float = 0.7
    ANSWER_RELEVANCY_THRESHOLD: float = 0.7

    # 是否启用各指标
    ENABLE_FAITHFULNESS: bool = True
    ENABLE_ANSWER_RELEVANCY: bool = True
    ENABLE_CONTEXT_PRECISION: bool = True
    ENABLE_CONTEXT_RECALL: bool = True


# 全局配置实例
eval_config = EvalConfig()

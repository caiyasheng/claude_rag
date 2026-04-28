"""
数据集加载器 - T1
支持JSON加载和字段校验
"""
import json
import os
from typing import List, Optional
from app.rag_eval.schemas import EvalSample


def load_dataset_from_json(file_path: str) -> List[EvalSample]:
    """从JSON文件加载测试集

    Args:
        file_path: JSON文件路径

    Returns:
        EvalSample列表

    Raises:
        ValueError: 文件不存在或字段缺失
    """
    if not os.path.exists(file_path):
        raise ValueError(f"Dataset file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Dataset must be a JSON array")

    samples = []
    for i, item in enumerate(data):
        # 校验必要字段
        required_fields = ["question", "golden_answer"]
        for field in required_fields:
            if field not in item:
                raise ValueError(f"Item {i} missing required field: {field}")

        sample = EvalSample(
            id=item.get("id", f"sample_{i}"),
            question=item["question"],
            golden_answer=item["golden_answer"],
            golden_context=item.get("golden_context", []),
            metadata=item.get("metadata", {}),
        )
        samples.append(sample)

    return samples


def save_dataset_to_json(samples: List[EvalSample], file_path: str) -> None:
    """保存测试集到JSON文件

    Args:
        samples: EvalSample列表
        file_path: 保存路径
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    data = [
        {
            "id": s.id,
            "question": s.question,
            "golden_answer": s.golden_answer,
            "golden_context": s.golden_context,
            "metadata": s.metadata,
        }
        for s in samples
    ]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def validate_sample(item: dict) -> bool:
    """校验单条数据字段完整性

    Args:
        item: 原始数据字典

    Returns:
        是否通过校验
    """
    required_fields = ["question", "golden_answer"]
    return all(field in item for field in required_fields)

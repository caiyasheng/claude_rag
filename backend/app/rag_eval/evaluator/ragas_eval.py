"""
RAGAS评测 - Minimax 终极适配版
4 个指标全开，失败就是失败，不造假
"""
from typing import List
import os
os.environ["RAGAS_DO_NOT_TRACK"] = "true"
from app.rag_eval.schemas import EvalRecord


def evaluate_with_ragas(records: List[EvalRecord]) -> List[EvalRecord]:
    """✅ 通义千问原生支持，零兼容问题"""

    from .qwen_adapter import get_llm_for_ragas
    eval_llm, run_config = get_llm_for_ragas()

    try:
        from datasets import Dataset
        from ragas.evaluation import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )

        valid_records = [r for r in records if r.is_success()]
        if not valid_records:
            return records

        print(f"🧪 RAGAS 开始评测，共 {len(valid_records)} 条")

        data = {
            "question": [r.sample.question for r in valid_records],
            "answer": [r.result.answer for r in valid_records],
            "contexts": [r.result.retrieved_chunks for r in valid_records],
            "ground_truth": [r.sample.golden_answer for r in valid_records],
        }

        dataset = Dataset.from_dict(data)

        result = evaluate(
            dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            ],
            llm=eval_llm,
            run_config=run_config,
            raise_exceptions=False,
            show_progress=True,
        )

        scores_df = result.to_pandas()

        for i, record in enumerate(valid_records):
            try:
                if i < len(scores_df):
                    row = scores_df.iloc[i]
                    record.scores = {
                        "faithfulness": _safe_float(row.get("faithfulness")),
                        "answer_relevancy": _safe_float(row.get("answer_relevancy")),
                        "context_precision": _safe_float(row.get("context_precision")),
                        "context_recall": _safe_float(row.get("context_recall")),
                    }
            except Exception as e:
                print(f"⚠️ 第 {i} 条评分失败，跳过: {e}")
                record.scores = {}

        scored = sum(1 for r in valid_records if r.scores and any(v is not None for v in r.scores.values()))
        print(f"✅ RAGAS 评测完成！成功评分: {scored}/{len(valid_records)}")

    except ImportError as e:
        print(f"❌ RAGAS 库未安装: {e}")
    except Exception as e:
        print(f"❌ RAGAS 评测失败: {e}")
        import traceback
        traceback.print_exc()

    return records


def _safe_float(val) -> float:
    """安全提取分数，None 或 NaN 返回 None"""
    if val is None:
        return None
    try:
        f = float(val)
        return f if f == f else None
    except (ValueError, TypeError):
        return None

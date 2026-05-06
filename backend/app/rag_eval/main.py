"""
评测主流程 - 检索层 + 生成层分离评测
使用 DeepEval 框架
"""
import os
import json
import concurrent.futures
from functools import partial
from typing import List, Optional
from app.rag_eval.schemas import EvalSample, EvalRecord, RagResult
from app.rag_eval.pipeline.runner import run_rag
from app.rag_eval.evaluator.deep_eval import get_deepEval_evaluator
from app.rag_eval.evaluator.retrieval_eval import get_retrieval_evaluator, RetrievalMetrics
from app.rag_eval.report.generator import generate_csv_report, generate_json_summary, generate_html_report
from app.rag_eval.dataset.loader import load_dataset_from_json, save_dataset_to_json
from app.rag_eval.config import eval_config

MAX_PARALLEL = 3


class EvalEngine:
    """评测引擎 - 统筹整个评测流程（检索层 + 生成层分离）"""

    def __init__(self, dataset_path: str = None, k: int = 4):
        self.dataset_path = dataset_path
        self.k = k
        self.records: List[EvalRecord] = []
        self.current_index = 0
        self.total_count = 0

    def load_dataset(self, dataset_path: str = None) -> List[EvalSample]:
        """加载测试集"""
        path = dataset_path or self.dataset_path
        if not path:
            raise ValueError("No dataset path provided")
        return load_dataset_from_json(path)

    def run_evaluation(
        self,
        samples: List[EvalSample],
        max_samples: int = None,
        progress_callback=None,
    ) -> List[EvalRecord]:
        """运行 RAG 检索 + 生成

        Args:
            samples: 测试样本列表
            max_samples: 最大评测数量
            progress_callback: 进度回调 (current, total, record)

        Returns:
            EvalRecord列表
        """
        max_samples = max_samples or len(samples)
        samples = samples[:max_samples]

        self.records = []
        self.current_index = 0
        self.total_count = len(samples)

        print(f"开始 RAG 检索+生成，共 {len(samples)} 条数据，并发度: {MAX_PARALLEL}")

        def evaluate_one(sample, idx):
            try:
                result = run_rag(sample.question, k=self.k)
                record = EvalRecord(
                    sample=sample,
                    result=result,
                    scores=None,
                    issues=[],
                    metadata={"latency": result.latency}
                )
                print(f"[{idx}/{len(samples)}] 完成: {sample.question[:30]}...")
                return idx, record
            except Exception as e:
                print(f"[{idx}/{len(samples)}] 失败: {e}")
                record = EvalRecord(
                    sample=sample,
                    result=None,
                    scores=None,
                    issues=["error"],
                    metadata={"error": str(e)}
                )
                return idx, record

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
            futures = [executor.submit(partial(evaluate_one, s, i+1)) for i, s in enumerate(samples)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        results.sort(key=lambda x: x[0])
        self.records = [r[1] for r in results]
        self.current_index = len(samples)
        self.total_count = len(samples)

        for i, record in enumerate(self.records):
            if progress_callback:
                progress_callback(i + 1, len(samples), record)

        print(f"RAG 执行完成，成功: {sum(1 for r in self.records if r.is_success())}, 失败: {sum(1 for r in self.records if not r.is_success())}")
        return self.records

    def run_retrieval_evaluation(
        self,
        records: List[EvalRecord] = None,
    ) -> List[EvalRecord]:
        """执行检索层评测

        Args:
            records: 记录列表，默认使用 self.records

        Returns:
            更新后的记录列表
        """
        records = records or self.records
        if not records:
            return []

        print("🔍 开始检索层评测...")
        evaluator = get_retrieval_evaluator(k=self.k)

        try:
            records = evaluator.evaluate_records(records)
            print("✅ 检索层评测完成")
        except Exception as e:
            print(f"❌ 检索层评测失败: {e}")
            import traceback
            traceback.print_exc()

        return records

    def run_generation_evaluation(self, records: List[EvalRecord] = None) -> List[EvalRecord]:
        """执行生成层评测（DeepEval）

        Args:
            records: 记录列表，默认使用 self.records

        Returns:
            更新后的记录列表
        """
        records = records or self.records
        if not records:
            return []

        print("📝 开始生成层评测（DeepEval）...")
        evaluator = get_deepEval_evaluator()

        try:
            records = evaluator.evaluate(records)
            print("✅ 生成层评测完成")
        except Exception as e:
            print(f"❌ 生成层评测失败: {e}")
            import traceback
            traceback.print_exc()

        return records

    def diagnose_all(self, records: List[EvalRecord] = None) -> List[EvalRecord]:
        """对所有记录进行归因诊断（检索+生成综合）"""
        records = records or self.records

        for record in records:
            issues = []

            # 检查检索层指标
            if "retrieval_metrics" in record.metadata:
                rm = record.metadata["retrieval_metrics"]
                if rm and isinstance(rm, RetrievalMetrics):
                    if rm.hit_rate_at_k < 0.5:
                        issues.append("检索质量低")
                    if rm.recall < 0.5:
                        issues.append("召回不足")

            # 检查生成层指标
            if record.scores:
                try:
                    answer_correctness = record.scores.get("answer_correctness")
                    faithfulness = record.scores.get("faithfulness")
                    answer_relevancy = record.scores.get("answer_relevancy")

                    if answer_correctness is not None and answer_correctness < 0.5:
                        issues.append("答案错误")
                    if faithfulness is not None and faithfulness < 0.5:
                        issues.append("幻觉")
                    if answer_relevancy is not None and answer_relevancy < 0.5:
                        issues.append("答非所问")
                except Exception as e:
                    print(f"⚠️ 归因诊断失败: {e}")

            record.issues = issues or ["正常"]

        return records

    def generate_reports(self, records: List[EvalRecord] = None, output_dir: str = None) -> dict:
        """生成报告（检索层 + 生成层）"""
        from datetime import datetime

        records = records or self.records
        output_dir = output_dir or os.path.join(eval_config.DATASET_DIR, "reports")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(output_dir, f"eval_{timestamp}.csv")
        json_path = os.path.join(output_dir, f"eval_{timestamp}.json")
        html_path = os.path.join(output_dir, f"eval_{timestamp}.html")

        generate_csv_report(records, csv_path)
        generate_json_summary(records, json_path)
        generate_html_report(records, html_path)

        return {
            "id": timestamp,
            "name": f"评测报告_{timestamp}",
            "csv_path": csv_path,
            "json_path": json_path,
            "html_path": html_path,
            "total": len(records),
            "success": sum(1 for r in records if r.is_success()),
            "failed": sum(1 for r in records if not r.is_success()),
            "created_at": datetime.now().isoformat(),
        }

    def run_full_pipeline(
        self,
        dataset_path: str = None,
        max_samples: int = None,
        run_retrieval: bool = True,
        run_generation: bool = True,
        output_dir: str = None,
        progress_callback=None,
    ) -> dict:
        """完整评测流程（检索层 + 生成层分离）

        Args:
            dataset_path: 测试集路径
            max_samples: 最大样本数
            run_retrieval: 是否运行检索层评测
            run_generation: 是否运行生成层评测
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            最终报告路径和统计信息
        """
        # 1. 加载数据集
        samples = self.load_dataset(dataset_path)

        # 2. RAG 检索 + 生成
        records = self.run_evaluation(samples, max_samples, progress_callback)

        # 3. 检索层评测（使用 RAGAS 生成的 golden_context）
        if run_retrieval:
            records = self.run_retrieval_evaluation(records)

        # 4. 生成层评测
        if run_generation:
            records = self.run_generation_evaluation(records)

        # 5. 归因诊断
        records = self.diagnose_all(records)

        # 6. 生成报告
        report_info = self.generate_reports(records, output_dir)

        return report_info


# 全局便捷函数
def run_full_eval(
    dataset_path: str,
    max_samples: int = None,
    run_retrieval: bool = True,
    run_generation: bool = True,
    output_dir: str = None,
) -> dict:
    """便捷函数：运行完整评测"""
    engine = EvalEngine()
    return engine.run_full_pipeline(
        dataset_path=dataset_path,
        max_samples=max_samples,
        run_retrieval=run_retrieval,
        run_generation=run_generation,
        output_dir=output_dir,
    )
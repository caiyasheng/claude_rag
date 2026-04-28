"""
评测主流程 - T7
包含异常处理的评测执行器
"""
import os
import json
import concurrent.futures
from functools import partial
from typing import List, Optional
from app.rag_eval.schemas import EvalSample, RagResult, EvalRecord
from app.rag_eval.pipeline.runner import run_rag
from app.rag_eval.evaluator.ragas_eval import evaluate_with_ragas
from app.rag_eval.analyzer.diagnose import diagnose
from app.rag_eval.report.generator import generate_csv_report, generate_json_summary, generate_html_report
from app.rag_eval.dataset.loader import load_dataset_from_json, save_dataset_to_json
from app.rag_eval.config import eval_config

MAX_PARALLEL = 3


class EvalEngine:
    """评测引擎 - 统筹整个评测流程"""

    def __init__(self, dataset_path: str = None):
        self.dataset_path = dataset_path
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
        """运行完整评测流程

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

        print(f"开始评测，共 {len(samples)} 条数据，并发度: {MAX_PARALLEL}")

        import concurrent.futures
        from functools import partial

        def evaluate_one(sample, idx):
            try:
                result = run_rag(sample.question)
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

        print(f"评测完成，成功: {sum(1 for r in self.records if r.is_success())}, 失败: {sum(1 for r in self.records if not r.is_success())}")

        return self.records

    def run_ragas_evaluation(self, records: List[EvalRecord] = None) -> List[EvalRecord]:
        """执行RAGAS评测

        Args:
            records: 记录列表，默认使用self.records

        Returns:
            更新后的记录列表
        """
        records = records or self.records
        if not records:
            return []

        print("开始RAGAS评测...")

        try:
            # RAGAS 内部用了 asyncio.run()，新线程运行避免嵌套事件循环
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(evaluate_with_ragas, records)
                records = future.result()
                
            print("RAGAS评测完成")
        except Exception as e:
            print(f"RAGAS评测失败: {e}")

        return records

    def diagnose_all(self, records: List[EvalRecord] = None) -> List[EvalRecord]:
        """对所有记录进行归因诊断"""
        records = records or self.records

        for record in records:
            if record.scores:
                try:
                    record.issues = diagnose(record.scores)
                except Exception as e:
                    print(f"⚠️ 归因诊断失败: {e}")
                    record.issues = ["诊断失败"]

        return records

    def generate_reports(self, records: List[EvalRecord] = None, output_dir: str = None) -> dict:
        """生成报告

        Args:
            records: 记录列表
            output_dir: 输出目录

        Returns:
            报告路径信息
        """
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
        run_ragas: bool = True,
        output_dir: str = None,
        progress_callback=None,
    ) -> dict:
        """完整评测流程

        Args:
            dataset_path: 测试集路径
            max_samples: 最大样本数
            run_ragas: 是否运行RAGAS评测
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            最终报告路径和统计信息
        """
        # 1. 加载数据集
        samples = self.load_dataset(dataset_path)

        # 2. 运行RAG
        records = self.run_evaluation(samples, max_samples, progress_callback)

        # 3. RAGAS评测
        if run_ragas:
            records = self.run_ragas_evaluation(records)

        # 4. 归因诊断
        records = self.diagnose_all(records)

        # 5. 生成报告
        report_info = self.generate_reports(records, output_dir)

        return report_info


# 全局便捷函数
def run_full_eval(
    dataset_path: str,
    max_samples: int = None,
    run_ragas: bool = True,
    output_dir: str = None,
) -> dict:
    """便捷函数：运行完整评测"""
    engine = EvalEngine()
    return engine.run_full_pipeline(
        dataset_path=dataset_path,
        max_samples=max_samples,
        run_ragas=run_ragas,
        output_dir=output_dir,
    )

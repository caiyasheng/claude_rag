"""
评测API路由 - 检索层 + 生成层分离评测
"""
import os
import json
import asyncio
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from anyio import to_thread

from app.rag_eval.schemas import EvalSample, EvalRecord
from app.rag_eval.main import EvalEngine
from app.rag_eval.dataset.loader import load_dataset_from_json, save_dataset_to_json
from app.rag_eval.config import eval_config

router = APIRouter(tags=["eval"])


# ============== 响应模型 ==============

class EvalStatsResponse(BaseModel):
    total_chunks: int
    total_files: int
    dataset_count: int
    last_eval_time: Optional[str] = None


class GenerateResponse(BaseModel):
    success: bool
    message: str
    dataset_path: str
    samples_count: int


class EvalProgressResponse(BaseModel):
    current: int
    total: int
    question: str
    status: str
    result: Optional[dict] = None


class RetrievalMetricsSummary(BaseModel):
    hit_rate_at_k: Optional[float] = None
    recall: Optional[float] = None
    precision: Optional[float] = None
    f1: Optional[float] = None
    map_at_k: Optional[float] = None
    ndcg_at_k: Optional[float] = None


class GenerationMetricsSummary(BaseModel):
    answer_correctness: Optional[float] = None
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    contextual_precision: Optional[float] = None
    contextual_recall: Optional[float] = None


class EvalResultResponse(BaseModel):
    success: bool
    message: str
    report_id: Optional[str] = None
    total: int
    success_count: int
    failed_count: int
    retrieval_metrics: Optional[RetrievalMetricsSummary] = None
    generation_metrics: Optional[GenerationMetricsSummary] = None
    issue_distribution: dict
    records: List[dict]


# ============== API端点 ==============

@router.get("/stats", response_model=EvalStatsResponse)
async def get_eval_stats():
    """获取评测统计信息"""
    from app.services.rag_service import get_rag_service

    rag_service = get_rag_service()
    chunks_data = rag_service.get_all_chunks()

    dataset_path = os.path.join(eval_config.DATASET_DIR, "dataset.json")
    dataset_count = 0
    last_eval_time = None

    if os.path.exists(dataset_path):
        try:
            samples = load_dataset_from_json(dataset_path)
            dataset_count = len(samples)
        except:
            pass

    return EvalStatsResponse(
        total_chunks=chunks_data.get("total_chunks", 0),
        total_files=chunks_data.get("total_files", 0),
        dataset_count=dataset_count,
        last_eval_time=last_eval_time,
    )


@router.post("/dataset/generate", response_model=GenerateResponse)
async def generate_dataset(max_samples: int = 50):
    """从知识库生成测试集（使用 RAGAS，支持 multi-hop、跨文档、三元组）

    Args:
        max_samples: 最大生成数量
    """
    try:
        output_path = os.path.join(eval_config.DATASET_DIR, "dataset.json")
        os.makedirs(eval_config.DATASET_DIR, exist_ok=True)

        # 使用 RAGAS 生成（线程池运行，避免嵌套事件循环）
        from app.rag_eval.dataset.ragas_generator import generate_test_dataset_ragas
        samples = await to_thread.run_sync(
            generate_test_dataset_ragas,
            max_samples,
            output_path,
        )

        return GenerateResponse(
            success=True,
            message="测试集生成成功（RAGAS）",
            dataset_path=output_path,
            samples_count=len(samples),
        )
    except ImportError as e:
        import traceback
        import sys
        print(f"\n❌=== 环境诊断信息 ===❌")
        print(f"Python 版本: {sys.version}")
        print(f"Python 路径: {sys.executable}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"RAGAS 导入失败: {str(e)}\n💡 请检查服务运行的 Python 环境是否正确安装了 ragas")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/dataset/{sample_id}")
async def delete_sample(sample_id: str):
    """删除单条测试数据"""
    from app.rag_eval.dataset.loader import delete_sample_from_json

    dataset_path = os.path.join(eval_config.DATASET_DIR, "dataset.json")
    if not os.path.exists(dataset_path):
        raise HTTPException(status_code=404, detail="测试集文件不存在")

    success = delete_sample_from_json(dataset_path, sample_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"未找到样本: {sample_id}")

    # 重新加载看更新后的数量
    samples = load_dataset_from_json(dataset_path)
    return {"success": True, "message": f"已删除样本: {sample_id}", "count": len(samples)}


@router.delete("/dataset")
async def clear_dataset():
    """清空测试集"""
    from app.rag_eval.dataset.loader import clear_dataset

    dataset_path = os.path.join(eval_config.DATASET_DIR, "dataset.json")
    clear_dataset(dataset_path)
    return {"success": True, "message": "测试集已清空"}


@router.get("/dataset")
async def get_dataset(page: int = 1, page_size: int = 5):
    """获取当前测试集（分页）"""
    dataset_path = os.path.join(eval_config.DATASET_DIR, "dataset.json")

    if not os.path.exists(dataset_path):
        return {"exists": False, "samples": [], "count": 0, "page": 1, "page_size": page_size, "total_pages": 0}

    try:
        samples = load_dataset_from_json(dataset_path)
        total = len(samples)
        total_pages = max(1, (total + page_size - 1) // page_size)

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        page_samples = samples[start:end]

        return {
            "exists": True,
            "samples": [
                {
                    "id": s.id,
                    "question": s.question,
                    "golden_answer": s.golden_answer,
                    "golden_context_count": len(s.golden_context),
                }
                for s in page_samples
            ],
            "count": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
async def run_evaluation(
    max_samples: int = None,
    k: int = 4,
    run_retrieval: bool = True,
    run_generation: bool = True,
):
    """运行评测（检索层 + 生成层分离）

    Args:
        max_samples: 最大评测数量
        k: 检索Top-K
        run_retrieval: 是否运行检索层评测
        run_generation: 是否运行生成层评测
    """
    dataset_path = os.path.join(eval_config.DATASET_DIR, "dataset.json")

    if not os.path.exists(dataset_path):
        raise HTTPException(status_code=400, detail="请先生成或上传测试集")

    try:
        engine = EvalEngine(k=k)

        # 加载数据集
        samples = engine.load_dataset(dataset_path)

        # 限制数量
        if max_samples:
            samples = samples[:max_samples]

        # 进度回调存储
        progress_store = {"records": []}

        def progress_callback(current, total, record):
            progress_store["records"].append({
                "question": record.sample.question,
                "status": "success" if record.is_success() else "failed",
                "latency": record.metadata.get("latency", 0),
            })

        # 运行完整评测流程
        report_info = engine.run_full_pipeline(
            dataset_path=dataset_path,
            max_samples=max_samples,
            run_retrieval=run_retrieval,
            run_generation=run_generation,
            progress_callback=progress_callback,
        )

        records = engine.records

        # 计算检索层平均指标
        retrieval_metrics_list = [
            r.metadata.get("retrieval_metrics")
            for r in records
            if r.metadata.get("retrieval_metrics")
        ]
        retrieval_avg = {}
        if retrieval_metrics_list:
            for key in ["hit_rate_at_k", "recall", "precision", "f1", "map_at_k", "ndcg_at_k"]:
                vals = [getattr(m, key, None) for m in retrieval_metrics_list if getattr(m, key, None) is not None]
                if vals:
                    retrieval_avg[key] = round(sum(vals) / len(vals), 4)

        # 计算生成层平均指标
        valid_scores = [r for r in records if r.scores]
        generation_avg = {}
        if valid_scores:
            for key in ["answer_correctness", "faithfulness", "answer_relevancy", "contextual_precision", "contextual_recall"]:
                vals = [r.scores.get(key) for r in valid_scores if r.scores.get(key) is not None]
                if vals:
                    generation_avg[key] = round(sum(vals) / len(vals), 4)

        # 问题分布
        issue_distribution = {}
        for r in records:
            for issue in r.issues:
                issue_distribution[issue] = issue_distribution.get(issue, 0) + 1

        return EvalResultResponse(
            success=True,
            message="评测完成",
            report_id=report_info["id"],
            total=len(records),
            success_count=sum(1 for r in records if r.is_success()),
            failed_count=sum(1 for r in records if not r.is_success()),
            retrieval_metrics=RetrievalMetricsSummary(**retrieval_avg) if retrieval_avg else None,
            generation_metrics=GenerationMetricsSummary(**generation_avg) if generation_avg else None,
            issue_distribution=issue_distribution,
            records=[
                {
                    "question": r.sample.question,
                    "answer": r.result.answer if r.result else "",
                    "golden_answer": r.sample.golden_answer,
                    "retrieval_metrics": {
                        "hit_rate_at_k": getattr(r.metadata.get("retrieval_metrics"), "hit_rate_at_k", None),
                        "recall": getattr(r.metadata.get("retrieval_metrics"), "recall", None),
                        "precision": getattr(r.metadata.get("retrieval_metrics"), "precision", None),
                        "f1": getattr(r.metadata.get("retrieval_metrics"), "f1", None),
                        "map_at_k": getattr(r.metadata.get("retrieval_metrics"), "map_at_k", None),
                        "ndcg_at_k": getattr(r.metadata.get("retrieval_metrics"), "ndcg_at_k", None),
                    } if r.metadata.get("retrieval_metrics") else None,
                    "generation_scores": r.scores or {},
                    "issues": r.issues,
                    "latency": r.metadata.get("latency", 0),
                }
                for r in records
            ],
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports")
async def get_reports():
    """获取报告列表"""
    reports_dir = os.path.join(eval_config.DATASET_DIR, "reports")

    if not os.path.exists(reports_dir):
        return {"reports": []}

    reports = []
    for fname in os.listdir(reports_dir):
        fpath = os.path.join(reports_dir, fname)
        if os.path.isfile(fpath):
            reports.append({
                "name": fname,
                "path": fpath,
                "size": os.path.getsize(fpath),
                "modified": os.path.getmtime(fpath),
            })

    return {"reports": sorted(reports, key=lambda x: x["modified"], reverse=True)}


@router.get("/report/view/{report_id}", response_class=HTMLResponse)
async def view_html_report(report_id: str):
    """在线查看 HTML 报告"""
    reports_dir = os.path.join(eval_config.DATASET_DIR, "reports")
    fpath = os.path.join(reports_dir, f"eval_{report_id}.html")

    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="报告不存在")

    with open(fpath, "r", encoding="utf-8") as f:
        return f.read()


from fastapi.responses import HTMLResponse
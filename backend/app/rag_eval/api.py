"""
评测API路由
"""
import os
import json
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.rag_eval.schemas import EvalSample, EvalRecord
from app.rag_eval.main import EvalEngine
from app.rag_eval.dataset.loader import load_dataset_from_json, save_dataset_to_json
from app.rag_eval.dataset.generator import generate_test_dataset
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


class EvalResultResponse(BaseModel):
    success: bool
    message: str
    report_id: Optional[str] = None
    total: int
    success_count: int
    failed_count: int
    avg_scores: dict
    issue_distribution: dict
    records: List[dict]


# ============== API端点 ==============

@router.get("/stats", response_model=EvalStatsResponse)
async def get_eval_stats():
    """获取评测统计信息"""
    from app.services.rag_service import get_rag_service

    rag_service = get_rag_service()
    chunks_data = rag_service.get_all_chunks()

    # 检查是否存在已有数据集
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
    """从知识库生成测试集"""
    try:
        output_path = os.path.join(eval_config.DATASET_DIR, "dataset.json")
        os.makedirs(eval_config.DATASET_DIR, exist_ok=True)

        samples = generate_test_dataset(
            max_samples=max_samples,
            output_path=output_path
        )

        return GenerateResponse(
            success=True,
            message="测试集生成成功",
            dataset_path=output_path,
            samples_count=len(samples),
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports")
async def upload_dataset(file: UploadFile = File(...)):
    """上传测试集JSON文件"""
    try:
        content = await file.read()

        # 校验JSON格式
        data = json.loads(content)
        if not isinstance(data, list):
            raise ValueError("Dataset must be a JSON array")

        # 保存
        os.makedirs(eval_config.DATASET_DIR, exist_ok=True)
        output_path = os.path.join(eval_config.DATASET_DIR, "dataset.json")

        with open(output_path, "wb") as f:
            f.write(content)

        return {
            "success": True,
            "message": f"上传成功，共 {len(data)} 条数据",
            "dataset_path": output_path,
            "count": len(data),
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dataset")
async def get_dataset():
    """获取当前测试集"""
    dataset_path = os.path.join(eval_config.DATASET_DIR, "dataset.json")

    if not os.path.exists(dataset_path):
        return {"exists": False, "samples": [], "count": 0}

    try:
        samples = load_dataset_from_json(dataset_path)
        return {
            "exists": True,
            "samples": [
                {
                    "id": s.id,
                    "question": s.question,
                    "golden_answer": s.golden_answer,
                    "golden_context_count": len(s.golden_context),
                }
                for s in samples
            ],
            "count": len(samples),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
async def run_evaluation(max_samples: int = None):
    """运行评测"""
    dataset_path = os.path.join(eval_config.DATASET_DIR, "dataset.json")

    if not os.path.exists(dataset_path):
        raise HTTPException(status_code=400, detail="请先生成或上传测试集")

    try:
        engine = EvalEngine(dataset_path)

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

        # 运行评测
        records = engine.run_evaluation(
            samples,
            max_samples=max_samples,
            progress_callback=progress_callback,
        )

        # RAGAS评测
        records = engine.run_ragas_evaluation(records)

        # 归因诊断
        records = engine.diagnose_all(records)

        # ✅ 自动保存报告，永久存档
        try:
            report_info = engine.generate_reports(records)
        except Exception as e:
            print(f"报告生成失败（不影响结果）: {e}")
            report_info = {"id": None}

        # 计算统计
        success_records = [r for r in records if r.is_success() and r.scores]
        avg_scores = {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_precision": None,
            "context_recall": None,
        }

        if success_records:
            for key in avg_scores:
                values = [r.scores.get(key) for r in success_records if r.scores.get(key) is not None and r.scores.get(key) == r.scores.get(key)]
                if values:
                    avg_scores[key] = round(sum(values) / len(values), 4)

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
            avg_scores={k: (round(v, 4) if v is not None else None) for k, v in avg_scores.items()},
            issue_distribution=issue_distribution,
            records=[
                {
                    "question": r.sample.question,
                    "answer": r.result.answer if r.result else "",
                    "golden_answer": r.sample.golden_answer,
                    "scores": {
                        k: (float(v) if v == v else None)
                        for k, v in (r.scores or {}).items()
                        if v is not None and v == v
                    },
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


@router.get("/report/{report_type}")
async def get_report(report_type: str):
    """获取报告内容"""
    if report_type not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="report_type must be 'csv' or 'json'")

    reports_dir = os.path.join(eval_config.DATASET_DIR, "reports")
    filename = f"eval_report.{report_type}"
    fpath = os.path.join(reports_dir, filename)

    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="报告不存在，请先运行评测")

    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "type": report_type,
        "content": content,
        "path": fpath,
    }


from fastapi.responses import HTMLResponse


@router.get("/report/view/{report_id}", response_class=HTMLResponse)
async def view_html_report(report_id: str):
    """在线查看 HTML 报告"""
    reports_dir = os.path.join(eval_config.DATASET_DIR, "reports")
    fpath = os.path.join(reports_dir, f"eval_{report_id}.html")

    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="报告不存在")

    with open(fpath, "r", encoding="utf-8") as f:
        return f.read()

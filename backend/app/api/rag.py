"""
RAG API Routes
"""
import os
import uuid
import logging
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.rag_service import get_rag_service
from config import UPLOAD_DIR

logger = logging.getLogger(__name__)
router = APIRouter()

# Request/Response models
class QueryRequest(BaseModel):
    question: str
    k: Optional[int] = None
    return_docs: Optional[bool] = False


class QueryResponse(BaseModel):
    answer: str
    docs: Optional[List[dict]] = None


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """RAG 问答接口"""
    try:
        rag_service = get_rag_service()
        result = rag_service.query(
            question=request.question,
            k=request.k,
            return_docs=request.return_docs or True,
        )

        if isinstance(result, tuple):
            answer, docs = result
            doc_dicts = [
                {"content": doc.page_content[:500], "source": doc.metadata.get("source", "unknown")}
                for doc in docs
            ]
            return QueryResponse(answer=answer, docs=doc_dicts)
        else:
            return QueryResponse(answer=result)
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parse-strategies")
async def get_parse_strategies():
    """获取支持的解析策略列表"""
    return {
        "strategies": [
            {
                "value": "auto",
                "label": "智能推荐",
                "description": "自动检测文档类型，兼顾速度与质量",
                "speed": "⚡ 快",
                "useCase": "大多数文档，不知道选什么时推荐"
            },
            {
                "value": "fast",
                "label": "极速模式",
                "description": "PyPDF原生文字提取，速度最快",
                "speed": "🚀 最快",
                "useCase": "纯文字合同、规范、制度文档"
            },
            {
                "value": "ocr_only",
                "label": "扫描件模式",
                "description": "轻量OCR，扫描件拍照文档",
                "speed": "⏱️ 中等",
                "useCase": "扫描件、拍照上传的文档"
            },
            {
                "value": "hi_res",
                "label": "高精度模式",
                "description": "完整结构解析，表格/图表/标题识别",
                "speed": "🐢 较慢",
                "useCase": "PRD、研究报告、设计文档"
            },
            {
                "value": "prd",
                "label": "PRD文档专用",
                "description": "产品需求文档增强模式",
                "speed": "🐢 较慢",
                "useCase": "PRD、含大量表格的文档"
            }
        ]
    }


@router.post("/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    parse_strategy: str = Form("auto", description="解析策略: auto/fast/ocr_only/hi_res/prd"),
):
    """上传并索引文档"""
    try:
        uploaded_files = []
        for file in files:
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(file.filename)[1]
            filename = f"{file_id}{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)

            with open(filepath, "wb") as f:
                content = await file.read()
                f.write(content)

            uploaded_files.append({
                "path": filepath,
                "original_name": file.filename
            })

        rag_service = get_rag_service()
        chunk_count = rag_service.index_documents_with_original_names(
            uploaded_files,
            parse_strategy=parse_strategy
        )

        strategy_names = {
            "auto": "智能推荐",
            "fast": "极速模式",
            "ocr_only": "扫描件模式",
            "hi_res": "高精度模式",
            "prd": "PRD文档专用",
        }

        return {
            "success": True,
            "files": [f["original_name"] for f in uploaded_files],
            "chunks": chunk_count,
            "parse_strategy": parse_strategy,
            "strategy_name": strategy_names.get(parse_strategy, parse_strategy),
        }
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/stats")
async def get_stats():
    """获取索引统计"""
    try:
        rag_service = get_rag_service()
        return rag_service.get_indexed_files()
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/chunks")
async def get_all_chunks(limit: int = 1000):
    """获取所有索引块内容（按文档分组）"""
    try:
        rag_service = get_rag_service()
        return rag_service.get_all_chunks(limit=limit)
    except Exception as e:
        logger.error(f"Get chunks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/delete")
async def delete_document(source: str):
    """按文档名称删除对应索引"""
    try:
        rag_service = get_rag_service()
        deleted_count = rag_service.delete_document(source)
        return {
            "success": True,
            "source": source,
            "deleted_chunks": deleted_count,
            "message": f"Deleted {deleted_count} chunks for document: {source}"
        }
    except Exception as e:
        logger.error(f"Delete document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/reset")
async def reset_index():
    """重置索引"""
    try:
        rag_service = get_rag_service()
        rag_service.reset_index()
        return {"success": True, "message": "Index reset successfully"}
    except Exception as e:
        logger.error(f"Reset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

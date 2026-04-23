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


@router.post("/documents/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """上传并索引文档"""
    try:
        uploaded_paths = []
        for file in files:
            # 保存文件
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(file.filename)[1]
            filename = f"{file_id}{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)

            with open(filepath, "wb") as f:
                content = await file.read()
                f.write(content)

            uploaded_paths.append(filepath)

        # 索引文档
        rag_service = get_rag_service()
        chunk_count = rag_service.index_documents(uploaded_paths)

        return {
            "success": True,
            "files": [f.filename for f in files],
            "chunks": chunk_count,
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

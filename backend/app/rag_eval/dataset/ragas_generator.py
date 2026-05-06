"""
RAGAS 测试集生成器 - 支持多跳、跨文档场景
使用 RAGAS 的 dataset.generate() 生成三元组 (question, golden_context, golden_answer)
"""
import os
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI
from langchain_core.documents import Document

from app.rag_eval.schemas import EvalSample
from app.services.rag_service import get_rag_service
from config import config


# RAGAS 相关配置
os.environ["RAGAS_DO_NOT_TRACK"] = "true"
os.environ["TIKTOKEN_CACHE_DIR"] = "/tmp"
os.environ["TIKTOKEN_NO_DOWNLOAD"] = "1"


def _check_ragas_available():
    """✅ 动态检查 RAGAS 是否可用（每次调用都实时检查）"""
    try:
        from ragas.testset import TestsetGenerator
        from langchain_openai import ChatOpenAI as LangChainChatOpenAI
        return True, TestsetGenerator, LangChainChatOpenAI
    except Exception as e:
        return False, None, None


class RAGASTestsetGenerator:
    """使用 RAGAS 生成测试集"""

    def __init__(self, llm_provider: str = None, llm_model: str = None):
        self.llm_provider = (llm_provider or config.LLM_PROVIDER).lower()
        self.llm_model = llm_model or config.LLM_MODEL
        self.embeddings = None
        self._init_llm()

    def _init_llm(self):
        """初始化 LLM 用于 RAGAS（原生 DashScope SDK，5-10 QPS 高并发）"""
        available, _, LangChainChatOpenAI = _check_ragas_available()
        if not available:
            raise ImportError(
                "RAGAS 未安装或导入失败\n"
                "💡 请运行: pip install ragas>=0.2.0\n"
                "💡 安装后无需重启服务，直接重试即可！"
            )
            
        DASHSCOPE_API_KEY = config.EMBEDDING_API_KEY
        
        if DASHSCOPE_API_KEY and len(DASHSCOPE_API_KEY.strip()) > 20:
            from config import QWEN_MODEL
            from .dashscope_wrapper import QwenChat
            
            self.llm = QwenChat(
                model_name=QWEN_MODEL,
                api_key=DASHSCOPE_API_KEY,
                temperature=0.1,
                max_retries=15,
            )
            print(f"✅ RAGAS LLM: 通义千问 {QWEN_MODEL}（原生 DashScope SDK）")
            print(f"✅ API 入口: https://dashscope.aliyuncs.com/api/v1 (非兼容层)")
            print(f"✅ 并发能力: 5-10 QPS (企业级)")
        else:
            self.llm = LangChainChatOpenAI(
                model=config.LLM_MODEL,
                api_key=config.MINIMAX_API_KEY,
                base_url=config.MINIMAX_API_URL,
                temperature=0.3,
            )
            print(f"⚠️ RAGAS LLM: Minimax（不推荐，易出现 JSON 格式错误）")

    def _init_embeddings(self):
        """初始化 embeddings 用于 RAGAS（原生 DashScope SDK）"""
        if self.embeddings is None:
            DASHSCOPE_API_KEY = config.EMBEDDING_API_KEY
            
            from .dashscope_wrapper import QwenEmbeddings
            self.embeddings = QwenEmbeddings(
                model_name="text-embedding-v3",
                api_key=DASHSCOPE_API_KEY,
            )
            print(f"✅ RAGAS Embedding: 通义千问 text-embedding-v3（原生 DashScope SDK）")

    def generate_from_knowledge_base(
        self,
        max_samples: int = 50,
        output_path: str = None,
        question_types: List[str] = None,
    ) -> List[EvalSample]:
        """从知识库生成测试集（使用 RAGAS）

        Args:
            max_samples: 最大生成数量
            output_path: 保存路径
            question_types: 问题类型列表，可选 ["simple", "complex", "reasoning", "multi-hop"]

        Returns:
            EvalSample 列表（三元组：question, golden_context, golden_answer）
        """
        available, TestsetGenerator, _ = _check_ragas_available()
        if not available:
            raise ImportError(
                "RAGAS 未安装或导入失败\n"
                "💡 请运行: pip install ragas>=0.2.0\n"
                "💡 安装后无需重启服务，直接重试即可！"
            )

        print(f"开始使用 RAGAS 生成测试集，目标数量: {max_samples}")

        # 获取知识库文档
        rag_service = get_rag_service()
        chunks_data = rag_service.get_all_chunks(limit=None)

        if chunks_data.get("total_chunks", 0) == 0:
            raise ValueError("知识库为空，请先索引一些文档")

        # 构建 Documents 列表
        chunks_by_file = chunks_data.get("chunks_by_file", {})
        documents = []
        for source, chunks in chunks_by_file.items():
            for chunk in chunks:
                doc = Document(
                    page_content=chunk["content"],
                    metadata={
                        "source": source,
                        "chunk_id": chunk["id"],
                    }
                )
                documents.append(doc)

        print(f"知识库共有 {len(documents)} 个文档块")

        # 初始化 embeddings
        self._init_embeddings()

        # ✅ 正确方式：from_langchain 工厂方法（RAGAS 0.4.x 官方 API）
        print("✅ 使用 RAGAS 官方 API: TestsetGenerator.from_langchain()")
        print("✅ 稳定模式: max_workers=2 (避免限流)")
        generator = TestsetGenerator.from_langchain(
            llm=self.llm,
            embedding_model=self.embeddings,
        )

        # 生成测试集（稳定模式，避免限流）
        print("RAGAS 正在生成测试集，请稍候...")
        from ragas import RunConfig
        testset = generator.generate_with_langchain_docs(
            documents=documents,
            testset_size=max_samples,
            run_config=RunConfig(
                max_workers=2,
                max_retries=15,
                max_wait=60,
            ),
        )

        # 转换为 EvalSample
        samples = []
        for i, row in testset.iter_rows():
            question = row.get("question", "")
            answer = row.get("ground_truth", "")
            context = row.get("context", [])

            if question and answer:
                # context 可能是 list of strings 或单个 string
                if isinstance(context, str):
                    golden_context = [context] if context else []
                elif isinstance(context, list):
                    golden_context = context
                else:
                    golden_context = []

                sample = EvalSample(
                    id=f"ragas_{i}",
                    question=question,
                    golden_answer=answer,
                    golden_context=golden_context,
                    metadata={
                        "source": "ragas",
                        "question_type": row.get("question_type", "unknown"),
                    }
                )
                samples.append(sample)

        print(f"RAGAS 生成完成！共 {len(samples)} 条测试用例")

        # 保存
        if output_path:
            self._save_samples(samples, output_path)

        return samples

    def generate_simple_dataset(
        self,
        documents: List[Document],
        max_samples: int = 50,
    ) -> List[EvalSample]:
        """简单接口：直接从文档列表生成测试集

        Args:
            documents: Document 列表
            max_samples: 最大数量

        Returns:
            EvalSample 列表
        """
        available, TestsetGenerator, _ = _check_ragas_available()
        if not available:
            raise ImportError(
                "RAGAS 未安装或导入失败\n"
                "💡 请运行: pip install ragas>=0.2.0\n"
                "💡 安装后无需重启服务，直接重试即可！"
            )

        self._init_embeddings()

        # ✅ 正确方式：from_langchain 工厂方法（RAGAS 0.4.x 官方 API）
        generator = TestsetGenerator.from_langchain(
            llm=self.llm,
            embedding_model=self.embeddings,
        )

        from ragas import RunConfig
        testset = generator.generate_with_langchain_docs(
            documents=documents,
            testset_size=max_samples,
            run_config=RunConfig(
                max_workers=2,
                max_retries=15,
                max_wait=60,
            ),
        )

        samples = []
        for i, row in testset.iter_rows():
            question = row.get("question", "")
            answer = row.get("ground_truth", "")
            context = row.get("context", [])

            if question and answer:
                golden_context = context if isinstance(context, list) else [context] if context else []
                sample = EvalSample(
                    id=f"ragas_{i}",
                    question=question,
                    golden_answer=answer,
                    golden_context=golden_context,
                    metadata={"source": "ragas"}
                )
                samples.append(sample)

        return samples

    def _save_samples(self, samples: List[EvalSample], output_path: str):
        """保存样本到文件"""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        data = [
            {
                "id": s.id,
                "question": s.question,
                "golden_answer": s.golden_answer,
                "golden_context": s.golden_context,  # 可能是多个片段的 list
                "metadata": s.metadata,
            }
            for s in samples
        ]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"测试集已保存到: {output_path}")


# 全局函数
def generate_test_dataset_ragas(
    max_samples: int = 50,
    output_path: str = None,
    question_types: List[str] = None,
) -> List[EvalSample]:
    """使用 RAGAS 生成测试集（便捷函数）"""
    generator = RAGASTestsetGenerator()
    return generator.generate_from_knowledge_base(
        max_samples=max_samples,
        output_path=output_path,
        question_types=question_types,
    )
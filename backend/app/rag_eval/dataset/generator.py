"""
数据集生成器 - 使用LLM从知识库自动生成测试集
"""
import json
import os
import time
from typing import List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.rag_eval.schemas import EvalSample
from app.services.rag_service import get_rag_service
from config import config


class DatasetGenerator:
    """从知识库自动生成测试集"""

    def __init__(self, llm_provider: str = None, llm_model: str = None):
        self.llm = self._create_llm(llm_provider, llm_model)

    def _create_llm(self, provider: str = None, model: str = None):
        """创建LLM实例"""
        provider = (provider or config.LLM_PROVIDER).lower()
        model = model or config.LLM_MODEL

        if provider == "minimax":
            return ChatOpenAI(
                model=model,
                api_key=config.MINIMAX_API_KEY,
                base_url=config.MINIMAX_API_URL,
                temperature=0.1,
            )
        elif provider == "openai":
            return ChatOpenAI(
                model=model,
                api_key=config.LLM_API_KEY,
                base_url=config.LLM_BASE_URL if config.LLM_BASE_URL else None,
                temperature=0.1,
            )
        else:
            # 默认用minimax
            return ChatOpenAI(
                model=config.LLM_MODEL,
                api_key=config.MINIMAX_API_KEY,
                base_url=config.MINIMAX_API_URL,
                temperature=0.1,
            )

    def generate_qa_from_chunk(self, chunk: str, chunk_id: str) -> Optional[dict]:
        """从单个chunk生成一对Q&A

        Args:
            chunk: 文档块内容
            chunk_id: 块ID

        Returns:
            {"question": str, "golden_answer": str} 或 None
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个问答对生成专家。

**严格输出要求：**
- 只返回一个合法的 JSON 对象
- 不要任何解释、说明、markdown标记
- 不要代码块标记 ```json
- 直接输出：{{"question": "...", "golden_answer": "..."}}

生成要求：
1. 问题要具体、有意义，不能太泛
2. 答案要能从文档片段中找到
3. 用中文生成"""),
            ("human", "文档片段:\n{chunk}")
        ])

        chain = prompt | self.llm

        try:
            response = chain.invoke({"chunk": chunk})
            text = response.content.strip()

            text = self._clean_json_text(text)

            try:
                qa = json.loads(text)
            except json.JSONDecodeError:
                qa = self._extract_json_fallback(text)

            if qa and "question" in qa and "golden_answer" in qa:
                return qa
            return None
        except Exception as e:
            print(f"生成Q&A失败 (chunk_id={chunk_id}): {e}")
            return None

    def _clean_json_text(self, text: str) -> str:
        """清理JSON文本"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _extract_json_fallback(self, text: str) -> Optional[dict]:
        """容错：用正则提取JSON"""
        import re

        match = re.search(r'\{[\s\S]*"question"[\s\S]*"golden_answer"[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass

        match = re.search(r'\{[^{}]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass

        print(f"JSON解析失败，原始内容前100字符: {text[:100]}")
        return None

    def generate_from_knowledge_base(self, max_samples: int = 50, output_path: str = None) -> List[EvalSample]:
        """从知识库生成测试集

        Args:
            max_samples: 最大生成数量
            output_path: 保存路径

        Returns:
            EvalSample列表
        """
        print(f"开始从知识库生成测试集，目标数量: {max_samples}")

        # 从RAGService获取所有chunks
        rag_service = get_rag_service()
        chunks_data = rag_service.get_all_chunks(limit=None)  # 先拿全部

        if chunks_data.get("total_chunks", 0) == 0:
            raise ValueError("知识库为空，请先索引一些文档")

        chunks_by_file = chunks_data.get("chunks_by_file", {})
        all_chunks = []
        for source, chunks in chunks_by_file.items():
            for chunk in chunks:
                all_chunks.append({
                    "id": chunk["id"],
                    "content": chunk["content"],
                    "source": source
                })

        print(f"知识库共有 {len(all_chunks)} 个chunks")

        import random
        random.shuffle(all_chunks)  # ✅ 打乱，保证不同文档均衡采样

        # 限制数量 (多拿一些，保证多样性)
        all_chunks = all_chunks[:max_samples * 4]

        print(f"已打乱，随机选择 {len(all_chunks)} 个chunks生成")

        samples = []
        generated = 0
        failed = 0

        for i, chunk in enumerate(all_chunks):
            if generated >= max_samples:
                break

            print(f"正在生成 {generated + 1}/{max_samples} ...")

            qa = self.generate_qa_from_chunk(chunk["content"], chunk["id"])

            if qa:
                sample = EvalSample(
                    id=f"gen_{chunk['id']}",
                    question=qa["question"],
                    golden_answer=qa["golden_answer"],
                    golden_context=[chunk["content"]],  # 使用原始chunk作为golden_context
                    metadata={
                        "source": chunk["source"],
                        "chunk_id": chunk["id"],
                    }
                )
                samples.append(sample)
                generated += 1
            else:
                failed += 1

            # 避免请求过快
            time.sleep(0.5)

        print(f"生成完成！成功: {generated}, 失败: {failed}")

        # 保存
        if output_path:
            self._save_samples(samples, output_path)

        return samples

    def _save_samples(self, samples: List[EvalSample], output_path: str):
        """保存样本到文件"""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

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

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"测试集已保存到: {output_path}")


def generate_test_dataset(max_samples: int = 50, output_path: str = None) -> List[EvalSample]:
    """便捷函数：从知识库生成测试集"""
    generator = DatasetGenerator()
    return generator.generate_from_knowledge_base(max_samples=max_samples, output_path=output_path)

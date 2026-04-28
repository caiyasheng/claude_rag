"""
统一数据结构 - T3
核心数据结构定义，解耦输入/输出/评测
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvalSample:
    """测试样本"""
    id: str
    question: str
    golden_answer: str
    golden_context: list[str]  # ground truth contexts
    metadata: dict = field(default_factory=dict)


@dataclass
class RagResult:
    """RAG执行结果"""
    answer: str
    retrieved_chunks: list[str]  # 检索到的文档块
    reranked_chunks: list[str] = field(default_factory=list)  # 重排后的文档块（如果有）
    final_context: str = ""  # 最终拼接到context的文本
    latency: float = 0.0  # 响应延迟(秒)
    token_count: int = 0  # token消耗


@dataclass
class EvalRecord:
    """评测记录 - 统一数据结构"""
    sample: EvalSample
    result: Optional[RagResult]  # None表示执行失败
    scores: Optional[dict] = None  # RAGAS评测分数
    issues: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # 可扩展：latency, token_count, error等

    def is_success(self) -> bool:
        """是否成功执行"""
        return self.result is not None

    def get_question(self) -> str:
        """获取问题"""
        return self.sample.question

    def get_answer(self) -> str:
        """获取模型回答"""
        return self.result.answer if self.result else ""

    def get_scores(self) -> dict:
        """获取分数，失败时返回空字典"""
        return self.scores or {}

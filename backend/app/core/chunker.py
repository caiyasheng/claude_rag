"""
文本分块模块 - 支持多种分块策略
包括: RecursiveCharacterTextSplitter, 语义分块, 代码分块等
"""
from typing import List, Optional, Callable
from langchain_core.documents import Document
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    Language,
    TextSplitter,
)
from config import config
import logging

logger = logging.getLogger(__name__)


class ChunkConfig:
    """分块配置"""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size or config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or config.CHUNK_OVERLAP
        self.separators = separators
        logger.info(f"[分块配置] chunk_size={self.chunk_size}, chunk_overlap={self.chunk_overlap}")


class RecursiveChunker:
    """使用RecursiveCharacterTextSplitter进行分块"""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        separators: Optional[List[str]] = None,
        keep_separator: bool = True,
    ):
        self.chunk_size = chunk_size or config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or config.CHUNK_OVERLAP
        self.separators = separators or ["\n\n", "\n", ".", "，", " "]
        self.keep_separator = keep_separator
        logger.info(f"[递归分块器] 初始化: 块大小={self.chunk_size}, 重叠={self.chunk_overlap}")

    def split_documents(
        self,
        documents: List[Document],
    ) -> List[Document]:
        total_chars = sum(len(doc.page_content) for doc in documents)
        logger.info(f"[递归分块器] 开始分块: {len(documents)} 个文档, {total_chars} 字符")
        print(f"✂️  [分块器] 开始分块: {len(documents)} 个文档, {total_chars} 字符")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            keep_separator=self.keep_separator,
        )
        chunks = text_splitter.split_documents(documents)
        logger.info(f"[递归分块器] 分块完成: 生成 {len(chunks)} 个块")
        print(f"✅ [分块器] 分块完成: 生成 {len(chunks)} 个块")
        return chunks


class CodeChunker:
    """代码专用分块器"""

    # 支持的编程语言
    SUPPORTED_LANGUAGES = {
        "python": Language.PYTHON,
        "js": Language.JS,
        "javascript": Language.JS,
        "typescript": Language.TS,
        "ts": Language.TS,
        "java": Language.JAVA,
        "c": Language.C,
        "cpp": Language.CPP,
        "go": Language.GO,
        "rust": Language.RUST,
        "ruby": Language.RUBY,
        "php": Language.PHP,
        "swift": Language.SWIFT,
        "kotlin": Language.KOTLIN,
    }

    def __init__(
        self,
        language: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 0,
    ):
        """
        初始化代码分块器

        Args:
            language: 编程语言，如"python", "js"
            chunk_size: 块大小
            chunk_overlap: 重叠大小
        """
        self.language = language.lower()
        if self.language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"不支持的语言: {language}, 支持: {list(self.SUPPORTED_LANGUAGES.keys())}"
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        """分割代码文本"""
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=self.SUPPORTED_LANGUAGES[self.language],
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        return splitter.split_text(text)

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """分割代码文档"""
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=self.SUPPORTED_LANGUAGES[self.language],
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        return splitter.split_documents(documents)


class SemanticChunker:
    """语义分块器 - 基于句子相似度进行分割"""

    def __init__(
        self,
        buffer_size: int = 1,
        breakpoint_percentile_threshold: int = 95,
        embed_model=None,
    ):
        """
        初始化语义分块器

        Args:
            buffer_size: 缓冲区大小，控制评估相似度时组合多少个句子
            breakpoint_percentile_threshold: 断点阈值，数值越小分割越细
            embed_model: 嵌入模型，默认使用OpenAI
        """
        self.buffer_size = buffer_size
        self.breakpoint_percentile_threshold = breakpoint_percentile_threshold
        self.embed_model = embed_model or OpenAIEmbedding()

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """分割文档"""
        from llama_index.core import Document as LlamaDocument

        # 转换为LlamaIndex文档
        llama_docs = [LlamaDocument(text=doc.page_content) for doc in documents]

        splitter = SemanticSplitterNodeParser(
            buffer_size=self.buffer_size,
            breakpoint_percentile_threshold=self.breakpoint_percentile_threshold,
            embed_model=self.embed_model,
        )

        nodes = splitter.get_nodes_from_documents(llama_docs)

        # 转换回LangChain文档
        return [
            Document(page_content=node.text, metadata=documents[0].metadata)
            for node in nodes
        ]


class AdaptiveChunker:
    """自适应分块器 - 根据内容类型自动选择分块策略"""

    def __init__(
        self,
        text_chunk_size: int = None,
        text_chunk_overlap: int = None,
    ):
        self.text_chunk_size = text_chunk_size or config.CHUNK_SIZE
        self.text_chunk_overlap = text_chunk_overlap or config.CHUNK_OVERLAP

    def split_documents(
        self,
        documents: List[Document],
        custom_splitter: Optional[Callable] = None,
    ) -> List[Document]:
        """
        分割文档，自动检测内容类型

        Args:
            documents: Document列表
            custom_splitter: 可选的自定义分块器

        Returns:
            分割后的Document列表
        """
        if custom_splitter:
            return custom_splitter(documents)

        # 简单检测是否是代码（通过元数据或内容特征）
        if documents:
            first_doc = documents[0]
            metadata = first_doc.metadata or {}

            # 检查是否有语言标记
            if metadata.get("category") == "Code":
                # 使用基础分块器
                pass

        # 默认使用RecursiveCharacterTextSplitter
        return RecursiveChunker(
            chunk_size=self.text_chunk_size,
            chunk_overlap=self.text_chunk_overlap,
        ).split_documents(documents)


def chunk_documents(
    documents: List[Document],
    strategy: str = "recursive",
    **kwargs,
) -> List[Document]:
    if not documents:
        logger.warning("[分块器] 空文档列表，跳过分块")
        return []

    logger.info(f"[分块器] 使用策略: {strategy}")
    print(f"🔧 [分块器] 使用分块策略: {strategy}")

    if strategy == "recursive":
        chunker = RecursiveChunker(**kwargs)
        return chunker.split_documents(documents)

    elif strategy == "semantic":
        logger.info("[分块器] 使用语义分块策略")
        print("🧠 [分块器] 使用语义分块策略")
        chunker = SemanticChunker(**kwargs)
        return chunker.split_documents(documents)

    elif strategy == "code":
        language = kwargs.get("language", "python")
        logger.info(f"[分块器] 使用代码分块策略，语言: {language}")
        print(f"💻 [分块器] 使用代码分块策略，语言: {language}")
        chunker = CodeChunker(language=language)
        return chunker.split_documents(documents)

    else:
        raise ValueError(f"未知的分块策略: {strategy}")


if __name__ == "__main__":
    # 测试
    from langchain_core.documents import Document

    docs = [Document(page_content="这是第一段。\n\n这是第二段。\n\n这是第三段。")]
    chunks = chunk_documents(docs, strategy="recursive", chunk_size=50, chunk_overlap=10)
    print(f"分块结果: {len(chunks)} 个块")
    for i, chunk in enumerate(chunks):
        print(f"  块 {i+1}: {chunk.page_content[:50]}...")

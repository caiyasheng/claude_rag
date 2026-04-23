"""
数据加载模块 - 使用Unstructured实现强大的文档解析能力
支持: PDF, Markdown, HTML, JSON, TXT, 网页等
"""
from typing import List, Optional, Union
from langchain_core.documents import Document
from langchain_unstructured import UnstructuredLoader
from unstructured.partition.auto import partition
import os
import logging

logger = logging.getLogger(__name__)


class DocumentLoader:
    """统一的文档加载器，使用Unstructured作为核心解析引擎"""

    def __init__(self, strategy: str = "hi_res"):
        self.strategy = strategy
        logger.info(f"[文档加载器] 初始化，解析策略: {strategy}")
        print(f"📄 [文档加载器] 初始化完成，解析策略: {strategy}")

    def load_file(
        self,
        file_path: str,
        strategy: Optional[str] = None,
        coordinates: bool = False,
        partition_via_api: bool = False,
    ) -> List[Document]:
        strategy = strategy or self.strategy
        filename = os.path.basename(file_path)
        logger.info(f"[文档加载器] 开始加载文件: {filename}")
        print(f"📥 [文档加载器] 开始加载: {filename}")

        loader = UnstructuredLoader(
            file_path=file_path,
            strategy=strategy,
            partition_via_api=partition_via_api,
            coordinates=coordinates,
        )

        docs = list(loader.load())
        total_chars = sum(len(doc.page_content) for doc in docs)
        logger.info(f"[文档加载器] 文件 {filename} 加载完成: {len(docs)} 个元素, {total_chars} 字符")
        print(f"✅ [文档加载器] {filename} 加载完成: {len(docs)} 个元素, {total_chars} 字符")
        return docs

    def load_web(self, url: str) -> List[Document]:
        logger.info(f"[文档加载器] 开始加载网页: {url}")
        print(f"🌐 [文档加载器] 开始加载网页: {url}")
        loader = UnstructuredLoader(web_url=url)
        docs = list(loader.load())
        total_chars = sum(len(doc.page_content) for doc in docs)
        logger.info(f"[文档加载器] 网页 {url} 加载完成: {len(docs)} 个元素, {total_chars} 字符")
        print(f"✅ [文档加载器] 网页加载完成: {len(docs)} 个元素, {total_chars} 字符")
        return docs

    def load_with_unstructured(
        self,
        filename: str,
        content_type: Optional[str] = None,
    ) -> List[Document]:
        """
        使用unstructured.partition直接解析

        Args:
            filename: 文件路径
            content_type: 内容类型，如"application/pdf"

        Returns:
            Document列表
        """
        elements = partition(filename=filename, content_type=content_type)

        docs = []
        for el in elements:
            docs.append(
                Document(
                    page_content=str(el),
                    metadata={
                        "category": type(el).__name__,
                        "element_id": getattr(el, "id", None),
                    },
                )
            )
        return docs

    def load_with_parent_child(
        self,
        file_path: str,
        page_number: Optional[int] = None,
    ) -> List[Document]:
        """
        加载文档并建立父子关系

        Args:
            file_path: 文件路径
            page_number: 如果指定，只处理指定页面

        Returns:
            Document列表，包含父子关系
        """
        loader = UnstructuredLoader(
            file_path=file_path,
            strategy=self.strategy,
        )

        docs = list(loader.load())

        # 如果指定了页面号，过滤
        if page_number is not None:
            docs = [doc for doc in docs if doc.metadata.get("page_number") == page_number]

        return docs


def load_documents(
    source: Union[str, List[str]],
    source_type: str = "auto",
    strategy: str = "hi_res",
) -> List[Document]:
    loader = DocumentLoader(strategy=strategy)

    if isinstance(source, list):
        logger.info(f"[文档加载器] 批量加载 {len(source)} 个文件")
        print(f"📚 [文档加载器] 批量加载 {len(source)} 个文件")
        all_docs = []
        for s in source:
            all_docs.extend(load_documents(s, source_type, strategy))
        logger.info(f"[文档加载器] 批量加载完成，总计 {len(all_docs)} 个元素")
        print(f"📚 [文档加载器] 批量加载完成，总计 {len(all_docs)} 个元素")
        return all_docs

    if source_type == "auto":
        if source.startswith("http"):
            source_type = "web"
        else:
            source_type = "file"

    if source_type == "web":
        return loader.load_web(source)
    else:
        return loader.load_file(source)


if __name__ == "__main__":
    # 测试
    loader = DocumentLoader()

    # 测试PDF
    # docs = loader.load_file("data/sample.pdf")
    # print(f"加载了 {len(docs)} 个文档块")

    # 测试网页
    # docs = loader.load_web("https://zh.wikipedia.org/wiki/黑神话：悟空")
    # print(f"加载了 {len(docs)} 个文档块")
    print("DocumentLoader 已就绪")

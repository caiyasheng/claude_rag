"""
数据加载模块 - 优化的文档解析能力
支持: PDF, Markdown, HTML, JSON, TXT, CSV, 网页等
"""
from typing import List, Optional, Union
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_unstructured import UnstructuredLoader
from unstructured.partition.auto import partition
from unstructured.partition.csv import partition_csv
import os
import logging
import io

logger = logging.getLogger(__name__)


class DocumentLoader:
    """优化的文档加载器 - 默认使用PyPDF保证速度，需要OCR时可选hi_res"""

    def __init__(self, strategy: str = "auto", languages: List[str] = ["chi_sim", "eng"]):
        """
        Args:
            strategy: auto     = 智能检测，原生文字用PyPDF，扫描版自动用OCR
                     fast     = PyPDF快速提取原生文字
                     ocr_only = 仅使用轻量OCR（扫描版PDF推荐，不卡）
                     hi_res   = Unstructured高清OCR（质量最好但最慢）
        """
        self.strategy = strategy
        self.languages = languages
        logger.info(f"[文档加载器] 初始化，解析策略: {strategy}")
        mode_names = {
            "auto": "智能自动模式",
            "fast": "快速模式 (PyPDF)",
            "ocr_only": "轻量OCR模式",
            "hi_res": "高清OCR模式"
        }
        print(f"📄 [文档加载器] 初始化完成，使用: {mode_names.get(strategy, strategy)}")

    def load_file(
        self,
        file_path: str,
        strategy: Optional[str] = None,
        coordinates: bool = False,
        partition_via_api: bool = False,
        languages: Optional[List[str]] = None,
    ) -> List[Document]:
        strategy = strategy or self.strategy
        languages = languages or self.languages
        filename = os.path.basename(file_path)
        logger.info(f"[文档加载器] 开始加载文件: {filename}, strategy={strategy}")
        print(f"📥 [文档加载器] 开始加载: {filename}")

        if filename.lower().endswith(".pdf"):
            if strategy == "auto":
                return self._load_pdf_auto(file_path)
            elif strategy == "fast":
                return self._load_pdf_fast(file_path)
            elif strategy == "ocr_only":
                return self._load_pdf_ocr_only(file_path)
        
        if filename.lower().endswith(".csv"):
            return self._load_csv(file_path)
        
        return self._load_with_unstructured(
            file_path, strategy, coordinates, partition_via_api, languages
        )

    def _load_pdf_auto(self, file_path: str) -> List[Document]:
        """智能模式: 先用fast检测，如果是扫描版自动转轻量OCR"""
        docs = self._load_pdf_fast(file_path)
        total_chars = sum(len(d.page_content) for d in docs)
        
        if total_chars < 100 and len(docs) > 0:
            filename = os.path.basename(file_path)
            print(f"🔍 检测到是扫描版PDF，自动切换到轻量OCR模式...")
            return self._load_pdf_ocr_only(file_path)
        return docs

    def _load_pdf_fast(self, file_path: str) -> List[Document]:
        """使用 PyPDF 快速提取 PDF 原生文字（速度快10~100倍）"""
        filename = os.path.basename(file_path)
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            
            for doc in docs:
                doc.page_content = self._clean_text(doc.page_content)
                doc.metadata["category"] = self._infer_category(doc.page_content)
                
            total_chars = sum(len(doc.page_content) for doc in docs)
            logger.info(f"[文档加载器] PyPDF 加载完成: {len(docs)} 页, {total_chars} 字符")
            print(f"✅ [文档加载器] {filename} 快速加载完成: {len(docs)} 页, {total_chars} 字符")
            
            if total_chars < 100 and len(docs) > 0:
                print(f"⚠️  [提示] 提取文字较少，这可能是扫描版PDF，建议使用 strategy='hi_res' OCR 模式")
            
            return docs
        except Exception as e:
            logger.warning(f"PyPDF 加载失败，回退到 unstructured: {e}")
            print(f"⚠️  PyPDF 加载失败，回退到 OCR 模式...")
            return self._load_pdf_ocr_only(file_path)

    def _load_pdf_ocr_only(self, file_path: str) -> List[Document]:
        """轻量 OCR 模式 - 使用 pytesseract 直接识别（快！不卡！）"""
        filename = os.path.basename(file_path)
        
        try:
            import pytesseract
            from pdf2image import convert_from_path
            
            print(f"🔍 开始轻量 OCR 识别: {filename}")
            
            lang = "+".join(self.languages)
            images = convert_from_path(file_path, dpi=150)
            docs = []
            
            for page_num, image in enumerate(images, 1):
                text = pytesseract.image_to_string(image, lang=lang)
                if text.strip():
                    cleaned_text = self._clean_text(text)
                    docs.append(Document(
                        page_content=cleaned_text,
                        metadata={
                            "source": file_path,
                            "page_number": page_num,
                            "category": self._infer_category(cleaned_text),
                            "filename": filename,
                        }
                    ))
            
            total_chars = sum(len(d.page_content) for d in docs)
            print(f"✅ [轻量OCR] {filename} 完成: {len(docs)} 页, {total_chars} 字符")
            logger.info(f"[轻量OCR] 完成: {len(docs)} 页, {total_chars} 字符")
            return docs
            
        except ImportError as e:
            logger.warning(f"OCR 依赖未安装 {e}，回退到 hi_res 模式")
            print(f"⚠️  OCR 依赖未完全安装，使用标准 hi_res 模式...")
            return self._load_with_unstructured(file_path, "hi_res", False, False, self.languages)

    def _load_csv(self, file_path: str) -> List[Document]:
        """使用 Unstructured 解析 CSV 文件
        CSV 会被解析为 Table 元素，保留行列结构
        """
        filename = os.path.basename(file_path)
        try:
            elements = partition_csv(
                filename=file_path,
                include_header=True,
                infer_table_structure=True,
            )
            
            docs = []
            for el in elements:
                doc = Document(
                    page_content=str(el),
                    metadata={
                        "source": file_path,
                        "filename": filename,
                        "category": "Table",
                        "element_id": getattr(el, "id", None),
                    }
                )
                if hasattr(el, "metadata") and hasattr(el.metadata, "text_as_html"):
                    doc.metadata["table_html"] = el.metadata.text_as_html
                docs.append(doc)
            
            total_rows = len(docs)
            total_chars = sum(len(doc.page_content) for doc in docs)
            logger.info(f"[CSV加载器] {filename} 完成: {total_rows} 行, {total_chars} 字符")
            print(f"✅ [CSV加载器] {filename} 完成: {total_rows} 行, {total_chars} 字符")
            return docs
            
        except Exception as e:
            logger.error(f"CSV 加载失败: {e}")
            print(f"❌ [CSV加载器] {filename} 失败: {e}")
            raise

    def _load_with_unstructured(
        self,
        file_path: str,
        strategy: str,
        coordinates: bool = False,
        partition_via_api: bool = False,
        languages: Optional[List[str]] = None,
    ) -> List[Document]:
        """使用 Unstructured 进行高级解析（支持OCR）"""
        filename = os.path.basename(file_path)
        
        loader_kwargs = {
            "file_path": file_path,
            "strategy": strategy,
            "partition_via_api": partition_via_api,
            "coordinates": coordinates,
            "languages": languages or self.languages,
        }
        
        if strategy == "hi_res":
            loader_kwargs.update({
                "table_format": "html",
                "include_page_breaks": True,
                "infer_table_structure": True,
            })
        
        loader = UnstructuredLoader(**loader_kwargs)

        docs = list(loader.load())
        total_chars = sum(len(doc.page_content) for doc in docs)
        logger.info(f"[文档加载器] 文件 {filename} 加载完成: {len(docs)} 个元素, {total_chars} 字符")
        print(f"✅ [文档加载器] {filename} 加载完成: {len(docs)} 个元素, {total_chars} 字符")
        return docs

    def load_prd(self, file_path: str) -> List[Document]:
        """专门加载PRD产品需求文档
        强制使用 hi_res 模式，最优保留表格、列表、标题层级
        适用于: PRD、设计文档、研究报告、包含大量图表的文档
        """
        filename = os.path.basename(file_path)
        logger.info(f"[PRD加载器] 开始解析产品需求文档: {filename} (强制hi_res模式)")
        print(f"📋 [PRD加载器] 解析结构化文档: {filename}")
        print(f"   → 启用: 表格HTML结构 / 标题层级识别 / 列表还原")
        
        docs = self._load_with_unstructured(
            file_path,
            strategy="hi_res",
        )
        
        for doc in docs:
            doc.page_content = self._clean_text(doc.page_content)
            if "category" not in doc.metadata:
                doc.metadata["category"] = self._infer_category(doc.page_content)
        
        categories = {}
        for doc in docs:
            cat = doc.metadata.get("category", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1
        
        category_info = ", ".join([f"{k}:{v}" for k, v in categories.items()])
        logger.info(f"[PRD加载器] 结构识别结果: {category_info}")
        print(f"✅ [PRD加载器] 完成! 结构统计: {category_info}")
        
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
        loader_kwargs = {
            "file_path": file_path,
            "strategy": self.strategy,
        }
        
        if self.strategy == "hi_res":
            loader_kwargs.update({
                "table_format": "html",
                "infer_table_structure": True,
            })
        
        loader = UnstructuredLoader(**loader_kwargs)
        docs = list(loader.load())

        if page_number is not None:
            docs = [doc for doc in docs if doc.metadata.get("page_number") == page_number]

        return docs

    def _clean_text(self, text: str) -> str:
        """基础文档清洗
        - 去除多余空白和换行
        - 去除常见页眉页脚特征
        - 规范化标点
        """
        import re
        
        lines = text.split("\n")
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            if re.match(r'^\d+\s*$', line) and len(line) <= 3:
                continue
            
            if len(line) < 50:
                if re.search(r'第\s*\d+\s*页|Page\s*\d+|版权所有|©|Confidential', line, re.IGNORECASE):
                    continue
            
            cleaned_lines.append(line)
        
        result = "\n".join(cleaned_lines)
        
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = re.sub(r' {2,}', ' ', result)
        
        return result

    def _infer_category(self, text: str) -> str:
        """根据内容特征推断元素类别"""
        import re
        
        text_stripped = text.strip()
        
        if len(text_stripped) < 80:
            if re.match(r'^[一二三四五六七八九十]+、|^\d+\.\s|^第[一二三四五六七八九十]+章|^[A-Z][a-z]+(\s+[A-Z][a-z]+){0,5}$', text_stripped):
                return "Heading"
            
            if text_stripped.isupper() and len(text_stripped) < 50:
                return "Title"
        
        if re.match(r'^[-•●○■□▪▫►▸]|^\d+[.、)]\s', text_stripped):
            return "ListItem"
        
        if text_stripped.count("|") >= 2 or text_stripped.count("\t") >= 2:
            return "Table"
        
        return "NarrativeText"


def load_documents(
    source: Union[str, List[str]],
    source_type: str = "auto",
    strategy: str = "auto",
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
    elif source_type == "prd":
        return loader.load_prd(source)
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

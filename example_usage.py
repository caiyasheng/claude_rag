"""
RAG系统使用示例
"""
from main import RAGSystem


def example_basic():
    """基础用法"""
    # 初始化RAG系统
    rag = RAGSystem(
        embedding_provider="huggingface",  # 使用HuggingFace嵌入
        llm_provider="openai",  # 使用OpenAI LLM
    )

    # 加载并索引文档
    rag.load_and_index(
        source="./data/your_document.pdf",  # PDF文件
        source_type="file",
        verbose=True,
    )

    # 查询
    answer = rag.query("你的问题是什么？")
    print(f"答案: {answer}")


def example_web():
    """网页加载示例"""
    rag = RAGSystem()

    # 加载网页
    rag.load_and_index(
        source="https://zh.wikipedia.org/wiki/人工智能",
        source_type="web",
        verbose=True,
    )

    # 查询
    answer = rag.query("人工智能的定义是什么？")
    print(f"答案: {answer}")


def example_multiple_docs():
    """多文档加载示例"""
    rag = RAGSystem()

    # 加载多个文档
    rag.load_and_index(
        source=[
            "./data/doc1.pdf",
            "./data/doc2.md",
            "./data/doc3.txt",
        ],
        verbose=True,
    )

    # 查询
    answer = rag.query("相关问题")
    print(f"答案: {answer}")


def example_with_rerank():
    """使用重排序的示例"""
    rag = RAGSystem()

    rag.load_and_index("./data/document.pdf", verbose=True)

    # 使用重排序检索
    answer = rag.query(
        "你的问题",
        use_rerank=True,
        verbose=True,
    )
    print(f"答案: {answer}")


def example_programmatic():
    """编程方式使用"""
    from loader import load_documents
    from chunker import chunk_documents
    from embedding import create_embeddings
    from vectorstore import create_vectorstore
    from retriever import create_retriever
    from chain import create_rag_chain

    # 1. 加载
    docs = load_documents("./data/document.pdf")

    # 2. 分块
    chunks = chunk_documents(docs, strategy="recursive", chunk_size=500, chunk_overlap=100)

    # 3. 嵌入
    embeddings = create_embeddings(provider="huggingface", model="BAAI/bge-small-zh")

    # 4. 向量存储
    vectorstore = create_vectorstore(
        provider="chroma",
        embeddings=embeddings,
        documents=chunks,
        persist_directory="./my_vectorstore",
    )

    # 5. 创建检索器
    retriever = create_retriever(
        vectorstore=vectorstore,
        retriever_type="similarity",
        search_kwargs={"k": 3},
    )

    # 6. 创建RAG链
    chain = create_rag_chain(
        retriever=retriever,
        llm_type="openai",
    )

    # 7. 查询
    answer = chain.invoke("你的问题")
    print(f"答案: {answer}")


if __name__ == "__main__":
    example_basic()

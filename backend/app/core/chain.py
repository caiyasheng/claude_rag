"""
RAG链模块 - 构建完整的RAG查询链
"""
from typing import Optional, Dict, Any, List, Union, Callable
from langchain_core.retrievers import BaseRetriever
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (
    RunnablePassthrough,
    RunnableParallel,
    RunnableLambda,
)
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel
from config import config
import logging
import time

logger = logging.getLogger(__name__)


def log_chain_step(step_name: str, data: Any) -> Any:
    """记录链执行步骤"""
    logger.info(f"[RAG链] {step_name}")
    return data


class RAGChain:
    """RAG链 - 整合检索和生成"""

    def __init__(
        self,
        retriever: BaseRetriever,
        llm: BaseChatModel = None,
        prompt_template: str = None,
        system_prompt: str = None,
        input_key: str = "question",
        context_key: str = "context",
        output_key: str = "answer",
    ):
        self.retriever = retriever
        self.llm = llm or self._create_llm()
        self.input_key = input_key
        self.context_key = context_key
        self.output_key = output_key
        logger.info(f"[RAG链] 初始化 RAG 链，LLM提供者: {config.LLM_PROVIDER}")
        print(f"⛓️  [RAG链] 初始化完成，LLM: {config.LLM_PROVIDER.upper()}")

        # 默认提示模板
        if prompt_template is None:
            prompt_template = """基于以下上下文，回答问题。如果上下文中没有相关信息，请说"我无法从提供的上下文中找到相关信息"。

上下文:
{context}

问题: {question}

回答:"""

        if system_prompt:
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", prompt_template),
            ])
        else:
            self.prompt = PromptTemplate.from_template(prompt_template)

        self._build_chain()

    def _create_llm(self) -> BaseChatModel:
        """创建LLM"""
        provider = config.LLM_PROVIDER.lower()

        if provider == "openai":
            return ChatOpenAI(
                model=config.LLM_MODEL,
                api_key=config.LLM_API_KEY,
                base_url=config.LLM_BASE_URL if config.LLM_BASE_URL else None,
                temperature=0.7,
            )

        elif provider == "deepseek":
            return ChatDeepSeek(
                model=config.DEEPSEEK_MODEL or "deepseek-chat",
                api_key=config.DEEPSEEK_API_KEY,
                temperature=0.7,
            )

        elif provider == "ollama":
            return ChatOllama(
                model=config.OLLAMA_MODEL or "qwen2.5",
                base_url=config.OLLAMA_BASE_URL,
                temperature=0.7,
            )

        elif provider == "minimax":
            return ChatOpenAI(
                model=config.LLM_MODEL,
                api_key=config.MINIMAX_API_KEY,
                base_url=config.MINIMAX_API_URL,
                temperature=0.7,
            )

        else:
            raise ValueError(f"不支持的LLM提供者: {provider}")

    def _build_chain(self):
        """构建LCEL链"""
        def log_retrieval(docs: List) -> str:
            """记录检索结果并格式化"""
            logger.info(f"[RAG链] 检索到 {len(docs)} 个相关文档")
            doc_lengths = [len(doc.page_content) for doc in docs]
            total_chars = sum(doc_lengths)
            avg_length = int(total_chars / len(docs)) if docs else 0
            print(f"📚 [检索完成] {len(docs)} 个相关片段, 平均 {avg_length} 字符, 总计 {total_chars} 字符")
            return "\n\n".join(doc.page_content for doc in docs)

        def log_prompt(data: Dict) -> Dict:
            """记录提示词构建"""
            context_length = len(data.get(self.context_key, ""))
            question = data.get(self.input_key, "")
            logger.info(f"[RAG链] 构建提示词，上下文长度 {context_length}")
            print(f"📝 [提示词构建] 上下文: {context_length} 字符, 问题: {len(str(question))} 字符")
            return data

        def log_llm_start(data: Dict) -> Dict:
            """记录LLM开始"""
            logger.info(f"[RAG链] 开始LLM生成")
            print(f"🤖 [LLM生成] 正在调用模型生成回答...")
            return data

        # 构建链
        self.chain = (
            RunnableParallel({
                self.context_key: (
                    RunnableLambda(lambda x: x[self.input_key] if isinstance(x, dict) else x)
                    | self.retriever
                    | RunnableLambda(log_retrieval)
                ),
                self.input_key: RunnablePassthrough(),
            })
            | RunnableLambda(log_prompt)
            | RunnableLambda(log_llm_start)
            | self.prompt
            | self.llm
            | StrOutputParser()
        )

    def invoke(self, input: Union[str, Dict], **kwargs) -> str:
        if isinstance(input, str):
            input = {self.input_key: input}

        question = input.get(self.input_key, str(input))
        logger.info(f"[RAG链] 开始执行查询: {question[:80]}...")
        print(f"\n🚀 [RAG开始] 查询: {question[:80]}...")
        print("=" * 80)

        start = time.time()
        result = self.chain.invoke(input, **kwargs)
        elapsed = time.time() - start

        logger.info(f"[RAG链] 查询完成，回答长度: {len(result)} 字符，耗时: {elapsed:.2f}s")
        print("=" * 80)
        print(f"✅ [RAG完成] 回答长度: {len(result)} 字符，总耗时: {elapsed:.2f}s\n")
        return result

    async def ainvoke(self, input: Union[str, Dict], **kwargs) -> str:
        if isinstance(input, str):
            input = {self.input_key: input}

        question = input.get(self.input_key, str(input))
        logger.info(f"[RAG链] 开始异步执行查询: {question[:80]}...")
        print(f"\n🚀 [RAG开始] 异步查询: {question[:80]}...")
        print("=" * 80)

        start = time.time()
        result = await self.chain.ainvoke(input, **kwargs)
        elapsed = time.time() - start

        logger.info(f"[RAG链] 异步查询完成，回答长度: {len(result)} 字符，耗时: {elapsed:.2f}s")
        print("=" * 80)
        print(f"✅ [RAG完成] 回答长度: {len(result)} 字符，总耗时: {elapsed:.2f}s\n")
        return result

    def get_relevant_documents(self, query: str) -> List:
        """获取相关文档（不生成答案）"""
        return self.retriever.get_relevant_documents(query)

    def __call__(self, input: Union[str, Dict], **kwargs) -> str:
        """支持直接调用"""
        return self.invoke(input, **kwargs)


class SimpleRAGChain(RAGChain):
    """简化版RAG链"""

    def __init__(
        self,
        retriever: BaseRetriever,
        llm: BaseChatModel = None,
        **kwargs,
    ):
        system_prompt = """你是一个智能助手，基于提供的上下文回答问题。
始终基于上下文进行回答，如果上下文中没有相关信息，请明确指出。"""
        super().__init__(
            retriever=retriever,
            llm=llm,
            system_prompt=system_prompt,
            **kwargs,
        )


class ConversationalRAGChain(RAGChain):
    """对话式RAG链 - 支持多轮对话"""

    def __init__(
        self,
        retriever: BaseRetriever,
        llm: BaseChatModel = None,
        **kwargs,
    ):
        super().__init__(retriever=retriever, llm=llm, **kwargs)

    def _build_chain(self):
        """构建支持对话历史的链"""
        from langchain_core.messages import HumanMessage, AIMessage

        def get_chat_history(chat_history: List) -> List:
            """格式化对话历史"""
            formatted = []
            for msg in chat_history:
                if msg["type"] == "human":
                    formatted.append(HumanMessage(content=msg["content"]))
                else:
                    formatted.append(AIMessage(content=msg["content"]))
            return formatted

        def format_docs(docs: List) -> str:
            return "\n\n".join(doc.page_content for doc in docs)

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个智能助手，基于提供的上下文和对话历史回答问题。"),
            ("placeholder", "{chat_history}"),
            ("human", "上下文:\n{context}\n\n问题: {question}"),
        ])

        self.chain = (
            RunnableParallel({
                "context": self.retriever | RunnableLambda(format_docs),
                "question": RunnablePassthrough(),
                "chat_history": RunnablePassthrough(),
            })
            | prompt
            | self.llm
            | StrOutputParser()
        )

    def invoke(self, input: Union[str, Dict], **kwargs) -> str:
        if isinstance(input, str):
            input = {
                "question": input,
                "chat_history": kwargs.pop("chat_history", []),
            }
        return self.chain.invoke(input, **kwargs)


# 工厂函数
def create_rag_chain(
    retriever: BaseRetriever,
    llm_type: str = None,
    chain_type: str = "simple",
    **kwargs,
) -> RAGChain:
    """
    创建RAG链

    Args:
        retriever: 检索器
        llm_type: LLM类型，"openai", "deepseek", "ollama"
        chain_type: 链类型，"simple", "conversational"
        **kwargs: 其他参数

    Returns:
        RAGChain实例
    """
    if llm_type:
        config.LLM_PROVIDER = llm_type

    if chain_type == "simple":
        return SimpleRAGChain(retriever=retriever, **kwargs)
    elif chain_type == "conversational":
        return ConversationalRAGChain(retriever=retriever, **kwargs)
    else:
        return RAGChain(retriever=retriever, **kwargs)


if __name__ == "__main__":
    print("RAGChain模块已就绪")

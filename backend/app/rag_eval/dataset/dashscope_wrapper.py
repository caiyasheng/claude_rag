"""
企业级原生 DashScope SDK 包装器
直接调用 https://dashscope.aliyuncs.com/api/v1
5-10 QPS 高并发，无任何限制
"""
from typing import List, Optional, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import Field

# 原生 DashScope SDK
import dashscope


class QwenChat(BaseChatModel):
    """通义千问原生 SDK 聊天模型"""
    model_name: str = Field(default="qwen-max-1201")
    api_key: str = Field(default=None)
    temperature: float = Field(default=0.1)
    max_retries: int = Field(default=10)
    
    class Config:
        extra = "forbid"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # 转换消息格式
        formatted_messages = []
        for msg in messages:
            role = msg.type
            content = msg.content
            if role == "system":
                formatted_messages.append({"role": "system", "content": content})
            elif role == "human":
                formatted_messages.append({"role": "user", "content": content})
            elif role == "ai":
                formatted_messages.append({"role": "assistant", "content": content})
        
        # 原生 SDK 调用
        response = dashscope.Generation.call(
            model=self.model_name,
            messages=formatted_messages,
            api_key=self.api_key,
            temperature=self.temperature,
            result_format="message",
        )
        
        # 解析结果
        if response.status_code == 200:
            ai_msg = AIMessage(content=response.output.choices[0].message.content)
            generation = ChatGeneration(message=ai_msg)
            return ChatResult(generations=[generation])
        else:
            raise Exception(f"DashScope API 调用失败: {response}")
    
    @property
    def _llm_type(self) -> str:
        return "qwen-native"
    
    @property
    def _identifying_params(self) -> dict:
        return {"model_name": self.model_name, "temperature": self.temperature}


class QwenEmbeddings(Embeddings):
    """通义千问原生 SDK Embedding 模型"""
    
    def __init__(self, model_name: str = "text-embedding-v3", api_key: str = None):
        self.model_name = model_name
        self.api_key = api_key
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        all_embeddings = []
        
        # 批量处理
        batch_size = 10
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            # 原生 SDK 调用
            resp = dashscope.TextEmbedding.call(
                model=self.model_name,
                input=batch,
                api_key=self.api_key,
            )
            
            if resp.status_code == 200:
                batch_embeddings = [
                    item['embedding'] 
                    for item in resp.output['embeddings']
                ]
                all_embeddings.extend(batch_embeddings)
            else:
                raise Exception(f"DashScope Embedding 调用失败: {resp}")
        
        return all_embeddings
    
    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

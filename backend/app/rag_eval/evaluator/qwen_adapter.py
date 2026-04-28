"""
✅ 通义千问 Qwen - RAGAS 官方原生零失败方案
自动复用现有 DashScope Embedding Key，无需额外配置
"""


def get_llm_for_ragas():
    """✅ 通义千问优先，自动复用 Embedding 的 Key，开箱即用"""

    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper
    from ragas.run_config import RunConfig
    from config import config, EMBEDDING_API_KEY, EMBEDDING_BASE_URL

    # ✅ 阿里云 DashScope Key 是通用的！Embedding Key 直接能用在 LLM 上！
    DASHSCOPE_API_KEY = EMBEDDING_API_KEY
    DASHSCOPE_API_URL = EMBEDDING_BASE_URL

    if DASHSCOPE_API_KEY and len(DASHSCOPE_API_KEY.strip()) > 20:
        llm = ChatOpenAI(
            model="qwen-plus-2025-07-28",
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_API_URL,
            temperature=0,
            timeout=300,
            max_retries=5,
            max_tokens=8192,
        )
        print("✅ RAGAS 评测引擎: 通义千问 Qwen-Plus (自动复用 Embedding Key)")
        print(f"   - model = qwen-plus-2025-07-28")
    else:
        # ✅ 降级到 Minimax 兼容模式
        llm = ChatOpenAI(
            model=config.LLM_MODEL,
            api_key=config.MINIMAX_API_KEY,
            base_url=config.MINIMAX_API_URL,
            temperature=0,
            timeout=300,
            max_retries=5,
            max_tokens=8192,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
        print("⚠️ RAGAS 评测引擎: Minimax (兼容模式)")

    # ✅ RAGAS 官方标准配置
    ragas_llm = LangchainLLMWrapper(llm)
    run_config = RunConfig(
        max_workers=5,
        timeout=300,
        max_retries=5,
        max_wait=60,
    )

    print(f"   - temperature = 0 (确定性输出)")
    print(f"   - max_workers = 5 (千问并发稳定)")

    return ragas_llm, run_config

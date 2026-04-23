"""
快速测试脚本
"""
from loader import load_documents
from chunker import chunk_documents
from embedding import create_embeddings
from vectorstore import create_vectorstore

# 1. 加载文档
print("1. 加载文档...")
docs = load_documents("./data/云冈石窟.txt")
print(f"   加载了 {len(docs)} 个文档")

# 2. 分块
print("2. 分块...")
chunks = chunk_documents(docs, strategy="recursive", chunk_size=500, chunk_overlap=50)
print(f"   分成了 {len(chunks)} 个块")

# 3. 嵌入
print("3. 创建嵌入模型...")
emb = create_embeddings(provider="huggingface", model="BAAI/bge-small-zh")
vec = emb.embed_query("测试")
print(f"   嵌入维度: {len(vec)}")

# 4. 向量存储
print("4. 创建向量存储...")
vs = create_vectorstore(
    provider="chroma",
    embeddings=emb,
    documents=chunks,
    persist_directory="./test_vectorstore",
)

# 5. 搜索
print("5. 搜索测试...")
results = vs.search("云冈石窟的历史", k=2)
print(f"   找到 {len(results)} 个结果")
for i, doc in enumerate(results):
    print(f"\n   --- 结果 {i+1} ---")
    print(f"   {doc.page_content[:100]}...")

print("\n✅ 测试完成!")

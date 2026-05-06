# RAG 评测系统 - 待完成任务

## 项目背景
- 路径: `/Users/shengjia/PycharmProjects/claude_rag`
- 评测模块: `backend/app/rag_eval/`
- 当前已完成: 检索层+生成层分离评测、测试集RAGAS生成

---

## 已完成 ✅

### 1. 检索层 + 生成层分离评测
- **新增**: `evaluator/retrieval_eval.py` - 检索层评测（HitRate@K, Recall, Precision, F1, MAP@K, NDCG@K）
- **新增**: `evaluator/deep_eval.py` - 生成层评测（DeepEval: AnswerCorrectness, Faithfulness, AnswerRelevancy, ContextualPrecision, ContextualRecall）
- **改造**: `main.py` - 支持分离评测流程
- **改造**: `api.py` - 支持 k, run_retrieval, run_generation 参数
- **改造**: `report/generator.py` - 检索层+生成层双维度报告
- **golden_context 格式**: 支持多片段 list，用于 multi-hop/跨文档场景
- **重要**: golden_context 来自 RAGAS 测试集（真实知识库），禁止自行生成

### 2. 测试集生成改造
- **新增**: `dataset/ragas_generator.py` - 使用 RAGAS 生成三元组 (question, golden_context, golden_answer)
- **删除**: `dataset/generator.py` - 旧随机生成已删除
- **改造**: `api.py` - 直接使用 RAGAS，不再支持旧方法

---

## 未完成 ❌（本次讨论确认先不做）

### 1. 知识库质量评估
- 评估维度：需求完整性、无多版本冲突、无重复需求、PRD时效性、安全合规性
- 挑战：上线后一直不动的需求、后续优化/重构逻辑的知识库维护
- 状态：用户说先不做

### 2. 归因诊断升级（行业Judge Model）
- 从"阈值判断"升级为"行业Judge标注"
- 行业Judge Model（领域知识增强）- 用户说不知道是什么
- 自动判断类型：检索问题、生成问题、知识错误、过时信息、格式错误、多轮记忆丢失、地域性错误
- 聚类分析 → 定位根因
- 错题库 → 回流评测集与知识库
- 状态：用户说先不做

### 3. 离线 + 线上双看板
- 离线报告（保留）：HTML图表、CSV、JSON
- 实时监控（新增）：分钟级RAG效果看板、全链路指标（query→检索→排序→生成）
- 业务维度下钻（场景/模块/接口/模型版本）
- 状态：用户说先不做

---

## 本次实现的核心流程

```
测试集 (question + golden_answer + golden_context[多个片段])
       ↓
1. RAG 检索+生成 → EvalRecord.result
       ↓
2. 检索层评测（使用测试集自带的 golden_context）
   - 计算: HitRate@K, Recall, Precision, F1, MAP@K, NDCG@K
   - 多跳场景: 只要有一个片段匹配即算命中
   - ⚠️ golden_context 来自测试集，不自行生成
       ↓
3. 生成层评测（DeepEval）
   - AnswerCorrectness, Faithfulness, AnswerRelevancy,
   - ContextualPrecision, ContextualRecall
       ↓
4. 归因诊断（阈值判断）
       ↓
5. 生成报告（HTML/CSV/JSON）
```

---

## API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/eval/dataset/generate?max_samples=50` | 生成测试集（RAGAS） |
| POST | `/eval/run?max_samples=10&k=4&run_retrieval=true&run_generation=true` | 运行分离评测 |
| GET | `/eval/reports` | 获取报告列表 |
| GET | `/eval/report/view/{report_id}` | 查看HTML报告 |

---

## 依赖
- `deepeval>=0.21.0` - 已加入 requirements.txt
- `ragas>=0.2.0` - 已加入 requirements.txt

---

## 配置文件
- `backend/app/rag_eval/config.py` - 评测配置
- `backend/app/config.py` - LLM/Embedding 配置
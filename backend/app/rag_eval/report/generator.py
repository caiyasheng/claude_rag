"""
HTML 报告生成器 - 支持检索层 + 生成层分离评测
"""
import os
import json
from datetime import datetime
from typing import List, Optional
from app.rag_eval.schemas import EvalRecord


def generate_html_report(records: List[EvalRecord], output_path: str) -> str:
    """生成漂亮的 HTML 评测报告（检索层 + 生成层）"""

    total = len(records)
    success = sum(1 for r in records if r.is_success())
    failed = total - success

    # 解析检索层指标
    retrieval_metrics = []
    for r in records:
        if "retrieval_metrics" in r.metadata and r.metadata["retrieval_metrics"]:
            retrieval_metrics.append(r.metadata["retrieval_metrics"])

    retrieval_avg = {}
    if retrieval_metrics:
        for key in ["hit_rate_at_k", "recall", "precision", "f1", "map_at_k", "ndcg_at_k"]:
            vals = [getattr(m, key, None) for m in retrieval_metrics if getattr(m, key, None) is not None]
            if vals:
                retrieval_avg[key] = round(sum(vals) / len(vals), 4)

    # 解析生成层指标
    valid_scores = [r for r in records if r.scores]
    generation_avg = {}
    if valid_scores:
        for key in ["answer_correctness", "faithfulness", "answer_relevancy", "contextual_precision", "contextual_recall"]:
            vals = [r.scores.get(key) for r in valid_scores if r.scores.get(key) is not None]
            if vals:
                generation_avg[key] = round(sum(vals) / len(vals), 4)

    # 问题分布
    issue_dist = {}
    for r in records:
        for issue in r.issues:
            issue_dist[issue] = issue_dist.get(issue, 0) + 1

    # 明细行
    rows_html = ""
    for idx, r in enumerate(records):
        status_color = "#10b981" if r.is_success() else "#ef4444"
        status_text = "成功" if r.is_success() else "失败"

        # 检索层指标
        retrieval_html = ""
        if "retrieval_metrics" in r.metadata and r.metadata["retrieval_metrics"]:
            rm = r.metadata["retrieval_metrics"]
            for key in ["hit_rate_at_k", "recall", "precision", "ndcg_at_k"]:
                v = getattr(rm, key, None)
                if v is not None:
                    color = "#10b981" if v >= 0.8 else "#f59e0b" if v >= 0.6 else "#ef4444"
                    label = key.replace("_", " ")
                    retrieval_html += f'<span style="display:inline-block;padding:2px 6px;background:{color}20;color:{color};border-radius:10px;margin:2px;font-size:11px">{label}: {v:.3f}</span>'

        # 生成层指标
        generation_html = ""
        if r.scores:
            for k, v in r.scores.items():
                if v is not None:
                    color = "#10b981" if v >= 0.8 else "#f59e0b" if v >= 0.6 else "#ef4444"
                    generation_html += f'<span style="display:inline-block;padding:2px 6px;background:{color}20;color:{color};border-radius:10px;margin:2px;font-size:11px">{k}: {v:.3f}</span>'

        issues_html = ""
        for issue in r.issues:
            color_map = {
                "检索质量低": "#ef4444",
                "召回不足": "#f59e0b",
                "幻觉": "#3b82f6",
                "答非所问": "#8b5cf6",
                "答案错误": "#ef4444",
                "正常": "#10b981",
            }
            color = color_map.get(issue, "#6b7280")
            issues_html += f'<span style="display:inline-block;padding:2px 6px;background:{color}20;color:{color};border-radius:10px;margin:2px;font-size:11px">{issue}</span>'

        rows_html += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{idx+1}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;max-width:200px">
                <div style="font-weight:500;font-size:13px">{r.sample.question[:60]}{'...' if len(r.sample.question) > 60 else ''}</div>
            </td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb"><span style="color:{status_color};font-size:12px">{status_text}</span></td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{retrieval_html or '-'}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{generation_html or '-'}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{issues_html or '-'}</td>
        </tr>
        """

    # 检索层指标数据
    retrieval_labels = ["hit_rate_at_k", "recall", "precision", "f1", "map_at_k", "ndcg_at_k"]
    retrieval_data = [retrieval_avg.get(k, 0) for k in retrieval_labels]

    # 生成层指标数据
    gen_labels = ["answer_correctness", "faithfulness", "answer_relevancy", "contextual_precision", "contextual_recall"]
    gen_data = [generation_avg.get(k, 0) for k in gen_labels]

    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAG 评测报告 - 检索层 + 生成层</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f8fafc; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: white; padding: 24px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .header h1 {{ margin: 0; font-size: 24px; color: #1e293b; }}
        .header .time {{ color: #64748b; margin-top: 8px; }}
        .section {{ background: white; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .section h2 {{ margin: 0 0 16px 0; font-size: 18px; color: #1e293b; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }}
        .stats-row {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 20px; }}
        .stat-card {{ background: white; padding: 16px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat-val {{ font-size: 28px; font-weight: 700; }}
        .stat-label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
        .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
        .chart-card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .chart-card h3 {{ margin: 0 0 16px 0; font-size: 16px; color: #1e293b; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th {{ text-align: left; padding: 10px; border-bottom: 2px solid #e5e7eb; background: #f8fafc; color: #64748b; font-weight: 500; }}
        .layer-tag {{ display: inline-block; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 500; }}
        .layer-tag.retrieval {{ background: #dbeafe; color: #1d4ed8; }}
        .layer-tag.generation {{ background: #dcfce7; color: #15803d; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 RAG 系统评测报告</h1>
            <div class="time">生成时间: {time_str}</div>
        </div>

        <div class="stats-row">
            <div class="stat-card"><div class="stat-val">{total}</div><div class="stat-label">总样本数</div></div>
            <div class="stat-card"><div class="stat-val" style="color:#10b981">{success}</div><div class="stat-label">成功</div></div>
            <div class="stat-card"><div class="stat-val" style="color:#ef4444">{failed}</div><div class="stat-label">失败</div></div>
            <div class="stat-card"><div class="stat-val" style="color:#3b82f6">{len(retrieval_avg)}</div><div class="stat-label">检索指标数</div></div>
            <div class="stat-card"><div class="stat-val" style="color:#8b5cf6">{len(generation_avg)}</div><div class="stat-label">生成指标数</div></div>
        </div>

        <div class="section">
            <h2>🔍 检索层指标</h2>
            <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:12px">
                <div style="text-align:center;padding:12px;background:#f0f9ff;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#3b82f6">{retrieval_avg.get('hit_rate_at_k', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">HitRate@K</div>
                </div>
                <div style="text-align:center;padding:12px;background:#f0f9ff;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#3b82f6">{retrieval_avg.get('recall', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">Recall</div>
                </div>
                <div style="text-align:center;padding:12px;background:#f0f9ff;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#3b82f6">{retrieval_avg.get('precision', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">Precision</div>
                </div>
                <div style="text-align:center;padding:12px;background:#f0f9ff;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#3b82f6">{retrieval_avg.get('f1', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">F1</div>
                </div>
                <div style="text-align:center;padding:12px;background:#f0f9ff;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#3b82f6">{retrieval_avg.get('map_at_k', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">MAP@K</div>
                </div>
                <div style="text-align:center;padding:12px;background:#f0f9ff;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#3b82f6">{retrieval_avg.get('ndcg_at_k', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">NDCG@K</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>📝 生成层指标 (DeepEval)</h2>
            <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px">
                <div style="text-align:center;padding:12px;background:#f0fdf4;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#16a34a">{generation_avg.get('answer_correctness', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">Answer Correctness</div>
                </div>
                <div style="text-align:center;padding:12px;background:#f0fdf4;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#16a34a">{generation_avg.get('faithfulness', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">Faithfulness</div>
                </div>
                <div style="text-align:center;padding:12px;background:#f0fdf4;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#16a34a">{generation_avg.get('answer_relevancy', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">Answer Relevancy</div>
                </div>
                <div style="text-align:center;padding:12px;background:#f0fdf4;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#16a34a">{generation_avg.get('contextual_precision', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">Contextual Precision</div>
                </div>
                <div style="text-align:center;padding:12px;background:#f0fdf4;border-radius:8px">
                    <div style="font-size:20px;font-weight:700;color:#16a34a">{generation_avg.get('contextual_recall', 0):.3f}</div>
                    <div style="font-size:11px;color:#64748b">Contextual Recall</div>
                </div>
            </div>
        </div>

        <div class="charts-row">
            <div class="chart-card">
                <h3>检索层 vs 生成层 指标对比</h3>
                <canvas id="metricsChart"></canvas>
            </div>
            <div class="chart-card">
                <h3>问题分布</h3>
                <canvas id="issuesChart"></canvas>
            </div>
        </div>

        <div class="section">
            <h2>明细详情</h2>
            <table>
                <thead>
                    <tr>
                        <th width="50">#</th>
                        <th>问题</th>
                        <th width="70">状态</th>
                        <th>检索层指标</th>
                        <th>生成层指标</th>
                        <th>诊断</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
    </div>

    <script>
    new Chart(document.getElementById('metricsChart'), {{
        type: 'bar',
        data: {{
            labels: ['HitRate@K', 'Recall', 'Precision', 'F1', 'MAP@K', 'NDCG@K', 'AnsCorrect', 'Faithful', 'AnsRel', 'CtxPrec', 'CtxRecall'],
            datasets: [{{
                label: '得分',
                data: {retrieval_data + gen_data},
                backgroundColor: ['#3b82f6','#3b82f6','#3b82f6','#3b82f6','#3b82f6','#3b82f6','#16a34a','#16a34a','#16a34a','#16a34a','#16a34a'],
            }}]
        }},
        options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, max: 1 }} }} }}
    }});

    new Chart(document.getElementById('issuesChart'), {{
        type: 'doughnut',
        data: {{
            labels: Object.keys({json.dumps(issue_dist)}),
            datasets: [{{
                data: Object.values({json.dumps(issue_dist)}),
                backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#6b7280'],
            }}]
        }},
        options: {{ responsive: true }}
    }});
    </script>
</body>
</html>
    """

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def generate_csv_report(records: List[EvalRecord], output_path: str) -> None:
    """生成 CSV 评测报告"""
    import csv

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "问题", "标准答案", "系统回答",
            # 检索层指标
            "HitRate@K", "Recall", "Precision", "F1", "MAP@K", "NDCG@K",
            # 生成层指标
            "AnswerCorrectness", "Faithfulness", "AnswerRelevancy", "ContextualPrecision", "ContextualRecall",
            # 诊断
            "问题诊断", "耗时(ms)"
        ])

        for r in records:
            # 检索层指标
            retrieval_metrics = r.metadata.get("retrieval_metrics")
            hit_rate = getattr(retrieval_metrics, "hit_rate_at_k", "") if retrieval_metrics else ""
            recall = getattr(retrieval_metrics, "recall", "") if retrieval_metrics else ""
            precision = getattr(retrieval_metrics, "precision", "") if retrieval_metrics else ""
            f1 = getattr(retrieval_metrics, "f1", "") if retrieval_metrics else ""
            map_k = getattr(retrieval_metrics, "map_at_k", "") if retrieval_metrics else ""
            ndcg_k = getattr(retrieval_metrics, "ndcg_at_k", "") if retrieval_metrics else ""

            # 生成层指标
            scores = r.scores or {}

            writer.writerow([
                r.sample.question,
                r.sample.golden_answer,
                r.result.answer if r.result else "",
                # 检索层
                hit_rate, recall, precision, f1, map_k, ndcg_k,
                # 生成层
                scores.get("answer_correctness", ""),
                scores.get("faithfulness", ""),
                scores.get("answer_relevancy", ""),
                scores.get("contextual_precision", ""),
                scores.get("contextual_recall", ""),
                # 诊断
                ", ".join(r.issues),
                r.metadata.get("latency", 0),
            ])


def generate_json_summary(records: List[EvalRecord], output_path: str) -> None:
    """生成 JSON 摘要"""
    import json

    total = len(records)
    success = sum(1 for r in records if r.is_success())

    # 检索层平均指标
    retrieval_metrics_list = [r.metadata.get("retrieval_metrics") for r in records if r.metadata.get("retrieval_metrics")]
    retrieval_avg = {}
    if retrieval_metrics_list:
        for key in ["hit_rate_at_k", "recall", "precision", "f1", "map_at_k", "ndcg_at_k"]:
            vals = [getattr(m, key, None) for m in retrieval_metrics_list if getattr(m, key, None) is not None]
            if vals:
                retrieval_avg[key] = sum(vals) / len(vals)

    # 生成层平均指标
    valid_scores = [r for r in records if r.scores]
    generation_avg = {}
    if valid_scores:
        for key in ["answer_correctness", "faithfulness", "answer_relevancy", "contextual_precision", "contextual_recall"]:
            vals = [r.scores.get(key) for r in valid_scores if r.scores.get(key) is not None]
            if vals:
                generation_avg[key] = sum(vals) / len(vals)

    # 问题分布
    issue_dist = {}
    for r in records:
        for issue in r.issues:
            issue_dist[issue] = issue_dist.get(issue, 0) + 1

    summary = {
        "total": total,
        "success": success,
        "failed": total - success,
        "retrieval_layer_avg": retrieval_avg,
        "generation_layer_avg": generation_avg,
        "issue_distribution": issue_dist,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
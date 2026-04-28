"""
HTML 报告生成器 - 单文件，带图表，可分享
"""
import os
import json
from datetime import datetime
from typing import List
from app.rag_eval.schemas import EvalRecord


def generate_html_report(records: List[EvalRecord], output_path: str) -> str:
    """生成漂亮的 HTML 评测报告"""

    total = len(records)
    success = sum(1 for r in records if r.is_success())
    failed = total - success

    valid_scores = [r for r in records if r.scores]
    avg_scores = {}
    if valid_scores:
        for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            vals = [r.scores.get(key) for r in valid_scores if r.scores.get(key) is not None]
            if vals:
                avg_scores[key] = round(sum(vals) / len(vals), 3)
            else:
                avg_scores[key] = None

    issue_dist = {}
    for r in records:
        for issue in r.issues:
            issue_dist[issue] = issue_dist.get(issue, 0) + 1

    rows_html = ""
    for idx, r in enumerate(records):
        status_color = "#10b981" if r.is_success() else "#ef4444"
        status_text = "成功" if r.is_success() else "失败"
        scores_html = ""
        if r.scores:
            for k, v in r.scores.items():
                if v is not None:
                    color = "#10b981" if v >= 0.8 else "#f59e0b" if v >= 0.6 else "#ef4444"
                    scores_html += f'<span style="display:inline-block;padding:2px 8px;background:{color}20;color:{color};border-radius:12px;margin:2px;font-size:12px">{k}: {v:.3f}</span>'
        issues_html = ""
        for issue in r.issues:
            color = {"retrieval": "#ef4444", "hallucination": "#f59e0b", "relevance": "#3b82f6", "ok": "#10b981"}.get(issue, "#6b7280")
            issues_html += f'<span style="display:inline-block;padding:2px 8px;background:{color}20;color:{color};border-radius:12px;margin:2px;font-size:12px">{issue}</span>'

        rows_html += f"""
        <tr>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb">{idx+1}</td>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb;max-width:300px">
                <div style="font-weight:500">{r.sample.question}</div>
                <div style="font-size:12px;color:#6b7280;margin-top:4px">标准答案: {r.sample.golden_answer[:50]}...</div>
            </td>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb"><span style="color:{status_color}">{status_text}</span></td>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb">{scores_html}</td>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb">{issues_html}</td>
        </tr>
        """

    scores_data = json.dumps(avg_scores)
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAG 评测报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f8fafc; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: white; padding: 24px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .header h1 {{ margin: 0; font-size: 24px; color: #1e293b; }}
        .header .time {{ color: #64748b; margin-top: 8px; }}
        .stats-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }}
        .stat-card {{ background: white; padding: 16px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat-val {{ font-size: 28px; font-weight: 700; }}
        .stat-label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
        .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
        .chart-card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .chart-card h3 {{ margin: 0 0 16px 0; font-size: 16px; color: #1e293b; }}
        .table-card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow-x: auto; }}
        .table-card h3 {{ margin: 0 0 16px 0; font-size: 16px; color: #1e293b; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ text-align: left; padding: 10px; border-bottom: 2px solid #e5e7eb; background: #f8fafc; color: #64748b; font-weight: 500; }}
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
            <div class="stat-card"><div class="stat-val">{round(success/total*100, 1) if total > 0 else 0}%</div><div class="stat-label">成功率</div></div>
        </div>

        <div class="charts-row">
            <div class="chart-card">
                <h3>平均指标得分</h3>
                <canvas id="scoresChart"></canvas>
            </div>
            <div class="chart-card">
                <h3>问题分布</h3>
                <canvas id="issuesChart"></canvas>
            </div>
        </div>

        <div class="table-card">
            <h3>明细详情</h3>
            <table>
                <thead><tr><th width="60">#</th><th>问题</th><th width="80">状态</th><th>指标</th><th>诊断</th></tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
    </div>

    <script>
    const scores = {scores_data};
    const issueData = {json.dumps(issue_dist)};

    new Chart(document.getElementById('scoresChart'), {{
        type: 'bar',
        data: {{
            labels: Object.keys(scores).filter(k => scores[k] !== null),
            datasets: [{{
                data: Object.values(scores).filter(v => v !== null),
                backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'],
            }}]
        }},
        options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, max: 1 }} }} }}
    }});

    new Chart(document.getElementById('issuesChart'), {{
        type: 'doughnut',
        data: {{
            labels: Object.keys(issueData),
            datasets: [{{
                data: Object.values(issueData),
                backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6'],
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
            "Faithfulness", "Answer Relevancy", "Context Precision", "Context Recall",
            "问题诊断", "耗时(ms)"
        ])

        for r in records:
            writer.writerow([
                r.sample.question,
                r.sample.golden_answer,
                r.result.answer if r.result else "",
                r.scores.get("faithfulness", "") if r.scores else "",
                r.scores.get("answer_relevancy", "") if r.scores else "",
                r.scores.get("context_precision", "") if r.scores else "",
                r.scores.get("context_recall", "") if r.scores else "",
                ", ".join(r.issues),
                r.metadata.get("latency", 0),
            ])


def generate_json_summary(records: List[EvalRecord], output_path: str) -> None:
    """生成 JSON 摘要"""
    import json

    summary = {
        "total": len(records),
        "success": sum(1 for r in records if r.is_success()),
        "failed": sum(1 for r in records if not r.is_success()),
        "avg_scores": {},
        "issue_distribution": {},
    }

    valid_scores = [r for r in records if r.scores]
    if valid_scores:
        for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            vals = [r.scores.get(key) for r in valid_scores if r.scores.get(key) is not None]
            if vals:
                summary["avg_scores"][key] = sum(vals) / len(vals)

    for r in records:
        for issue in r.issues:
            summary["issue_distribution"][issue] = summary["issue_distribution"].get(issue, 0) + 1

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

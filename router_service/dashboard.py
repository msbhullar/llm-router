"""
Computes cost-savings/routing-distribution/latency stats from the logged
routing decisions, and renders them as a self-contained HTML dashboard.
No external charting library — a handful of numbers doesn't need one.
"""

from router_service.config import CHEAP_MODEL, STRONG_MODEL
from router_service.logging_store import _collection


def _percentile(sorted_vals: list, pct: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(int(len(sorted_vals) * pct), len(sorted_vals) - 1)
    return sorted_vals[idx]


def compute_stats() -> dict:
    docs = list(
        _collection.find(
            {}, {"_id": 0, "model_used": 1, "estimated_cost_usd": 1, "baseline_cost_usd": 1, "latency_ms": 1}
        )
    )

    total_cost = sum(d["estimated_cost_usd"] for d in docs)
    total_baseline = sum(d["baseline_cost_usd"] for d in docs)
    savings = total_baseline - total_cost
    savings_pct = (savings / total_baseline * 100) if total_baseline else 0

    by_model: dict = {}
    for d in docs:
        entry = by_model.setdefault(d["model_used"], {"count": 0, "latencies": []})
        entry["count"] += 1
        entry["latencies"].append(d["latency_ms"])

    model_stats = {}
    for model, info in by_model.items():
        lat = sorted(info["latencies"])
        model_stats[model] = {
            "count": info["count"],
            "p50": _percentile(lat, 0.50),
            "p95": _percentile(lat, 0.95),
            "p99": _percentile(lat, 0.99),
        }

    return {
        "total_requests": len(docs),
        "total_cost": total_cost,
        "total_baseline": total_baseline,
        "savings": savings,
        "savings_pct": savings_pct,
        "model_stats": model_stats,
    }


def _bar_row(label: str, count: int, total: int, color_var: str) -> str:
    pct = (count / total * 100) if total else 0
    width = max(pct, 2) if count else 0  # keep a sliver visible even for tiny shares
    return f"""
    <div class="bar-row">
      <div class="bar-label">{label}</div>
      <div class="bar-track">
        <div class="bar-fill" style="width:{width:.1f}%; background:var({color_var});"></div>
      </div>
      <div class="bar-value">{count} ({pct:.0f}%)</div>
    </div>"""


def render_dashboard(stats: dict) -> str:
    total = stats["total_requests"]
    cheap_count = stats["model_stats"].get(CHEAP_MODEL, {}).get("count", 0)
    strong_count = stats["model_stats"].get(STRONG_MODEL, {}).get("count", 0)

    bars = _bar_row(f"Cheap — {CHEAP_MODEL}", cheap_count, total, "--series-1") + _bar_row(
        f"Strong — {STRONG_MODEL}", strong_count, total, "--series-2"
    )

    latency_rows = ""
    for model in (CHEAP_MODEL, STRONG_MODEL):
        s = stats["model_stats"].get(model)
        if not s:
            continue
        latency_rows += f"""
        <tr>
          <td>{model}</td>
          <td>{s["p50"]}</td>
          <td>{s["p95"]}</td>
          <td>{s["p99"]}</td>
        </tr>"""

    empty_state = (
        '<p class="muted">No requests logged yet — call <code>POST /route</code> a few times, then refresh.</p>'
        if total == 0
        else ""
    )

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>LLM Router — Cost Savings Dashboard</title>
<style>
  :root {{
    color-scheme: light;
    --surface-1: #fcfcfb;
    --page: #f9f9f7;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --muted: #898781;
    --gridline: #e1e0d9;
    --border: rgba(11,11,11,0.10);
    --series-1: #2a78d6;
    --series-2: #eb6834;
    --success: #006300;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      color-scheme: dark;
      --surface-1: #1a1a19;
      --page: #0d0d0d;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --muted: #898781;
      --gridline: #2c2c2a;
      --border: rgba(255,255,255,0.10);
      --series-1: #3987e5;
      --series-2: #d95926;
      --success: #0ca30c;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 40px 24px;
    background: var(--page);
    color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  .wrap {{ max-width: 720px; margin: 0 auto; }}
  h1 {{ font-size: 20px; font-weight: 600; margin: 0 0 4px; }}
  .subtitle {{ color: var(--text-secondary); font-size: 14px; margin: 0 0 32px; }}
  .card {{
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
  }}
  .hero-label {{ color: var(--text-secondary); font-size: 13px; margin: 0 0 8px; }}
  .hero-value {{ font-size: 48px; font-weight: 600; color: var(--success); line-height: 1; margin: 0; }}
  .hero-sub {{ color: var(--text-secondary); font-size: 14px; margin: 8px 0 0; }}
  .stat-row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .stat-tile {{ flex: 1; min-width: 140px; }}
  .stat-tile .label {{ color: var(--text-secondary); font-size: 13px; margin: 0 0 4px; }}
  .stat-tile .value {{ font-size: 22px; font-weight: 600; margin: 0; }}
  h2 {{ font-size: 15px; font-weight: 600; margin: 0 0 16px; }}
  .legend {{ display: flex; gap: 16px; margin-bottom: 16px; font-size: 13px; color: var(--text-secondary); }}
  .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
  .swatch {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
  .bar-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
  .bar-label {{ width: 220px; font-size: 13px; color: var(--text-secondary); flex-shrink: 0; }}
  .bar-track {{ flex: 1; height: 24px; background: var(--gridline); border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px 0 0 4px; min-width: 2px; }}
  .bar-value {{ width: 90px; text-align: right; font-size: 13px; font-variant-numeric: tabular-nums; flex-shrink: 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ text-align: left; color: var(--muted); font-weight: 500; font-size: 12px; text-transform: uppercase;
        letter-spacing: 0.03em; padding: 0 0 8px; border-bottom: 1px solid var(--gridline); }}
  td {{ padding: 10px 0; border-bottom: 1px solid var(--gridline); font-variant-numeric: tabular-nums; }}
  td:not(:first-child), th:not(:first-child) {{ text-align: right; }}
  .muted {{ color: var(--muted); font-size: 14px; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>LLM Router — Cost Savings Dashboard</h1>
    <p class="subtitle">Live stats from every routing decision logged to MongoDB.</p>

    {empty_state}

    <div class="card">
      <p class="hero-label">Total cost savings vs. always using the strongest model</p>
      <p class="hero-value">${stats["savings"]:.4f}</p>
      <p class="hero-sub">{stats["savings_pct"]:.1f}% cheaper than the naive baseline, across {total} requests</p>
    </div>

    <div class="card">
      <div class="stat-row">
        <div class="stat-tile">
          <p class="label">Total requests</p>
          <p class="value">{total}</p>
        </div>
        <div class="stat-tile">
          <p class="label">Actual cost incurred</p>
          <p class="value">${stats["total_cost"]:.4f}</p>
        </div>
        <div class="stat-tile">
          <p class="label">Baseline cost (always strong)</p>
          <p class="value">${stats["total_baseline"]:.4f}</p>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Routing distribution</h2>
      <div class="legend">
        <span><span class="swatch" style="background:var(--series-1)"></span>Cheap tier</span>
        <span><span class="swatch" style="background:var(--series-2)"></span>Strong tier</span>
      </div>
      {bars}
    </div>

    <div class="card">
      <h2>Latency percentiles by model (ms)</h2>
      <table>
        <tr><th>Model</th><th>p50</th><th>p95</th><th>p99</th></tr>
        {latency_rows}
      </table>
    </div>
  </div>
</body>
</html>"""

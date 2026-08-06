"""
Interactive demo page served at GET /. Lets a visitor type a query, submit
it to POST /route via fetch(), and see the routing decision rendered
visually — which tier was picked, the answer, cost, and latency. Purely
for demo purposes; not part of the original spec's Section 4 API surface.
"""

from router_service.config import CHEAP_MODEL, STRONG_MODEL


def render_demo() -> str:
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>LLM Router — Try it live</title>
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
  .wrap {{ max-width: 640px; margin: 0 auto; }}
  h1 {{ font-size: 20px; font-weight: 600; margin: 0 0 4px; }}
  .subtitle {{ color: var(--text-secondary); font-size: 14px; margin: 0 0 8px; }}
  a.nav {{ color: var(--series-1); font-size: 13px; text-decoration: none; }}
  a.nav:hover {{ text-decoration: underline; }}
  .card {{
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-top: 24px;
  }}
  textarea {{
    width: 100%;
    min-height: 80px;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid var(--gridline);
    background: var(--page);
    color: var(--text-primary);
    font-family: inherit;
    font-size: 14px;
    resize: vertical;
  }}
  .chips {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }}
  .chip {{
    font-size: 12px;
    color: var(--text-secondary);
    background: var(--page);
    border: 1px solid var(--gridline);
    border-radius: 999px;
    padding: 6px 12px;
    cursor: pointer;
  }}
  .chip:hover {{ border-color: var(--series-1); color: var(--series-1); }}
  button.submit {{
    background: var(--series-1);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }}
  button.submit:disabled {{ opacity: 0.5; cursor: default; }}
  .result {{ display: none; }}
  .result.show {{ display: block; }}
  .badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    color: white;
    margin-bottom: 16px;
  }}
  .answer {{ font-size: 15px; line-height: 1.6; white-space: pre-wrap; margin: 0 0 20px; }}
  .stat-row {{ display: flex; gap: 24px; flex-wrap: wrap; border-top: 1px solid var(--gridline); padding-top: 16px; }}
  .stat {{ }}
  .stat .label {{ color: var(--muted); font-size: 12px; margin: 0 0 4px; }}
  .stat .value {{ font-size: 15px; font-weight: 600; margin: 0; font-variant-numeric: tabular-nums; }}
  .loading {{ color: var(--text-secondary); font-size: 14px; }}
  .error {{ color: #d03b3b; font-size: 14px; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>LLM Router — Try it live</h1>
    <p class="subtitle">Type a query. Watch it get routed to the cheap or strong model based on difficulty.</p>
    <a class="nav" href="/dashboard">View cost-savings dashboard &rarr;</a>

    <div class="card">
      <textarea id="query" placeholder="Ask something easy, or something that needs real reasoning...">What is the capital of Japan?</textarea>
      <div class="chips">
        <span class="chip" data-q="What is the capital of Japan?">Easy: capital of Japan</span>
        <span class="chip" data-q="A robe takes 2 bolts of blue fiber and half that much white fiber. How many bolts in total does it take?">Hard: fiber word problem</span>
        <span class="chip" data-q="What color is the sky?">Easy: sky color</span>
        <span class="chip" data-q="Compare the tradeoffs between REST and GraphQL APIs, and explain when you would choose one over the other.">Hard: REST vs GraphQL</span>
      </div>
      <button class="submit" id="submitBtn" onclick="submitQuery()">Route this query</button>
    </div>

    <div class="card result" id="resultCard">
      <div id="badge"></div>
      <p class="answer" id="answerText"></p>
      <div class="stat-row">
        <div class="stat"><p class="label">Difficulty score</p><p class="value" id="statDifficulty"></p></div>
        <div class="stat"><p class="label">Estimated cost</p><p class="value" id="statCost"></p></div>
        <div class="stat"><p class="label">Latency</p><p class="value" id="statLatency"></p></div>
      </div>
    </div>
  </div>

<script>
  const CHEAP_MODEL = {CHEAP_MODEL!r};
  const STRONG_MODEL = {STRONG_MODEL!r};

  document.querySelectorAll('.chip').forEach(chip => {{
    chip.addEventListener('click', () => {{
      document.getElementById('query').value = chip.dataset.q;
      submitQuery();
    }});
  }});

  async function submitQuery() {{
    const query = document.getElementById('query').value.trim();
    if (!query) return;

    const btn = document.getElementById('submitBtn');
    const resultCard = document.getElementById('resultCard');
    btn.disabled = true;
    btn.textContent = 'Routing...';
    resultCard.classList.remove('show');

    try {{
      const res = await fetch('/route', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{query}}),
      }});
      if (!res.ok) throw new Error('Request failed: ' + res.status);
      const data = await res.json();

      const isCheap = data.model_used === CHEAP_MODEL;
      const badge = document.getElementById('badge');
      badge.innerHTML = `<span class="badge" style="background:${{isCheap ? 'var(--series-1)' : 'var(--series-2)'}}">` +
        `${{isCheap ? 'CHEAP TIER' : 'STRONG TIER'}} &middot; ${{data.model_used}}</span>`;

      document.getElementById('answerText').textContent = data.answer.replace(/\*\*(.*?)\*\*/g, '$1').replace(/\*(.*?)\*/g, '$1');
      document.getElementById('statDifficulty').textContent = data.difficulty_score.toFixed(3);
      document.getElementById('statCost').textContent = '$' + data.estimated_cost.toFixed(6);
      document.getElementById('statLatency').textContent = data.latency_ms + ' ms';

      resultCard.classList.add('show');
    }} catch (err) {{
      const badge = document.getElementById('badge');
      badge.innerHTML = '';
      document.getElementById('answerText').innerHTML = `<span class="error">Error: ${{err.message}}</span>`;
      document.getElementById('statDifficulty').textContent = '—';
      document.getElementById('statCost').textContent = '—';
      document.getElementById('statLatency').textContent = '—';
      resultCard.classList.add('show');
    }} finally {{
      btn.disabled = false;
      btn.textContent = 'Route this query';
    }}
  }}
</script>
</body>
</html>"""

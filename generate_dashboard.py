import json
import os
import base64
from datetime import datetime, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Metric, Dimension, OrderBy
)
from google.oauth2 import service_account

PROPERTY_ID = "543326297"

def get_ga4_credentials():
    key_b64 = os.environ["GA4_KEY_JSON"]
    key_json = base64.b64decode(key_b64).decode("utf-8")
    key_dict = json.loads(key_json)
    return service_account.Credentials.from_service_account_info(
        key_dict,
        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )

def fetch_data():
    credentials = get_ga4_credentials()
    client = BetaAnalyticsDataClient(credentials=credentials)

    ranges = {
        "7d": DateRange(start_date="7daysAgo", end_date="today"),
        "30d": DateRange(start_date="30daysAgo", end_date="today"),
    }

    data = {}

    for key, date_range in ranges.items():
        # Overview metrics
        overview = client.run_report(RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            date_ranges=[date_range],
            metrics=[
                Metric(name="sessions"),
                Metric(name="activeUsers"),
                Metric(name="bounceRate"),
                Metric(name="averageSessionDuration"),
            ]
        ))
        row = overview.rows[0].metric_values
        avg_dur_s = int(float(row[3].value))

        # Daily sessions trend
        trend = client.run_report(RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            date_ranges=[date_range],
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="sessions"), Metric(name="activeUsers")],
            order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))]
        ))
        daily = [
            {
                "date": r.dimension_values[0].value,
                "sessions": int(r.metric_values[0].value),
                "users": int(r.metric_values[1].value)
            }
            for r in trend.rows
        ]

        # Top pages
        pages = client.run_report(RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            date_ranges=[date_range],
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="sessions")],
            limit=8
        ))
        top_pages = [
            {"page": r.dimension_values[0].value, "sessions": int(r.metric_values[0].value)}
            for r in pages.rows
        ]

        # Traffic sources
        sources = client.run_report(RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            date_ranges=[date_range],
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions")],
            limit=6
        ))
        traffic_sources = [
            {"source": r.dimension_values[0].value, "sessions": int(r.metric_values[0].value)}
            for r in sources.rows
        ]

        data[key] = {
            "sessions": int(row[0].value),
            "users": int(row[1].value),
            "bounce_rate": round(float(row[2].value) * 100, 1),
            "avg_session": f"{avg_dur_s // 60}m {avg_dur_s % 60}s",
            "daily": daily,
            "top_pages": top_pages,
            "traffic_sources": traffic_sources,
        }

    return data

def build_html(data):
    updated = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
    data_json = json.dumps(data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Site analytics — caryncampelo.com</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f3; color: #1a1a1a; min-height: 100vh; }}
  header {{ background: #fff; border-bottom: 1px solid #e5e5e5; padding: 1rem 2rem; display: flex; align-items: center; justify-content: space-between; }}
  header h1 {{ font-size: 16px; font-weight: 500; }}
  header p {{ font-size: 12px; color: #888; }}
  .toggle {{ display: flex; gap: 0; border: 1px solid #e5e5e5; border-radius: 8px; overflow: hidden; }}
  .toggle button {{ padding: 6px 16px; font-size: 13px; border: none; background: #fff; cursor: pointer; color: #555; transition: background 0.15s; }}
  .toggle button.active {{ background: #185FA5; color: #fff; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 2rem; }}
  .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 1.5rem; }}
  .metric {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 10px; padding: 1rem 1.25rem; }}
  .metric-label {{ font-size: 11px; color: #888; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.04em; }}
  .metric-val {{ font-size: 26px; font-weight: 500; }}
  .charts {{ display: grid; grid-template-columns: 2fr 1fr; gap: 12px; margin-bottom: 1.5rem; }}
  .card {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 10px; padding: 1.25rem; }}
  .card h2 {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 1rem; font-weight: 500; }}
  .bottom {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .bar-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }}
  .bar-name {{ font-size: 12px; color: #555; width: 120px; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .bar-track {{ flex: 1; height: 6px; background: #f0f0ee; border-radius: 3px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 3px; background: #378ADD; }}
  .bar-num {{ font-size: 12px; color: #1a1a1a; width: 40px; text-align: right; flex-shrink: 0; font-weight: 500; }}
  .source-row {{ display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0ee; }}
  .source-row:last-child {{ border-bottom: none; }}
  .source-name {{ font-size: 13px; color: #555; }}
  .source-num {{ font-size: 13px; font-weight: 500; }}
  footer {{ text-align: center; padding: 2rem; font-size: 11px; color: #bbb; }}
  @media (max-width: 700px) {{
    .metrics {{ grid-template-columns: repeat(2, 1fr); }}
    .charts, .bottom {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<header>
  <div>
    <h1>caryncampelo.com &mdash; analytics</h1>
    <p>Last updated: {updated}</p>
  </div>
  <div class="toggle">
    <button class="active" onclick="setRange('7d', this)">7 days</button>
    <button onclick="setRange('30d', this)">30 days</button>
  </div>
</header>

<main>
  <div class="metrics">
    <div class="metric"><div class="metric-label">Sessions</div><div class="metric-val" id="m-sessions">—</div></div>
    <div class="metric"><div class="metric-label">Visitors</div><div class="metric-val" id="m-users">—</div></div>
    <div class="metric"><div class="metric-label">Bounce rate</div><div class="metric-val" id="m-bounce">—</div></div>
    <div class="metric"><div class="metric-label">Avg. session</div><div class="metric-val" id="m-duration">—</div></div>
  </div>

  <div class="charts">
    <div class="card">
      <h2>Sessions over time</h2>
      <canvas id="trendChart" height="160"></canvas>
    </div>
    <div class="card">
      <h2>Traffic sources</h2>
      <canvas id="sourceChart" height="160"></canvas>
    </div>
  </div>

  <div class="bottom">
    <div class="card">
      <h2>Top pages</h2>
      <div id="pages-list"></div>
    </div>
    <div class="card">
      <h2>Channel breakdown</h2>
      <div id="sources-list"></div>
    </div>
  </div>
</main>

<footer>Auto-generated by your analytics agent &middot; Powered by Claude</footer>

<script>
const DATA = {data_json};
let trendChart, sourceChart;
let currentRange = '7d';

function setRange(range, btn) {{
  currentRange = range;
  document.querySelectorAll('.toggle button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  render(range);
}}

function fmt(n) {{ return n.toLocaleString(); }}

function render(range) {{
  const d = DATA[range];

  document.getElementById('m-sessions').textContent = fmt(d.sessions);
  document.getElementById('m-users').textContent = fmt(d.users);
  document.getElementById('m-bounce').textContent = d.bounce_rate + '%';
  document.getElementById('m-duration').textContent = d.avg_session;

  // Trend chart
  const labels = d.daily.map(r => {{
    const dt = r.date;
    return dt.slice(4,6) + '/' + dt.slice(6,8);
  }});
  const sessions = d.daily.map(r => r.sessions);
  const users = d.daily.map(r => r.users);

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(document.getElementById('trendChart'), {{
    type: 'line',
    data: {{
      labels,
      datasets: [
        {{ label: 'Sessions', data: sessions, borderColor: '#378ADD', backgroundColor: 'rgba(55,138,221,0.08)', tension: 0.3, fill: true, pointRadius: 2 }},
        {{ label: 'Visitors', data: users, borderColor: '#1D9E75', backgroundColor: 'rgba(29,158,117,0.08)', tension: 0.3, fill: true, pointRadius: 2 }}
      ]
    }},
    options: {{ plugins: {{ legend: {{ labels: {{ font: {{ size: 11 }} }} }} }}, scales: {{ x: {{ ticks: {{ font: {{ size: 10 }} }} }}, y: {{ ticks: {{ font: {{ size: 10 }} }} }} }} }}
  }});

  // Source donut
  const srcLabels = d.traffic_sources.map(s => s.source);
  const srcData = d.traffic_sources.map(s => s.sessions);
  const colors = ['#378ADD','#1D9E75','#D85A30','#7F77DD','#BA7517','#D4537E'];

  if (sourceChart) sourceChart.destroy();
  sourceChart = new Chart(document.getElementById('sourceChart'), {{
    type: 'doughnut',
    data: {{ labels: srcLabels, datasets: [{{ data: srcData, backgroundColor: colors, borderWidth: 1, borderColor: '#fff' }}] }},
    options: {{ plugins: {{ legend: {{ position: 'bottom', labels: {{ font: {{ size: 11 }}, padding: 10 }} }} }}, cutout: '60%' }}
  }});

  // Top pages bars
  const maxP = d.top_pages[0]?.sessions || 1;
  document.getElementById('pages-list').innerHTML = d.top_pages.map(p => `
    <div class="bar-row">
      <span class="bar-name" title="${{p.page}}">${{p.page}}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${{Math.round(p.sessions/maxP*100)}}%"></div></div>
      <span class="bar-num">${{fmt(p.sessions)}}</span>
    </div>`).join('');

  // Sources list
  document.getElementById('sources-list').innerHTML = d.traffic_sources.map(s => `
    <div class="source-row">
      <span class="source-name">${{s.source}}</span>
      <span class="source-num">${{fmt(s.sessions)}}</span>
    </div>`).join('');
}}

render('7d');
</script>
</body>
</html>"""

if __name__ == "__main__":
    print("Fetching GA4 data...")
    data = fetch_data()
    print("Building dashboard...")
    html = build_html(data)
    with open("index.html", "w") as f:
        f.write(html)
    print("Dashboard written to index.html")

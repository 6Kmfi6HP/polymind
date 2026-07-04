"""
Static gallery generator — produces an HTML gallery page for strategy templates.

Usage::

    from polymind.web.gallery import generate_gallery_html

    html = generate_gallery_html()
    with open("gallery.html", "w") as f:
        f.write(html)
"""

from __future__ import annotations

from polymind.templates import TemplateLibrary


def _template_card_html(info: object) -> str:
    """Render a single template card as HTML."""
    tags_html = " ".join(f'<span class="tag">{t}</span>' for t in info.tags[:4])
    params_items = "".join(
        f'<li><span class="key">{k}:</span> {v}</li>' for k, v in info.params.items()
    )

    return f"""
    <div class="card" onclick="showDetails('{info.name}')">
        <div class="card-header">
            <h3>{info.name}</h3>
            <span class="strategy-type">{info.strategy_type}</span>
        </div>
        <p class="description">{info.description}</p>
        <div class="tags">{tags_html}</div>
        <div class="params">
            <h4>Parameters</h4>
            <ul>{params_items}</ul>
        </div>
    </div>
    """


def _detail_modal_html(info: object) -> str:
    """Render a detail modal for a single template."""
    params_items = "".join(
        f'<li><span class="key">{k}:</span> {v}</li>' for k, v in info.params.items()
    )
    risk_items = "".join(
        f'<li><span class="key">{k}:</span> {v}</li>' for k, v in info.risk_limits.items()
    )

    return f"""
    <div id="modal-{info.name}" class="modal">
        <div class="modal-content">
            <span class="close" onclick="hideDetails('{info.name}')">&times;</span>
            <h2>{info.name}</h2>
            <p class="modal-desc">{info.description}</p>
            <p><strong>Type:</strong> {info.strategy_type}</p>
            <h3>Parameters</h3>
            <ul>{params_items}</ul>
            <h3>Risk Limits</h3>
            <ul>{risk_items}</ul>
            <h3>Tags</h3>
            <p>{', '.join(info.tags)}</p>
            <button onclick="navigator.clipboard.writeText(
                'polymind template run {info.name}'
            )">Copy deploy command</button>
        </div>
    </div>
    """


PAGE_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #0f1117; color: #e4e6eb; padding: 2rem; }
h1 { font-size: 2rem; margin-bottom: 0.5rem; }
.subtitle { color: #8b8d92; margin-bottom: 2rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
        gap: 1.5rem; }
.card { background: #1a1d27; border-radius: 12px; padding: 1.5rem;
        cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }
.card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
.card-header { display: flex; justify-content: space-between; align-items: center;
               margin-bottom: 0.75rem; }
.card-header h3 { font-size: 1.1rem; color: #58a6ff; }
.strategy-type { background: #21262d; padding: 0.2rem 0.6rem; border-radius: 4px;
                 font-size: 0.8rem; color: #8b949e; }
.description { font-size: 0.9rem; color: #8b8d92; margin-bottom: 1rem;
               line-height: 1.4; }
.tags { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 1rem; }
.tag { background: #1f2937; color: #58a6ff; padding: 0.15rem 0.5rem;
       border-radius: 8px; font-size: 0.75rem; }
.params { border-top: 1px solid #21262d; padding-top: 0.75rem; }
.params h4 { font-size: 0.85rem; color: #8b949e; margin-bottom: 0.5rem; }
.params ul { list-style: none; }
.params li { font-size: 0.8rem; padding: 0.15rem 0; }
.key { color: #58a6ff; }
.modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
         background: rgba(0,0,0,0.7); z-index: 1000; }
.modal-content { background: #1a1d27; margin: 5% auto; padding: 2rem; width: 90%;
                 max-width: 600px; border-radius: 12px; max-height: 80vh; overflow-y: auto; }
.close { float: right; font-size: 1.5rem; cursor: pointer; color: #8b949e; }
.modal-desc { color: #8b8d92; margin: 1rem 0; }
.modal h3 { color: #58a6ff; margin-top: 1rem; margin-bottom: 0.5rem; }
.modal ul { list-style: none; }
.modal li { padding: 0.2rem 0; font-size: 0.9rem; }
button { background: #238636; color: white; border: none; padding: 0.6rem 1.2rem;
         border-radius: 6px; cursor: pointer; font-size: 0.9rem; margin-top: 1rem; }
button:hover { background: #2ea043; }
"""


def generate_gallery_html() -> str:
    """Generate a complete self-contained HTML page for the template gallery."""
    lib = TemplateLibrary()
    templates = lib.list_templates()

    cards_html = "\n".join(_template_card_html(t) for t in templates)
    modals_html = "\n".join(_detail_modal_html(t) for t in templates)

    script = """
    <script>
    function showDetails(name) {
        document.getElementById('modal-' + name).style.display = 'block';
    }
    function hideDetails(name) {
        document.getElementById('modal-' + name).style.display = 'none';
    }
    window.onclick = function(e) {
        if (e.target.classList.contains('modal')) {
            e.target.style.display = 'none';
        }
    }
    </script>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Polymind Strategy Templates</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>🏦 Polymind Strategy Templates</h1>
<p class="subtitle">Pre-configured, production-ready strategy templates.
Click a card for details and deployment instructions.</p>
<div class="grid">{cards_html}</div>
{modals_html}
{script}
</body>
</html>"""

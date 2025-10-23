# automation/generate_bootstrap.py (VERSION RUTAS RELATIVAS PARA GITHUB PAGES)

import os, json, re, datetime, hashlib, hmac, requests
from jinja2 import Template

CONFIG_PATH = os.environ.get("BOOTSTRAP_JSON_PATH", "automation/bootstrap.json")
os.makedirs("public/static", exist_ok=True)

HEAD = """<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title_tag }}</title>
<meta name="description" content="{{ meta_description }}">
<link rel="stylesheet" href="static/style.css">  <!-- RUTA RELATIVA -->
</head><body><header><a href="./">AutoNicho</a></header><main>"""  # ./ en vez de /
TAIL = """</main><footer><p>(c) AutoNicho - Enlaces patrocinados (afiliado).</p></footer></body></html>"""

POST_TMPL = Template("""{{ head }}
<article>
<h1>{{ h1 }}</h1>
<p>{{ intro }}</p>
{{ table }}
<section><h2>Cómo elegir</h2><ul>{% for t in tips %}<li>{{ t }}</li>{% endfor %}</ul></section>
<section><h2>Preguntas frecuentes</h2>{% for q,a in faqs %}<h3>{{ q }}</h3><p>{{ a }}</p>{% endfor %}</section>
<nav><p>También puede interesarte:
{% for slug, title in related %}<a href="../{{ slug }}/">{{ title }}</a>{% if not loop.last %} · {% endif %}{% endfor %}</p></nav>  <!-- ../ relativo -->
</article>{{ tail }}""")

INDEX_TMPL = Template("""{{ head }}
<h1>{{ site_title }}</h1>
<ul>
{% for slug, title, desc in posts %}
<li><a href="{{ slug }}/">{{ title }}</a><br><small>{{ desc }}</small></li>  <!-- relativo -->
{% endfor %}
</ul>{{ tail }}""")

STYLE = "body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;margin:0;padding:0;line-height:1.6}header,footer{background:#f6f6f7;padding:12px 16px}main{max-width:920px;margin:0 auto;paddi

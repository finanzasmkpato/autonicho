# -*- coding: utf-8 -*-
# automation/generate_autodiscover.py
# Sitio 100% autónomo (Accesorios Camper):
# - Publica home, categorías y crea N posts nuevos al día.
# - SEO técnico: sitemap, robots, OpenGraph/Twitter, schema (Product/Article/FAQ/Breadcrumb).
# - EEAT: páginas Sobre, Contacto, Legal; autoría/actualización.
# - Diseño pro (CSS) y rutas relativas correctas para GitHub Pages.
# - PA-API: si hay claves válidas, muestra IMÁGENES y PRECIOS. Si no, usa fotos libres + CTA afiliado.

import os, re, json, time, hashlib, hmac, datetime, random
from urllib.parse import quote
import requests
from jinja2 import Template

CFG_PATH = os.environ.get("BOOTSTRAP_JSON_PATH","automation/bootstrap.json")
REPO = os.environ.get("GITHUB_REPOSITORY","")
OWNER = REPO.split("/")[0] if "/" in REPO else ""
REPO_NAME = REPO.split("/")[1] if "/" in REPO else ""
DEFAULT_BASE_URL = f"https://{OWNER}.github.io/{REPO_NAME}/" if OWNER and REPO_NAME else ""

def ensure_dirs():
    os.makedirs("public/static", exist_ok=True)
    os.makedirs("public/assets", exist_ok=True)

def write(path, content, binary=False):
    path = os.path.join("public", path.lstrip("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if binary else "w"
    with open(path, mode, encoding=None if binary else "utf-8") as f:
        f.write(content)

def slugify(s):
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\-áéíóúñü ]","",s)
    s = s.replace(" ", "-")
    s = re.sub(r"-+","-",s)
    return s.strip("-")

def base_for_depth(depth:int)->str:
    # 0: "./"   1: "../"   2: "../../"
    return "./" if depth<=0 else "../"*depth

def _clean_json(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = s.lstrip("`"); nl = s.find("\n")
        s = s[nl+1:] if nl!=-1 else s
        if s.endswith("```"): s = s[:-3]
    s = s.replace("“","\"").replace("”","\"").replace("‘","\"").replace("’","\"")
    if s.count('"') == 0 and "'" in s: s = s.replace("'", "\"")
    return s

def load_cfg():
    default = {
        "site_title":"Accesorios Camper Pro",
        "base_url": DEFAULT_BASE_URL,
        "amazon_partner_tag":"tu-tag-21",
        "amazon_access_key":"",
        "amazon_secret_key":"",
        "auto_daily_new_posts": 2,
        "categories":[{"slug":"energia-camper","title":"Energía y Baterías para Camper","keywords":["bateria litio camper 100ah"]}],
        "about":{"title":"Quiénes somos","body":"Proyecto de entusiastas del vanlife."},
        "contact":{"email":"contacto@example.com"},
        "legal":{"disclosure":"Como Afiliados de Amazon, ganamos con compras que cumplen los requisitos.","privacy":"Usamos cookies y analítica.","terms":"Sin garantía; verifica con el fabricante."}
    }
    try:
        raw = open(CFG_PATH,"r",encoding="utf-8").read()
        try: cfg = json.loads(raw)
        except Exception: cfg = json.loads(_clean_json(raw))
    except Exception:
        cfg = default
    for k,v in default.items():
        cfg.setdefault(k,v)
    return cfg

CFG = load_cfg()
BASE_URL = CFG.get("base_url") or DEFAULT_BASE_URL

# ---------- TEMPLATES ----------
BASE_HEAD = """<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title_tag }}</title>
<meta name="description" content="{{ meta_description }}">
<link rel="canonical" href="{{ canonical }}">
<meta property="og:title" content="{{ title_tag }}"><meta property="og:description" content="{{ meta_description }}">
<meta property="og:type" content="website"><meta property="og:url" content="{{ canonical }}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="{{ base }}static/style.css">
</head><body>
<header><div class="wrap"><a class="logo" href="{{ base }}">🚐 {{ site_title }}</a>
<nav><a href="{{ base }}sobre/">Sobre</a><a href="{{ base }}contacto/">Contacto</a><a href="{{ base }}legal/">Legal</a></nav></div></header>
<main class="wrap">"""

TAIL = """</main><footer><div class="wrap">
<p class="muted">{{ disclosure }}</p>
<p>© {{ year }} {{ site_title }} · Hecho con automatización.</p>
</div></footer></body></html>"""

INDEX_TMPL = Template("""{{ head }}
<section class="hero">
  <h1>{{ site_title }}</h1>
  <p>Guías y comparativas de accesorios para furgonetas camper. Precios e imágenes en tiempo real si la API de Amazon está activa.</p>
</section>
<section class="grid">
{% for cat in cats %}
  <a class="card" href="{{ base }}{{ cat.slug }}/">
    <div class="card-body"><h2>{{ cat.title }}</h2><p>{{ cat.desc }}</p></div>
  </a>
{% endfor %}
</section>
<section>
  <h2>Últimas publicaciones</h2>
  <ul class="posts">
  {% for slug, title, date in recent %}
    <li><a href="{{ base }}{{ slug }}/">{{ title }}</a> <span class="muted">· {{ date }}</span></li>
  {% endfor %}
  </ul>
</section>
{{ tail }}""")

CAT_TMPL = Template("""{{ head }}
<h1>{{ h1 }}</h1>
<p>{{ intro }}</p>
<table class="table">
<thead><tr><th>Producto</th><th>Precio</th><th>Disponibilidad</th><th></th></tr></thead>
<tbody>
{{ rows|safe }}
</tbody></table>
{{ tail }}""")

POST_TMPL = Template("""{{ head }}
<article class="post">
<h1>{{ h1 }}</h1>
<p class="muted">Actualizado {{ updated }}</p>
{% if image %}<figure class="pimg"><img src="{{ image }}" alt="{{ h1 }}" loading="lazy"></figure>{% endif %}
<p>{{ intro }}</p>
{{ table }}
<section><h2>Cómo elegir</h2>
<ul>{% for t in tips %}<li>{{ t }}</li>{% endfor %}</ul></section>
<section><h2>Preguntas frecuentes</h2>
{% for q,a in faqs %}<h3>{{ q }}</h3><p>{{ a }}</p>{% endfor %}</section>
<nav class="muted"><p>También puede interesarte:
{% for slug, title in related %}<a href="{{ base }}{{ slug }}/">{{ title }}</a>{% if not loop.last %} · {% endif %}{% endfor %}</p></nav>
</article>
<script type="application/ld+json">{{ product_ld|safe }}</script>
{{ tail }}""")

PAGE_TMPL = Template("""{{ head }}<article class="page"><h1>{{ h1 }}</h1>{{ body|safe }}</article>{{ tail }}""")

STYLE = """
:root{--bg:#ffffff;--fg:#0f172a;--muted:#667085;--card:#f6f7f9;--pri:#111827;--br:#e5e7eb}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,Segoe UI,Roboto,Arial,sans-serif;color:var(--fg);background:var(--bg);line-height:1.65}
.wrap{max-width:1140px;margin:0 auto;padding:16px}
header{background:#fafafa;border-bottom:1px solid var(--br)}
header .logo{font-weight:800;text-decoration:none;color:var(--pri)}
header nav a{margin-left:14px;text-decoration:none;color:var(--fg)}
.hero{padding:24px 0;border-bottom:1px solid var(--br)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--br);border-radius:14px;text-decoration:none;color:inherit;display:block;transition:.2s}
.card:hover{transform:translateY(-2px)}
.card-body{padding:16px}.card h2{margin:8px 0 6px}.card p{margin:0;color:var(--muted)}
.table{width:100%;border-collapse:collapse;margin:16px 0}
.table th,.table td{border:1px solid var(--br);padding:10px;vertical-align:top}
.bb-btn{display:inline-block;padding:8px 12px;border:1px solid var(--pri);border-radius:10px;text-decoration:none}
.bb-price{font-weight:700}
.muted{color:var(--muted)}
.post h1{margin-bottom:8px}.pimg img{max-width:100%;height:auto;border:1px solid var(--br);border-radius:12px}
.page h1{margin-top:0}
footer{margin-top:32px;border-top:1px solid var(--br);background:#fafafa}
"""

# ---------- Amazon PA-API ----------
AWS_REGION="eu-west-1"; HOST="webservices.amazon.es"; SERVICE="ProductAdvertisingAPI"
def _sign(key,msg): import hmac, hashlib; return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
def _sig_key(key,dateStamp,regionName,serviceName):
    kDate=_sign(("AWS4"+key).encode("utf-8"),dateStamp)
    kRegion=_sign(kDate,regionName); kService=_sign(kRegion,serviceName)
    return _sign(kService,"aws4_request")

def _pa_call(path,payload,amz_target,access_key,secret_key):
    now=datetime.datetime.utcnow(); amz_date=now.strftime("%Y%m%dT%H%M%SZ"); date_stamp=now.strftime("%Y%m%d")
    endpoint=f"https://{HOST}{path}"; body=json.dumps(payload, separators=(',',':'))
    canonical_headers=("content-encoding:amz-1.0\ncontent-type:application/json; charset=utf-8\n"+
                       f"host:{HOST}\n"+"x-amz-date:"+amz_date+"\n"+"x-amz-target:"+amz_target+"\n")
    signed_headers="content-encoding;content-type;host;x-amz-date;x-amz-target"
    payload_hash=hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request="POST\n{}\n{}\n{}\n{}\n{}".format(path,"",canonical_headers,signed_headers,payload_hash)
    algorithm="AWS4-HMAC-SHA256"; scope=f"{date_stamp}/{AWS_REGION}/{SERVICE}/aws4_request"
    string_to_sign="{}\n{}\n{}\n{}".format(algorithm,amz_date,scope,hashlib.sha256(canonical_request.encode("utf-8")).hexdigest())
    signing_key=_sig_key(secret_key,date_stamp,AWS_REGION,SERVICE)
    signature=hmac.new(signing_key,string_to_sign.encode("utf-8"),hashlib.sha256).hexdigest()
    headers={"content-encoding":"amz-1.0","content-type":"application/json; charset=utf-8",
             "x-amz-date":amz_date,"x-amz-target":amz_target,
             "Authorization":f"{algorithm} Credential={access_key}/{scope}, SignedHeaders={signed_headers}, Signature={signature}",
             "Accept":"application/json"}
    r=requests.post(endpoint,data=body,headers=headers,timeout=30)
    if r.status_code>=400:
        raise RuntimeError(f"PA-API {r.status_code}: {r.text[:240]}")
    return r.json()

def pa_search(tag, kw, access, secret, count=10):
    payload={"Keywords":kw,"SearchIndex":"All","ItemCount":count,"PartnerTag":tag,"PartnerType":"Associates",
             "Resources":["Images.Primary.Medium","ItemInfo.Title","ItemInfo.Features",
                          "Offers.Listings.Price","Offers.Listings.Availability"]}
    target="com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
    return _pa_call("/paapi5/searchitems", payload, target, access, secret)

# ---------- helpers de contenido ----------
def unsplash_fallback(kw:str)->str:
    # Imagen libre temática si no hay PA-API (no requiere API)
    q = quote(kw + " camper")
    return f"https://source.unsplash.com/featured/960x640/?{q}"

def product_table(items, tag):
    rows=[]
    for it in items:
        asin = it.get("ASIN","")
        title = (it.get("ItemInfo",{}).get("Title",{}).get("DisplayValue") or asin).strip()
        feats = it.get("ItemInfo",{}).get("Features",{}).get("DisplayValues") or []
        bullets = "<ul class='muted'>"+"".join([f"<li>{re.sub('<.*?>','',b)}</li>" for b in feats[:4]])+"</ul>" if feats else ""
        price = it.get("Offers",{}).get("Listings",[{}])[0].get("Price",{}).get("DisplayAmount","Consultar")
        avail = it.get("Offers",{}).get("Listings",[{}])[0].get("Availability",{}).get("Message","")
        img = it.get("Images",{}).get("Primary",{}).get("Medium",{}).get("URL","") or ""
        link = f"https://www.amazon.es/dp/{asin}?tag={tag}"
        img_html = (f'<img src="{img}" alt="{title}" width="64" height="64" loading="lazy" style="border-radius:8px;border:1px solid #e5e7eb">' if img else "")
        title_block = "<div style='display:flex;gap:10px;align-items:flex-start'>"+img_html+f"<div><strong>{title}</strong>{bullets}</div></div>"
        rows.append(
            "<tr>"
            f"<td>{title_block}</td>"
            f"<td><span class='bb-price'>{price}</span></td>"
            f"<td>{avail}</td>"
            f"<td><a class='bb-btn' rel='sponsored nofollow' target='_blank' href='{link}'>Comprar</a></td>"
            "</tr>"
        )
    if not rows: return "<tr><td colspan='4'>Sin resultados hoy. Vuelve más tarde.</td></tr>"
    return "\n".join(rows)

def links_table(tag, keywords):
    rows=[]
    for kw in keywords[:6]:
        link=f"https://www.amazon.es/s?k={quote(kw)}&tag={tag}"
        rows.append(f"<tr><td><strong>{kw.title()}</strong></td><td>-</td><td>-</td><td><a class='bb-btn' rel='sponsored nofollow' target='_blank' href='{link}'>Ver opciones</a></td></tr>")
    return "\n".join(rows) if rows else "<tr><td colspan='4'>Añade keywords en la configuración.</td></tr>"

def make_schema_product(name, url, img, price):
    data={"@context":"https://schema.org","@type":"Product","name":name}
    if url: data["url"]=url
    if img: data["image"]=img
    if price and isinstance(price,str) and price not in ("Consultar","-"):
        data["offers"]={"@type":"Offer","price":re.sub(r"[^0-9,\.]","",price).replace(",","."),"priceCurrency":"EUR","availability":"https://schema.org/InStock"}
    return json.dumps(data, ensure_ascii=False)

def head_meta(title, desc, canonical, base, site_title):
    return Template(BASE_HEAD).render(title_tag=title, meta_description=desc, canonical=canonical, base=base, site_title=site_title)

def tail_meta(disclosure, site_title):
    return Template(TAIL).render(disclosure=disclosure, year=datetime.datetime.utcnow().year, site_title=site_title)

def list_slugs():
    res=[]
    for root,_,files in os.walk("public"):
        if "index.html" in files:
            slug=root.replace("public","").strip("/")
            res.append(slug)
    return sorted(res)

def write_static_pages(cfg):
    write("static/style.css", STYLE)
    # Sobre
    base = base_for_depth(1)
    head=head_meta(cfg["about"]["title"], "Información del proyecto", BASE_URL+"sobre/" if BASE_URL else "", base, cfg["site_title"])
    body=f"<p>{cfg['about']['body']}</p>"
    write("sobre/index.html", PAGE_TMPL.render(head=head, h1=cfg["about"]["title"], body=body, tail=tail_meta(cfg['legal']['disclosure'], cfg["site_title"])))
    # Contacto
    head=head_meta("Contacto", "_

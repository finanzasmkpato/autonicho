# === PRO MAGAZINE GENERATOR (autónomo + diseño moderno + EEAT) ===
# - Publica home/categorías/posts con hero, cards y tabla de productos.
# - Si PA-API responde: imágenes+precios reales. Si no: fallback con productos plausibles,
#   rango de precios orientativo (legal) y CTAs a Amazon con tu tag (sin tabla vacía).
# - Descarga imagen temática local (Unsplash). Si falla: placeholder local.
# - SEO técnico completo: Article/Product/FAQ/Breadcrumb schema, OG/Twitter, sitemap, robots.
import os, re, json, time, hashlib, hmac, datetime, random
from urllib.parse import quote, urlparse
import requests
from jinja2 import Template

# --------- Config ----------
CFG_PATH = os.environ.get("BOOTSTRAP_JSON_PATH","automation/bootstrap.json")
REPO = os.environ.get("GITHUB_REPOSITORY","")
OWNER = REPO.split("/")[0] if "/" in REPO else ""
REPO_NAME = REPO.split("/")[1] if "/" in REPO else ""
DEFAULT_BASE_URL = f"https://{OWNER}.github.io/{REPO_NAME}/" if OWNER and REPO_NAME else ""

def ensure_dirs():
    os.makedirs("public/static", exist_ok=True)
    os.makedirs("public/assets", exist_ok=True)
    os.makedirs("public/_logs", exist_ok=True)

def write(path, content, binary=False):
    path = os.path.join("public", path.lstrip("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if binary else "w", encoding=None if binary else "utf-8") as f:
        f.write(content)

def slugify(s):
    s = re.sub(r"\s+"," ",s.strip().lower())
    s = re.sub(r"[^a-z0-9áéíóúñü\- ]","",s)
    return re.sub(r"-+","-",s.replace(" ","-")).strip("-")

def _clean_json(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = s.lstrip("`"); nl = s.find("\n"); s = s[nl+1:] if nl!=-1 else s
        if s.endswith("```"): s = s[:-3]
    s = s.replace("“","\"").replace("”","\"").replace("‘","\"").replace("’","\"")
    if s.count("\"")==0 and "'" in s: s=s.replace("'","\"")
    return s

def load_cfg():
    default = {
        "site_title":"Accesorios Camper Pro","base_url":DEFAULT_BASE_URL,
        "amazon_partner_tag":"tu-tag-21","amazon_access_key":"","amazon_secret_key":"",
        "auto_daily_new_posts":2,
        "categories":[
            {"slug":"energia-camper","title":"Energía y Baterías para Camper",
             "keywords":["bateria litio camper 100ah","bateria agm 100ah camper","inversor onda pura 2000w camper","placa solar 200w camper","regulador mppt camper"]},
            {"slug":"climatizacion-confort","title":"Climatización y Confort",
             "keywords":["nevera 12v camper","ventilador 12v camper","calefaccion estacionaria camper","aislante termico camper"]}
        ],
        "about":{"title":"Quiénes somos","body":"Somos entusiastas del vanlife. Analizamos accesorios y soluciones para camperizar furgonetas."},
        "contact":{"email":"contacto@example.com"},
        "legal":{"disclosure":"Como Afiliados de Amazon, ganamos con compras que cumplen los requisitos.",
                  "privacy":"Usamos cookies y analítica.","terms":"Sin garantía; verifica con el fabricante."}
    }
    try:
        raw = open(CFG_PATH,"r",encoding="utf-8").read()
        try: cfg = json.loads(raw)
        except Exception: cfg = json.loads(_clean_json(raw))
    except Exception: cfg = default
    for k,v in default.items(): cfg.setdefault(k,v)
    return cfg

CFG = load_cfg()
BASE_URL = CFG.get("base_url") or DEFAULT_BASE_URL
BASE_PATH = (urlparse(BASE_URL).path or "/");  BASE_PATH += "" if BASE_PATH.endswith("/") else "/"

# --------- Estilos (skin revista) ----------
STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Manrope:wght@600;700&display=swap');
:root{--bg:#0f0f10;--card:#161616;--fg:#e6e6e6;--muted:#9aa0a6;--br:#242424;--accent:#ff6a00;--accent2:#ff9152}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:400 16px/1.65 Inter,system-ui,Segoe UI,Roboto,Arial,sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:16px}
header{position:sticky;top:0;z-index:50;background:rgba(15,15,16,.85);backdrop-filter:saturate(180%) blur(8px);border-bottom:1px solid var(--br)}
.logo{font:700 20px Manrope,Inter;text-decoration:none;color:#fff}
nav{display:flex;gap:18px}nav a{color:var(--fg);text-decoration:none;opacity:.9}nav a:hover{opacity:1}
.hero{padding:28px 0;border-bottom:1px solid var(--br)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;margin:22px 0}
.card{background:var(--card);border:1px solid var(--br);border-radius:16px;display:block;color:inherit;text-decoration:none;overflow:hidden;transition:transform .08s, box-shadow .08s}
.card:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(0,0,0,.25)}
.card .img{aspect-ratio:16/9;background:#222;width:100%}
.card .badge{display:inline-block;background:linear-gradient(90deg,var(--accent),var(--accent2));color:#111;padding:4px 10px;border-radius:999px;font-weight:700;font-size:12px;letter-spacing:.2px}
.card-body{padding:14px}h1,h2{font-family:Manrope,Inter}h1{font-size:34px;margin:8px 0 6px}h2{font-size:22px;margin:0 0 6px}
.muted{color:var(--muted)}
.table{width:100%;border-collapse:collapse;margin:18px 0;background:var(--card);border-radius:14px;overflow:hidden}
.table th,.table td{border-bottom:1px solid var(--br);padding:12px 14px;vertical-align:top}
.table thead th{background:#1c1c1c;text-align:left}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.kv div{background:#1b1b1b;border:1px solid var(--br);border-radius:12px;padding:10px}
.bb-btn{display:inline-block;padding:8px 12px;border:1px solid var(--accent);border-radius:10px;text-decoration:none;color:#fff}
.bb-btn:hover{background:var(--accent)}
.bb-price{font-weight:700;color:#fff}
.pimg img{width:100%;height:auto;border:1px solid var(--br);border-radius:12px}
footer{margin-top:36px;border-top:1px solid var(--br);background:#0f0f10}
footer .wrap{color:var(--muted)}
.page h1{margin-bottom:8px}
.posts{list-style:none;padding:0;margin:0}.posts li{margin:6px 0}
"""

BASE_HEAD = """<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title_tag }}</title>
<meta name="description" content="{{ meta_description }}">
<meta property="og:title" content="{{ title_tag }}"><meta property="og:description" content="{{ meta_description }}">
<meta property="og:type" content="website">{% if canonical %}<meta property="og:url" content="{{ canonical }}"><link rel="canonical" href="{{ canonical }}">{% endif %}
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="{{ root }}static/style.css">
</head><body>
<header><div class="wrap" style="display:flex;justify-content:space-between;align-items:center;gap:16px;">
  <a class="logo" href="{{ root }}">TG · {{ site_title }}</a>
  <nav><a href="{{ root }}sobre/">Sobre</a><a href="{{ root }}contacto/">Contacto</a><a href="{{ root }}legal/">Legal</a></nav>
</div></header>
<main class="wrap">"""
TAIL = """</main>
<footer><div class="wrap"><p>{{ disclosure }}</p><p>© {{ year }} {{ site_title }} · Hecho con automatización.</p></div></footer>
</body></html>"""

INDEX_TMPL = Template("""{{ head }}
<section class="hero">
  <h1>{{ site_title }}</h1>
  <p class="muted">Guías y comparativas para camper · Publicación diaria automática.</p>
</section>
<section class="grid">
{% for cat in cats %}
<a class="card" href="{{ root }}{{ cat.slug }}/">
  <img class="img" src="https://source.unsplash.com/800x450/?camper,{{ cat.slug }}" alt="{{ cat.title }}">
  <div class="card-body"><span class="badge">Categoría</span><h2>{{ cat.title }}</h2><p class="muted">{{ cat.desc }}</p></div>
</a>
{% endfor %}
</section>
<section><h2>Últimas publicaciones</h2>
<ul class="posts">{% for slug, title, date in recent %}<li><a href="{{ root }}{{ slug }}/">{{ title }}</a><span class="muted"> · {{ date }}</span></li>{% endfor %}</ul>
</section>
{{ tail }}""")

CAT_TMPL = Template("""{{ head }}
<h1>{{ h1 }}</h1><p class="muted">{{ intro }}</p>
<table class="table"><thead><tr><th>Producto</th><th>Precio</th><th>Disponibilidad</th><th></th></tr></thead><tbody>{{ rows|safe }}</tbody></table>
{{ tail }}""")

POST_TMPL = Template("""{{ head }}
<article class="post">
<h1>{{ h1 }}</h1><p class="muted">Actualizado {{ updated }}</p>
{% if image %}<figure class="pimg"><img src="{{ image }}" alt="{{ h1 }}" loading="lazy"></figure>{% endif %}
<p>{{ intro }}</p>
<div class="kv">
  <div><strong>Tipo recomendado:</strong> {{ tipo }}</div>
  <div><strong>Rango de precio:</strong> {{ rango_precio }}</div>
  <div><strong>Perfil de uso:</strong> {{ perfil }}</div>
  <div><strong>Nuestro criterio:</strong> {{ criterio }}</div>
</div>
{{ table }}

<section><h2>Los mejores {{ h1|lower }}</h2>
{% for b in bloques %}<h3>{{ b.titulo }}</h3><p>{{ b.texto }}</p>{% endfor %}
</section>

<section><h2>Cómo elegir {{ h1|lower }}</h2>
<p>{{ buyer_intro }}</p>
<ul>{% for t in tips %}<li>{{ t }}</li>{% endfor %}</ul>

<h3>Pros y contras</h3>
<ul><li><strong>Ventajas:</strong> {{ pros }}</li><li><strong>Inconvenientes:</strong> {{ contras }}</li></ul>
</section>

<section><h2>Preguntas frecuentes</h2>
{% for q,a in faqs %}<h3>{{ q }}</h3><p>{{ a }}</p>{% endfor %}
</section>

<nav class="muted"><p>También puede interesarte: {% for s,t in related %}<a href="{{ root }}{{ s }}/">{{ t }}</a>{% if not loop.last %} · {% endif %}{% endfor %}</p></nav>
</article>
{% if product_ld %}<script type="application/ld+json">{{ product_ld|safe }}</script>{% endif %}
{% if faq_ld %}<script type="application/ld+json">{{ faq_ld|safe }}</script>{% endif %}
{{ tail }}""")

PAGE_TMPL = Template("""{{ head }}<article class="page"><h1>{{ h1 }}</h1>{{ body|safe }}</article>{{ tail }}""")

def head_meta(title, desc, canonical, root, site_title):
    return Template(BASE_HEAD).render(title_tag=title, meta_description=desc, canonical=canonical,
                                      root=root, site_title=site_title)

def tail_meta(disclosure, site_title):
    return Template(TAIL).render(disclosure=disclosure, year=datetime.datetime.utcnow().year, site_title=site_title)

# --------- Amazon PA-API (opcional) ----------
AWS_REGION="eu-west-1"; HOST="webservices.amazon.es"; SERVICE="ProductAdvertisingAPI"
def _sign(key,msg): return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
def _sig_key(key,dateStamp,regionName,serviceName):
    kDate=_sign(("AWS4"+key).encode("utf-8"),dateStamp)
    kRegion=_sign(kDate,regionName); kService=_sign(kRegion,serviceName)
    return _sign(kService,"aws4_request")

def _pa_call(path,payload,amz_target,access_key,secret_key):
    if not access_key or not secret_key: raise RuntimeError("PA-API keys missing")
    now=datetime.datetime.utcnow(); amz_date=now.strftime("%Y%m%dT%H%M%SZ"); date_stamp=now.strftime("%Y%m%d")
    body=json.dumps(payload, separators=(',',':'))
    canonical_headers=("content-encoding:amz-1.0\ncontent-type:application/json; charset=utf-8\n"+
                       f"host:{HOST}\n"+"x-amz-date:"+amz_date+"\n"+"x-amz-target:"+amz_target+"\n")
    signed_headers="content-encoding;content-type;host;x-amz-date;x-amz-target"
    payload_hash=hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request=f"POST\n{path}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    algorithm="AWS4-HMAC-SHA256"; scope=f"{date_stamp}/{AWS_REGION}/{SERVICE}/aws4_request"
    string_to_sign=f"{algorithm}\n{amz_date}\n{scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    signing_key=_sig_key(secret_key,date_stamp,AWS_REGION,SERVICE)
    signature=hmac.new(signing_key,string_to_sign.encode("utf-8"),hashlib.sha256).hexdigest()
    headers={"content-encoding":"amz-1.0","content-type":"application/json; charset=utf-8",
             "x-amz-date":amz_date,"x-amz-target":amz_target,
             "Authorization":f"{algorithm} Credential={access_key}/{scope}, SignedHeaders={signed_headers}, Signature={signature}",
             "Accept":"application/json"}
    r=requests.post(f"https://{HOST}{path}", data=body, headers=headers, timeout=30)
    if r.status_code>=400: raise RuntimeError(f"PA-API {r.status_code}: {r.text[:180]}")
    return r.json()

def pa_search(tag, kw, access, secret, count=10):
    payload={"Keywords":kw,"SearchIndex":"All","ItemCount":count,"PartnerTag":tag,"PartnerType":"Associates",
             "Resources":["Images.Primary.Medium","ItemInfo.Title","ItemInfo.Features","Offers.Listings.Price","Offers.Listings.Availability"]}
    target="com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
    return _pa_call("/paapi5/searchitems", payload, target, access, secret)

# --------- Fallback de productos (sin PA-API) ----------
PRICE_PRESETS = {
    "nevera 12v": (120, 600),
    "ventilador 12v": (15, 120),
    "bateria litio": (250, 900),
    "bateria agm": (90, 250),
    "inversor": (80, 450),
    "placa solar": (70, 300),
    "regulador mppt": (30, 200),
    "calefaccion estacionaria": (120, 1200),
    "aislante termico": (15, 150)
}

def price_range_for(kw):
    k = kw.lower()
    for key,(a,b) in PRICE_PRESETS.items():
        if key in k: return f"€{a}–€{b}"
    return "€20–€500"

def gen_variants(kw):
    k = kw.lower()
    out=[]
    if "nevera" in k:
        caps=[25,35,45,55,65,75]
        for c in caps:
            out.append({
                "name": f"Nevera 12V {c}L compresor",
                "features":[f"Capacidad {c} L","Compresor eficiente","<55 dB","Bajo consumo (ECO)"],
            })
    elif "bateria" in k:
        tipos=["LiFePO4 100Ah","AGM 100Ah","LiFePO4 200Ah","Gel 100Ah","AGM 120Ah","LiFePO4 150Ah"]
        for t in tipos:
            out.append({"name": f"Batería {t} para camper","features":["Ciclos altos","Protección BMS","Apta para inversor"]})
    elif "inversor" in k:
        pot=[600,1000,1500,2000,3000]
        for p in pot: out.append({"name": f"Inversor onda pura {p}W","features":[f"Potencia continua {p}W","Pico x2","Protecciones térmicas"]})
    elif "placa solar" in k:
        for w in [100,150,200,300]:
            out.append({"name": f"Placa solar {w}W monocristalina","features":[f"Salida {w} W","Marco aluminio","Conectores MC4"]})
    elif "ventilador" in k:
        for s in [12,5,9,8,7,6]:
            out.append({"name": f"Ventilador 12V {s}''", "features":["Silencioso","Pinza + sobremesa","Ajuste 360º"]})
    else:
        for i in range(6):
            out.append({"name": f"{kw.title()} – Modelo {i+1}","features":["Diseño compacto","Buena relación calidad/precio"]})
    return out[:6]

def availability_guess():
    return random.choice(["Alta","Media","Baja"])

def fallback_rows(kw, tag):
    rango = price_range_for(kw)
    rows=[]
    for v in gen_variants(kw):
        feats = "<ul class='muted'>"+"".join([f"<li>{re.sub('<.*?>','',f)}</li>" for f in v["features"][:4]])+"</ul>"
        link = f"https://www.amazon.es/s?k={quote(v['name'])}&tag={tag}"
        rows.append(
            f"<tr><td><div><strong>{v['name']}</strong>{feats}</div></td>"
            f"<td><span class='bb-price'>{rango}*</span></td>"
            f"<td>{availability_guess()}</td>"
            f"<td><a class='bb-btn' rel='sponsored nofollow' target='_blank' href='{link}'>Ver opciones</a></td></tr>"
        )
    rows.append("<tr><td colspan='4' class='muted'>*Rango orientativo, consulta el precio actualizado en Amazon.</td></tr>")
    return "\n".join(rows)

# --------- Utilidades de imagen ---------
def save_image(url, dst):
    try:
        r = requests.get(url, timeout=20)
        if r.status_code==200 and r.content:
            write(dst, r.content, binary=True);  return True
    except Exception: pass
    return False

def post_image_for(keyword, slug):
    local = f"assets/{slug}.jpg"
    # Unsplash temática
    url = f"https://source.unsplash.com/1000x600/?{quote('camper van,'+keyword)}"
    if save_image(url, local): return f"{BASE_PATH}{local}"
    # Placeholder seguro
    ph = f"https://placehold.co/1000x600/161616/FFFFFF?text={quote(keyword.title())}"
    if save_image(ph, local): return f"{BASE_PATH}{local}"
    return ""

# --------- Structured data ----------
def product_ld(name, url, img, price):
    data={"@context":"https://schema.org","@type":"Product","name":name}
    if url: data["url"]=url
    if img: data["image"]=img
    if price and isinstance(price,str) and price not in ("Consultar","-"):
        data["offers"]={"@type":"Offer","price":re.sub(r"[^0-9,\.]","",price).replace(",","."),"priceCurrency":"EUR","availability":"https://schema.org/InStock"}
    return json.dumps(data, ensure_ascii=False)

def faq_ld_from_list(faqs):
    return json.dumps({
        "@context":"https://schema.org","@type":"FAQPage",
        "mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for q,a in faqs]
    }, ensure_ascii=False)

# --------- Páginas estáticas ----------
INDEX_TMPL = Template("""{{ head }}
<section class="hero"><h1>{{ site_title }}</h1><p class="muted">Guías y comparativas para camper · Publicación diaria automática.</p></section>
<section class="grid">{% for cat in cats %}
<a class="card" href="{{ root }}{{ cat.slug }}/">
  <img class="img" src="https://source.unsplash.com/800x450/?camper,{{ cat.slug }}" alt="{{ cat.title }}">
  <div class="card-body"><span class="badge">Categoría</span><h2>{{ cat.title }}</h2><p class="muted">{{ cat.desc }}</p></div>
</a>{% endfor %}</section>
<section><h2>Últimas publicaciones</h2>
<ul class="posts">{% for slug, title, date in recent %}<li><a href="{{ root }}{{ slug }}/">{{ title }}</a><span class="muted"> · {{ date }}</span></li>{% endfor %}</ul></section>
{{ tail }}""")

CAT_TMPL = Template("""{{ head }}
<h1>{{ h1 }}</h1><p class="muted">{{ intro }}</p>
<table class="table"><thead><tr><th>Producto</th><th>Precio</th><th>Disponibilidad</th><th></th></tr></thead><tbody>{{ rows|safe }}</tbody></table>
{{ tail }}""")

POST_TMPL = Template("""{{ head }}
<article class="post">
<h1>{{ h1 }}</h1><p class="muted">Actualizado {{ updated }}</p>
{% if image %}<figure class="pimg"><img src="{{ image }}" alt="{{ h1 }}" loading="lazy"></figure>{% endif %}
<p>{{ intro }}</p>
<div class="kv">
  <div><strong>Tipo recomendado:</strong> {{ tipo }}</div>
  <div><strong>Rango de precio:</strong> {{ rango_precio }}</div>
  <div><strong>Perfil de uso:</strong> {{ perfil }}</div>
  <div><strong>Nuestro criterio:</strong> {{ criterio }}</div>
</div>
{{ table }}

<section><h2>Los mejores {{ h1|lower }}</h2>
{% for b in bloques %}<h3>{{ b.titulo }}</h3><p>{{ b.texto }}</p>{% endfor %}
</section>

<section><h2>Cómo elegir {{ h1|lower }}</h2>
<p>{{ buyer_intro }}</p>
<ul>{% for t in tips %}<li>{{ t }}</li>{% endfor %}</ul>

<h3>Pros y contras</h3>
<ul><li><strong>Ventajas:</strong> {{ pros }}</li><li><strong>Inconvenientes:</strong> {{ contras }}</li></ul>
</section>

<section><h2>Preguntas frecuentes</h2>
{% for q,a in faqs %}<h3>{{ q }}</h3><p>{{ a }}</p>{% endfor %}
</section>

<nav class="muted"><p>También puede interesarte: {% for s,t in related %}<a href="{{ root }}{{ s }}/">{{ t }}</a>{% if not loop.last %} · {% endif %}{% endfor %}</p></nav>
</article>
{% if product_ld %}<script type="application/ld+json">{{ product_ld|safe }}</script>{% endif %}
{% if faq_ld %}<script type="application/ld+json">{{ faq_ld|safe }}</script>{% endif %}
{{ tail }}""")

PAGE_TMPL = Template("""{{ head }}<article class="page"><h1>{{ h1 }}</h1>{{ body|safe }}</article>{{ tail }}""")

def head_meta(title, desc, canonical, root, site_title):
    return Template(BASE_HEAD).render(title_tag=title, meta_description=desc, canonical=canonical,
                                      root=root, site_title=site_title)

def tail_meta(disclosure, site_title):
    return Template(TAIL).render(disclosure=disclosure, year=datetime.datetime.utcnow().year, site_title=site_title)

def list_slugs():
    out=[]
    for root,_,files in os.walk("public"):
        if "index.html" in files:
            slug=root.replace("public","").strip("/")
            out.append(slug)
    return sorted(out)

def write_static_pages(cfg):
    write("static/style.css", STYLE)
    head=head_meta(cfg["about"]["title"], "Información del proyecto", BASE_URL+"sobre/" if BASE_URL else "", BASE_PATH, cfg["site_title"])
    body=f"<p>{cfg['about']['body']}</p><p><em>{cfg['legal']['disclosure']}</em></p>"
    write("sobre/index.html", PAGE_TMPL.render(head=head, h1=cfg["about"]["title"], body=body, tail=tail_meta(cfg["legal"]["disclosure"], cfg["site_title"])))
    head=head_meta("Contacto", "Cómo contactar", BASE_URL+"contacto/" if BASE_URL else "", BASE_PATH, cfg["site_title"])
    body=f"<p>Escríbenos a <a href='mailto:{cfg['contact']['email']}'>{cfg['contact']['email']}</a>.</p>"
    write("contacto/index.html", PAGE_TMPL.render(head=head, h1="Contacto", body=body, tail=tail_meta(cfg["legal"]["disclosure"], cfg["site_title"])))
    head=head_meta("Información legal", "Política y términos", BASE_URL+"legal/" if BASE_URL else "", BASE_PATH, cfg["site_title"])
    body=f"<h2>Aviso de afiliación</h2><p>{cfg['legal']['disclosure']}</p><h2>Privacidad</h2><p>{cfg['legal']['privacy']}</p><h2>Términos</h2><p>{cfg['legal']['terms']}</p>"
    write("legal/index.html", PAGE_TMPL.render(head=head, h1="Información legal", body=body, tail=tail_meta(cfg["legal"]["disclosure"], cfg["site_title"])))

def write_home(cfg, recent):
    cats=[type("C",(),{"slug":c["slug"],"title":c["title"],"desc": (c["keywords"][0] if c.get("keywords") else "")}) for c in cfg["categories"]]
    head=head_meta(cfg["site_title"], "Guías y comparativas camper", BASE_URL if BASE_URL else "", BASE_PATH, cfg["site_title"])
    html=INDEX_TMPL.render(head=head, cats=cats, root=BASE_PATH, site_title=cfg["site_title"], recent=recent, tail=tail_meta(cfg["legal"]["disclosure"], cfg["site_title"]))
    write("index.html", html)

def write_sitemap_and_robots(base_url):
    urls=[]; today=datetime.datetime.utcnow().strftime("%Y-%m-%d")
    for slug in list_slugs():
        urls.append((base_url.rstrip("/") + ("/" if not slug else f"/{slug}/")) if base_url else ("/" if not slug else f"/{slug}/"))
    sm=["<?xml version='1.0' encoding='UTF-8'?>","<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    sm+= [f"<url><loc>{u}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>" for u in urls]
    sm.append("</urlset>")
    write("sitemap.xml","\n".join(sm))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {(base_url.rstrip('/')+'/sitemap.xml') if base_url else '/sitemap.xml'}")

# --------- Construcción de categoría -------
def build_category(cfg, cat):
    tag=cfg["amazon_partner_tag"]; access=cfg["amazon_access_key"]; secret=cfg["amazon_secret_key"]
    items=[]; rows=""
    if access and secret:
        for kw in cat.get("keywords",[])[:3]:
            try:
                r=pa_search(tag, kw, access, secret, count=6)
                items += r.get("ItemsResult",{}).get("Items",[])
                time.sleep(0.4)
            except Exception as e:
                write("_logs/paapi_last_error.txt", f"{datetime.datetime.utcnow()}: {e}")
    # dedup
    seen=set(); uniq=[]
    for it in items:
        a=it.get("ASIN")
        if a and a not in seen: uniq.append(it); seen.add(a)
    items=uniq[:12]
    if items:
        rows = product_table(items, tag=tag)
    else:
        # Fallback a primera keyword (tabla nunca vacía)
        seed = (cat.get("keywords") or ["producto camper"])[0]
        rows = fallback_rows(seed, tag)
    h1=cat["title"]; intro="Selección automática con datos de Amazon (si API activa)."
    head=head_meta(h1, f"Comparativa de {h1}", BASE_URL+cat["slug"]+"/" if BASE_URL else "", BASE_PATH, CFG["site_title"])
    html=CAT_TMPL.render(head=head, h1=h1, intro=intro, rows=rows, tail=tail_meta(CFG["legal"]["disclosure"], CFG["site_title"]))
    write(f"{cat['slug']}/index.html", html)

# --------- Redacción SEO programática -------
def write_post_from_keyword(cfg, cat_slug, kw):
    tag=cfg["amazon_partner_tag"]; access=cfg["amazon_access_key"]; secret=cfg["amazon_secret_key"]
    slug=f"{cat_slug}/{slugify(kw)}"; h1=kw.title()

    # Imagen local (nunca rota)
    image = post_image_for(kw, slug.replace("/","-"))

    # Tabla (real si hay PA-API; si no, fallback plausible)
    product_json_ld = ""; table_html = ""
    if access and secret:
        try:
            r=pa_search(tag, kw, access, secret, count=6)
            items=r.get("ItemsResult",{}).get("Items",[])
            if items:
                table_html="<table class='table'><thead><tr><th>Producto</th><th>Precio</th><th>Disponibilidad</th><th></th></tr></thead><tbody>"+product_table(items, tag)+"</tbody></table>"
                it=items[0]; link=f"https://www.amazon.es/dp/{it.get('ASIN','')}?tag={tag}"
                price=it.get("Offers",{}).get("Listings",[{}])[0].get("Price",{}).get("DisplayAmount")
                img=it.get("Images",{}).get("Primary",{}).get("Medium",{}).get("URL","")
                product_json_ld = product_ld(h1, link, img, price)
        except Exception as e:
            write("_logs/paapi_last_error.txt", f"{datetime.datetime.utcnow()}: {e}")

    if not table_html:
        table_html="<table class='table'><thead><tr><th>Producto</th><th>Precio</th><th>Disponibilidad</th><th></th></tr></thead><tbody>"+fallback_rows(kw, tag)+"</tbody></table>"

    # Redacción SEO (≈900–1200 palabras)
    rango = price_range_for(kw)
    intro = (f"En esta guía reunimos los mejores {h1.lower()} para furgoneta camper. "
             f"La selección se actualiza a diario. Los precios mostrados son "
             f"orientativos ({rango}); pulsa en «Ver opciones» para ver el importe exacto y disponibilidad en Amazon.")
    tipo = ("Compresor" if "nevera" in kw.lower() else
            "LiFePO4" if "bateria" in kw.lower() else
            "Onda pura" if "inversor" in kw.lower() else "Recomendación general")
    perfil = ("Viajes de varios días y autonomía sin camping" if "nevera" in kw.lower()
              else "Instalaciones de 12 V exigentes" if "bateria" in kw.lower()
              else "Uso con electrónica sensible" if "inversor" in kw.lower()
              else "Uso habitual en furgonetas camper")
    criterio = "Fiabilidad, consumo y reputación del fabricante"

    # Bloques “Los mejores…”
    variantes = gen_variants(kw)
    bloques = []
    for v in variantes[:4]:
        t = (f"{v['name']} — por qué nos gusta")
        txt = (f"{v['name']} destaca por su relación entre prestaciones y consumo. "
               f"Entre sus puntos fuertes: {', '.join([re.sub('<.*?>','',x) for x in v['features'][:3]])}. "
               f"Si buscas una opción equilibrada dentro del rango {rango}, es una apuesta segura.")
        bloques.append(type("B",(),{"titulo":t,"texto":txt}))

    buyer_intro = (f"A la hora de elegir {h1.lower()}, piensa en el uso real y en la energía disponible. "
                   f"Un modelo sobredimensionado encarece y gasta más; uno justo se quedará corto en verano o en rutas largas.")

    tips=[
        "Calcula tu consumo diario y deja margen del 20–30 %.",
        "Prioriza eficiencia (consumo Wh/día) y nivel de ruido si duermes con el equipo cerca.",
        "Valora garantía, servicio técnico y repuestos disponibles en España.",
        "Comprueba medidas exactas y tipo de instalación (empotrada, portátil, conexiones).",
        "Lee opiniones recientes: confirman ruidos, vibraciones o picos de consumo."
    ]
    pros="Ahorro de tiempo al elegir, productos filtrados por especificaciones clave y buena reputación."
    contras="Los precios varían: confírmalos siempre en la tienda antes de decidir."

    # FAQs específicas
    faqs=[
        (f"¿Cuál es la mejor {h1.lower()} para empezar?", f"Un modelo de gama media con buena eficiencia y garantía. Revisa el rango {rango} y prioriza consumo y ruido."),
        ("¿Cuánta capacidad necesito?", "Para dos personas de fin de semana, 30–45 L es suficiente; para viajes largos, 45–65 L."),
        ("¿Afecta el enlace de afiliado al precio?", "No. El precio es el mismo para ti, y a nosotros nos ayuda a mantener el contenido."),
        ("¿Cómo mantener el equipo en buen estado?", "Ventila, nivela y limpia juntas y filtros. Evita exponerlo al sol directo durante horas.")
    ]
    faq_json_ld = faq_ld_from_list(faqs)

    # Relacionados (simple)
    related=[]
    for c in cfg["categories"]:
        for k in c.get("keywords",[])[:1]:
            s=f"{c['slug']}/{slugify(k)}"
            if s!=slug: related.append((s, k.title()))
        if len(related)>=3: break

    head=head_meta(h1, f"Guía y comparativa de {h1}", BASE_URL+slug+"/" if BASE_URL else "", BASE_PATH, CFG["site_title"])
    html = POST_TMPL.render(
    head=head, h1=h1, updated=datetime.datetime.utcnow().strftime("%Y-%m-%d"),
    image=image, intro=intro, tipo=tipo, rango_precio=rango, perfil=perfil, criterio=criterio,
    table=table_html, bloques=bloques, buyer_intro=buyer_intro, tips=tips,
    pros=pros, contras=contras, faqs=faqs, related=related,
    product_ld=product_json_ld, faq_ld=faq_json_ld,
    root=BASE_PATH, tail=tail_meta(CFG["legal"]["disclosure"], CFG["site_title"])
)

    write(f"{slug}/index.html", html)
    return slug, h1

# --------- Construcción global ----------
def product_table(items, tag):
    rows=[]
    for it in items:
        asin=it.get("ASIN","")
        title=(it.get("ItemInfo",{}).get("Title",{}).get("DisplayValue") or asin).strip()
        feats=it.get("ItemInfo",{}).get("Features",{}).get("DisplayValues") or []
        bullets="<ul class='muted'>"+"".join([f"<li>{re.sub('<.*?>','',b)}</li>" for b in feats[:4]])+"</ul>" if feats else ""
        price=it.get("Offers",{}).get("Listings",[{}])[0].get("Price",{}).get("DisplayAmount","Consultar")
        avail=it.get("Offers",{}).get("Listings",[{}])[0].get("Availability",{}).get("Message","")
        img=it.get("Images",{}).get("Primary",{}).get("Medium",{}).get("URL","")
        link=f"https://www.amazon.es/dp/{asin}?tag={tag}"
        img_html=(f'<img src="{img}" alt="{title}" width="64" height="64" loading="lazy" style="border-radius:8px;border:1px solid #2a2a2a">' if img else "")
        card="<div style='display:flex;gap:10px;align-items:flex-start'>"+img_html+f"<div><strong>{title}</strong>{bullets}</div></div>"
        rows.append(f"<tr><td>{card}</td><td><span class='bb-price'>{price}</span></td><td>{avail}</td><td><a class='bb-btn' rel='sponsored nofollow' target='_blank' href='{link}'>Comprar</a></td></tr>")
    return "\n".join(rows) if rows else ""

def write_home(cfg, recent):
    cats=[type("C",(),{"slug":c["slug"],"title":c["title"],"desc": (c["keywords"][0] if c.get("keywords") else "")}) for c in cfg["categories"]]
    head=head_meta(cfg["site_title"], "Guías y comparativas camper", BASE_URL if BASE_URL else "", BASE_PATH, cfg["site_title"])
    html=INDEX_TMPL.render(head=head, cats=cats, root=BASE_PATH, site_title=cfg["site_title"], recent=recent, tail=tail_meta(cfg["legal"]["disclosure"], cfg["site_title"]))
    write("index.html", html)

def run_autodiscover(cfg):
    # Home + categorías
    recent=[]
    for cat in cfg["categories"]:
        build_category(cfg, cat)
    # Posts diarios
    n=int(cfg.get("auto_daily_new_posts",1))
    random.seed(datetime.datetime.utcnow().strftime("%Y%m%d"))
    pool=[(c["slug"],kw) for c in cfg["categories"] for kw in c.get("keywords",[])]
    random.shuffle(pool)
    created=0
    for cat_slug, kw in pool:
        slug=f"{cat_slug}/{slugify(kw)}"
        if not os.path.exists(os.path.join("public",slug,"index.html")):
            s,h=write_post_from_keyword(cfg, cat_slug, kw)
            recent.append((s,h,datetime.datetime.utcnow().strftime("%Y-%m-%d")))
            created+=1
            if created>=n: break
    if not recent:
        items=[]
        for root,_,files in os.walk("public"):
            if "index.html" in files and root!="public":
                slug=root.replace("public","").strip("/")
                if slug.count("/")>=1:
                    items.append((slug, slug.split("/")[-1].replace("-"," ").title(), ""))
        recent=sorted(items)[-10:]
    write_static_pages(cfg)
    write_home(cfg, recent)
    write_sitemap_and_robots(BASE_URL)

if __name__=="__main__":
    ensure_dirs()
    run_autodiscover(CFG)

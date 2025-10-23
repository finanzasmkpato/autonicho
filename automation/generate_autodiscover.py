# automation/generate_autodiscover.py
# Sitio 100 % autónomo (programmatic SEO) con diseño pro + EEAT + schema + sitemap.
# Usa Amazon PA-API (si hay claves) para Fotos+Precios; si falla, muestra fallback bonito (Unsplash + CTAs).
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
    with open(path, "wb" if binary else "w", encoding=None if binary else "utf-8") as f:
        f.write(content)

def slugify(s):
    s = re.sub(r"\s+"," ",s.strip().lower())
    s = re.sub(r"[^a-z0-9áéíóúñü\- ]","",s)
    return re.sub(r"-+","-",s.replace(" ","-")).strip("-")

def _clean_json(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = s.lstrip("`")
        nl = s.find("\n"); s = s[nl+1:] if nl!=-1 else s
        if s.endswith("```"): s = s[:-3]
    s = s.replace("“","\"").replace("”","\"").replace("‘","\"").replace("’","\"")
    if s.count("\"")==0 and "'" in s: s=s.replace("'","\"")
    return s

def load_cfg():
    default = {
        "site_title":"Accesorios Camper Pro","base_url":DEFAULT_BASE_URL,
        "amazon_partner_tag":"tu-tag-21","amazon_access_key":"","amazon_secret_key":"",
        "auto_daily_new_posts":2,
        "categories":[{"slug":"energia-camper","title":"Energía y Baterías para Camper","keywords":["bateria litio camper 100ah"]}],
        "about":{"title":"Quiénes somos","body":"Proyecto de entusiastas del vanlife."},
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

# ====== TEMPLATES & STYLE ======
BASE_HEAD = """<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title_tag }}</title>
<meta name="description" content="{{ meta_description }}">
<meta property="og:title" content="{{ title_tag }}"><meta property="og:description" content="{{ meta_description }}">
<meta property="og:type" content="website">{% if canonical %}<meta property="og:url" content="{{ canonical }}"><link rel="canonical" href="{{ canonical }}">{% endif %}
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="{{ base }}static/style.css">
</head><body>
<header><div class="wrap">
  <a class="logo" href="{{ base }}">🚐 {{ site_title }}</a>
  <nav><a href="{{ base }}sobre/">Sobre</a><a href="{{ base }}contacto/">Contacto</a><a href="{{ base }}legal/">Legal</a></nav>
</div></header>
<main class="wrap">"""
TAIL = """</main>
<footer><div class="wrap"><p>{{ disclosure }}</p><p>© {{ year }} {{ site_title }} · Hecho con automatización.</p></div></footer>
</body></html>"""

INDEX_TMPL = Template("""{{ head }}
<section class="hero"><h1>{{ site_title }}</h1><p>Guías y comparativas de accesorios para furgonetas camper. Precios al día si la API está activa.</p></section>
<section class="grid">
{% for cat in cats %}
<a class="card" href="{{ base }}{{ cat.slug }}/">
  <div class="card-body"><h2>{{ cat.title }}</h2><p>{{ cat.desc }}</p></div>
</a>
{% endfor %}
</section>
<section><h2>Últimas publicaciones</h2>
<ul class="posts">{% for slug, title, date in recent %}<li><a href="{{ base }}{{ slug }}/">{{ title }}</a><span class="muted"> · {{ date }}</span></li>{% endfor %}</ul>
</section>
{{ tail }}""")

CAT_TMPL = Template("""{{ head }}
<h1>{{ h1 }}</h1><p>{{ intro }}</p>
<table class="table"><thead><tr><th>Producto</th><th>Precio</th><th>Disponibilidad</th><th></th></tr></thead><tbody>{{ rows|safe }}</tbody></table>
{{ tail }}""")

POST_TMPL = Template("""{{ head }}
<article class="post">
<h1>{{ h1 }}</h1><p class="muted">Actualizado {{ updated }}</p>
{% if image %}<figure class="pimg"><img src="{{ image }}" alt="{{ h1 }}" loading="lazy"></figure>{% endif %}
<p>{{ intro }}</p>
{{ table }}
<section><h2>Cómo elegir</h2><ul>{% for t in tips %}<li>{{ t }}</li>{% endfor %}</ul></section>
<section><h2>Preguntas frecuentes</h2>{% for q,a in faqs %}<h3>{{ q }}</h3><p>{{ a }}</p>{% endfor %}</section>
<nav class="muted"><p>También puede interesarte: {% for s,t in related %}<a href="{{ base }}{{ s }}/">{{ t }}</a>{% if not loop.last %} · {% endif %}{% endfor %}</p></nav>
</article>
{% if product_ld %}<script type="application/ld+json">{{ product_ld|safe }}</script>{% endif %}
{{ tail }}""")

PAGE_TMPL = Template("""{{ head }}<article class="page"><h1>{{ h1 }}</h1>{{ body|safe }}</article>{{ tail }}""")

STYLE = """
:root{--bg:#fff;--fg:#0f172a;--muted:#667085;--card:#f6f7f9;--pri:#111827;--br:#e5e7eb}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,Segoe UI,Roboto,Arial,sans-serif;color:var(--fg);background:var(--bg);line-height:1.65}
.wrap{max-width:1088px;margin:0 auto;padding:16px}
header{background:#fafafa;border-bottom:1px solid var(--br)}.logo{font-weight:700;text-decoration:none;color:var(--pri)}
nav{display:flex;gap:16px}.hero{padding:24px 0;border-bottom:1px solid var(--br)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin:18px 0}
.card{background:var(--card);border:1px solid var(--br);border-radius:14px;text-decoration:none;color:inherit;display:block;transition:transform .05s}
.card:hover{transform:translateY(-2px)}.card-body{padding:16px}.card h2{margin:6px 0}.muted{color:var(--muted)}
.table{width:100%;border-collapse:collapse;margin:16px 0}.table th,.table td{border:1px solid var(--br);padding:10px;vertical-align:top}
.bb-btn{display:inline-block;padding:8px 12px;border:1px solid var(--pri);border-radius:10px;text-decoration:none}
.bb-price{font-weight:700}.pimg img{max-width:100%;height:auto;border:1px solid var(--br);border-radius:12px}
footer{margin-top:32px;border-top:1px solid var(--br);background:#fafafa}
"""

def head_meta(title, desc, canonical, base, site_title):
    return Template(BASE_HEAD).render(title_tag=title, meta_description=desc, canonical=canonical,
                                      base=base, site_title=site_title)

def tail_meta(disclosure, site_title):
    return Template(TAIL).render(disclosure=site_title and CFG["legal"]["disclosure"] or "",
                                 year=datetime.datetime.utcnow().year, site_title=site_title)

# ====== Amazon PA-API ======
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
    if r.status_code>=400: raise RuntimeError(f"PA-API {r.status_code}: {r.text[:200]}")
    return r.json()

def pa_search(tag, kw, access, secret, count=10):
    payload={"Keywords":kw,"SearchIndex":"All","ItemCount":count,"PartnerTag":tag,"PartnerType":"Associates",
             "Resources":["Images.Primary.Medium","ItemInfo.Title","ItemInfo.Features","Offers.Listings.Price","Offers.Listings.Availability"]}
    target="com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
    return _pa_call("/paapi5/searchitems", payload, target, access, secret)

# ====== Tablas / Fallback ======
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
        img_html = (f'<img src="{img}" alt="{title}" width="64" height="64" loading="lazy" style="border-radius:8px;border:1px solid #e5e7eb">' if img else "")
        card = "<div style='display:flex;gap:10px;align-items:flex-start'>"+img_html+f"<div><strong>{title}</strong>{bullets}</div></div>"
        rows.append(f"<tr><td>{card}</td><td><span class='bb-price'>{price}</span></td><td>{avail}</td><td><a class='bb-btn' rel='sponsored nofollow' target='_blank' href='{link}'>Comprar</a></td></tr>")
    if not rows: return "<tr><td colspan='4'>Sin resultados hoy. Vuelve más tarde.</td></tr>"
    return "\n".join(rows)

def links_table(tag, keywords):
    rows=[]
    for kw in keywords[:6]:
        link=f"https://www.amazon.es/s?k={quote(kw)}&tag={tag}"
        rows.append(f"<tr><td><strong>{kw.title()}</strong></td><td>-</td><td>-</td><td><a class='bb-btn' rel='sponsored nofollow' target='_blank' href='{link}'>Ver opciones</a></td></tr>")
    if not rows: return "<tr><td colspan='4'>Sin datos.</td></tr>"
    return "\n".join(rows)

def unsplash_fallback(term):
    # imagen temática libre para que la página se vea profesional aunque no haya fotos de producto
    q = quote(f"camper van,{term}")
    return f"https://source.unsplash.com/800x520/?{q}"

def product_ld(name, url, img, price):
    data={"@context":"https://schema.org","@type":"Product","name":name}
    if url: data["url"]=url
    if img: data["image"]=img
    if price and isinstance(price,str) and price not in ("Consultar","-"):
        data["offers"]={"@type":"Offer","price":re.sub(r"[^0-9,\.]","",price).replace(",","."),"priceCurrency":"EUR","availability":"https://schema.org/InStock"}
    return json.dumps(data, ensure_ascii=False)

# ====== Escritura de páginas ======
def list_slugs():
    out=[]
    for root,_,files in os.walk("public"):
        if "index.html" in files:
            slug=root.replace("public","").strip("/")
            out.append(slug)
    return sorted(out)

def write_static_pages(cfg):
    write("static/style.css", STYLE)
    # Sobre / Contacto / Legal (base ../ para cargar CSS correctamente)
    head=head_meta(cfg["about"]["title"], "Información del proyecto", BASE_URL+"sobre/" if BASE_URL else "", "../", cfg["site_title"])
    body=f"<p>{cfg['about']['body']}</p><p><em>{cfg['legal']['disclosure']}</em></p>"
    write("sobre/index.html", PAGE_TMPL.render(head=head, h1=cfg["about"]["title"], body=body, tail=tail_meta(cfg["legal"]["disclosure"], cfg["site_title"])))
    head=head_meta("Contacto", "Cómo contactar", BASE_URL+"contacto/" if BASE_URL else "", "../", cfg["site_title"])
    body=f"<p>Escríbenos a <a href='mailto:{cfg['contact']['email']}'>{cfg['contact']['email']}</a>.</p>"
    write("contacto/index.html", PAGE_TMPL.render(head=head, h1="Contacto", body=body, tail=tail_meta(cfg["legal"]["disclosure"], cfg["site_title"])))
    head=head_meta("Información legal", "Política y términos", BASE_URL+"legal/" if BASE_URL else "", "../", cfg["site_title"])
    body=f"<h2>Aviso de afiliación</h2><p>{cfg['legal']['disclosure']}</p><h2>Privacidad</h2><p>{cfg['legal']['privacy']}</p><h2>Términos</h2><p>{cfg['legal']['terms']}</p>"
    write("legal/index.html", PAGE_TMPL.render(head=head, h1="Información legal", body=body, tail=tail_meta(cfg["legal"]["disclosure"], cfg["site_title"])))

def write_home(cfg, recent):
    cats=[type("C",(),{"slug":c["slug"],"title":c["title"],"desc": (c["keywords"][0] if c.get("keywords") else "")}) for c in cfg["categories"]]
    head=head_meta(cfg["site_title"], "Guías y comparativas camper", BASE_URL if BASE_URL else "", "./", cfg["site_title"])
    html=INDEX_TMPL.render(head=head, cats=cats, base="./", site_title=cfg["site_title"], recent=recent, tail=tail_meta(cfg["legal"]["disclosure"], cfg["site_title"]))
    write("index.html", html)

def write_sitemap_and_robots(base_url):
    urls=[]
    for slug in list_slugs():
        urls.append((base_url.rstrip("/") + ("/" if not slug else f"/{slug}/")) if base_url else ("/" if not slug else f"/{slug}/"))
    today=datetime.datetime.utcnow().strftime("%Y-%m-%d")
    sm=["<?xml version='1.0' encoding='UTF-8'?>","<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    sm+= [f"<url><loc>{u}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>" for u in urls]
    sm.append("</urlset>")
    write("sitemap.xml","\n".join(sm))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {(base_url.rstrip('/')+'/sitemap.xml') if base_url else '/sitemap.xml'}")

def build_category(cfg, cat):
    tag=cfg["amazon_partner_tag"]; access=cfg["amazon_access_key"]; secret=cfg["amazon_secret_key"]
    items=[]; rows=""
    if access and secret:
        for kw in cat.get("keywords",[])[:3]:
            try:
                r=pa_search(tag, kw, access, secret, count=6)
                items += r.get("ItemsResult",{}).get("Items",[])
                time.sleep(0.5)
            except Exception as e:
                write("_logs/paapi_last_error.txt", f"{datetime.datetime.utcnow()}: {e}")
    # dedup
    seen=set(); items2=[]
    for it in items:
        a=it.get("ASIN")
        if a and a not in seen: items2.append(it); seen.add(a)
    items=items2[:12]
    rows = product_table(items, tag) if items else links_table(tag, cat.get("keywords",[]))
    h1=cat["title"]; intro="Selección automática con datos de Amazon (si API activa)."
    head=head_meta(h1, f"Comparativa de {h1}", BASE_URL+cat["slug"]+"/" if BASE_URL else "", "../", CFG["site_title"])
    html=CAT_TMPL.render(head=head, h1=h1, intro=intro, rows=rows, tail=tail_meta(CFG["legal"]["disclosure"], CFG["site_title"]))
    write(f"{cat['slug']}/index.html", html)
    return items[:1] if items else []

def write_post_from_keyword(cfg, cat_slug, kw):
    tag=cfg["amazon_partner_tag"]; access=cfg["amazon_access_key"]; secret=cfg["amazon_secret_key"]
    slug=f"{cat_slug}/{slugify(kw)}"
    h1=kw.title()
    image=""; price=None; table="<p>Sin datos hoy.</p>"; pld=""
    if access and secret:
        try:
            r=pa_search(tag, kw, access, secret, count=6)
            items=r.get("ItemsResult",{}).get("Items",[])
            table="<table class='table'><thead><tr><th>Producto</th><th>Precio</th><th>Disponibilidad</th><th></th></tr></thead><tbody>"+product_table(items, tag)+"</tbody></table>"
            if items:
                it=items[0]
                image=it.get("Images",{}).get("Primary",{}).get("Medium",{}).get("URL","") or ""
                price=it.get("Offers",{}).get("Listings",[{}])[0].get("Price",{}).get("DisplayAmount")
                link=f"https://www.amazon.es/dp/{it.get('ASIN','')}?tag={tag}"
                pld=product_ld(h1, link, image, price)
        except Exception as e:
            write("_logs/paapi_last_error.txt", f"{datetime.datetime.utcnow()}: {e}")
    if not image:
        image = unsplash_fallback(kw)
    tips=["Define presupuesto y tamaño.","Revisa garantía y repuestos.","Evita extras que no usarás."]
    faqs=[("¿Cambian los precios?","Sí, Amazon los actualiza."),("¿Afecta el afiliado al precio?","No."),("¿Cómo elegimos?","Disponibilidad, reputación y especificaciones.")]
    head=head_meta(h1, f"Guía: {h1}", BASE_URL+slug+"/" if BASE_URL else "", "../", CFG["site_title"])
    html=POST_TMPL.render(head=head, h1=h1, updated=datetime.datetime.utcnow().strftime("%Y-%m-%d"),
                          intro="Comparativa generada automáticamente.", table=table, tips=tips, faqs=faqs,
                          related=[], tail=tail_meta(CFG["legal"]["disclosure"], CFG["site_title"]),
                          base="../", image=image, product_ld=pld)
    write(f"{slug}/index.html", html)
    return slug, h1

def run_autodiscover(cfg):
    recent=[]
    for cat in cfg["categories"]:
        build_category(cfg, cat)
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
        # lista últimos 10
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

def main():
    ensure_dirs()
    run_autodiscover(CFG)

if __name__=="__main__":
    main()

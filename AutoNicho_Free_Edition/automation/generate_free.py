import os, json, re, datetime, requests
from jinja2 import Template
from automation.paapi import paapi_get_items
PARTNER_TAG = os.environ.get("AMAZON_PARTNER_TAG", "")
CFWA = os.environ.get("CLOUDFLARE_WEB_ANALYTICS_TOKEN", "")
HEAD = """<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title_tag }}</title>
<meta name="description" content="{{ meta_description }}">
{% if cfwa %}<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token": "{{ cfwa }}"}'></script>{% endif %}
<script defer src="/static/buybox.js"></script>
<link rel="stylesheet" href="/static/style.css">
</head><body><header><a href="/">AutoNicho</a></header><main>"""
TAIL = """</main><footer><p>(c) AutoNicho Free - Enlaces patrocinados (afiliado).</p></footer></body></html>"""
POST_TMPL = Template("""{{ head }}
<article>
<h1>{{ h1 }}</h1>
<p>{{ intro }}</p>
{{ table }}
<section><h2>Como elegir</h2><ul>{% for tip in tips %}<li>{{ tip }}</li>{% endfor %}</ul></section>
<section><h2>Preguntas frecuentes</h2>{% for q,a in faqs %}<h3>{{ q }}</h3><p>{{ a }}</p>{% endfor %}</section>
<nav><p>Tambien puede interesarte: {% for slug, title in related %}<a href="/{{ slug }}/">{{ title }}</a>{% if not loop.last %} · {% endif %}{% endfor %}</p></nav>
</article>{{ tail }}""")
INDEX_TMPL = Template("""{{ head }}<h1>Guias y comparativas</h1><ul>{% for slug, title, desc in posts %}<li><a href="/{{ slug }}/">{{ title }}</a><br><small>{{ desc }}</small></li>{% endfor %}</ul>{{ tail }}""")
def ensure_dirs(): os.makedirs("public", exist_ok=True); os.makedirs("public/static", exist_ok=True)
def write(path, content):
    path = os.path.join("public", path.lstrip("/")); os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(content)
def load_posts_list():
    idx=[]; 
    for root,_,files in os.walk("public"):
        for f in files:
            if f=="index.html" and root!="public":
                slug=root.replace("public","").strip("/")
                txt=open(os.path.join(root,f),"r",encoding="utf-8").read()
                t=re.search(r"<h1>(.*?)</h1>",txt,re.S); d=re.search(r"<p>(.*?)</p>",txt,re.S)
                idx.append((slug,t.group(1) if t else slug,(d.group(1)[:160]+'...') if d else ""))
    return sorted(idx)[:200]
def describe_item(it):
    title=(it.get("ItemInfo",{}).get("Title",{}).get("DisplayValue") or "").strip()
    feats=it.get("ItemInfo",{}).get("Features",{}).get("DisplayValues") or []
    bullets=[f for f in feats if isinstance(f,str)][:5]; return title, bullets
def build_table(api, tag):
    rows=[]
    for it in api.get("ItemsResult",{}).get("Items",[]):
        asin=it.get("ASIN",""); title,bullets=describe_item(it)
        price=it.get("Offers",{}).get("Listings",[{}])[0].get("Price",{}).get("DisplayAmount","Consultar")
        avail=it.get("Offers",{}).get("Listings",[{}])[0].get("Availability",{}).get("Message","")
        link=f"https://www.amazon.es/dp/{asin}?tag={tag}"
        bl="<ul>"+"".join([f"<li>{b}</li>" for b in bullets])+"</ul>" if bullets else ""
        rows.append(f"<tr><td><strong>{title or asin}</strong>{bl}</td><td><span class='bb-price' id='price-{asin}'>{price}</span></td><td>{avail}</td><td><div class='buybox' data-asin='{asin}'><a class='bb-btn' rel='sponsored nofollow' target='_blank' href='{link}'>Ver precio</a></div></td></tr>")
    if not rows: return "<p>No se pudo cargar la tabla.</p>"
    return "<table><thead><tr><th>Modelo</th><th>Precio</th><th>Disponibilidad</th><th></th></tr></thead><tbody>"+"".join(rows)+"</tbody></table>"
def write_index():
    posts=load_posts_list()
    head=Template(HEAD).render(title_tag="AutoNicho Free - guias y comparativas", meta_description="Listas y comparativas generadas automaticamente con datos de Amazon.", cfwa=CFWA)
    html=INDEX_TMPL.render(head=head, posts=posts, tail=TAIL); write("index.html", html)
def write_sitemap():
    urls=["/"]; 
    for root,_,files in os.walk("public"):
        for f in files:
            if f=="index.html" and root!="public":
                slug=root.replace("public","").strip("/"); urls.append(f"/{slug}/")
    sm=["<?xml version='1.0' encoding='UTF-8'?>","<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    now=datetime.datetime.utcnow().strftime("%Y-%m-%d")
    for u in urls: sm+= [f"<url><loc>{u}</loc><lastmod>{now}</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>"]
    sm.append("</urlset>"); write("sitemap.xml","\n".join(sm)); write("robots.txt", "User-agent: *\nAllow: /\n")
def main():
    ensure_dirs()
    seeds=json.load(open("seeds.json","r",encoding="utf-8"))
    cats=seeds.get("categories",[])[:2]
    existing=set([p[0] for p in load_posts_list()])
    for cat in cats:
        slug=cat["slug"]; 
        if slug in existing: continue
        asins=cat.get("asins",[])[:5]
        api=paapi_get_items(asins) if asins else {}
        table=build_table(api, PARTNER_TAG)
        h1=cat.get("title","Guia de compra")
        intro="Comparativa rapida con datos oficiales de Amazon. Revisa el precio actualizado en el boton."
        tips=["Define presupuesto y tamano.","Mira garantia y repuestos.","Evita pagar extras que no usaras."]
        faqs=[("Cambian los precios?","Si, Amazon los actualiza."),("Influye el afiliado en el precio?","No."),("Como elegimos?","Disponibilidad, reputacion y especificaciones.")]
        head=Template(HEAD).render(title_tag=h1, meta_description=f"Guia rapida: {h1}.", cfwa=CFWA)
        related=[(rslug,rtitle) for rslug,rtitle,_ in load_posts_list()[:3]]
        html=POST_TMPL.render(head=head, h1=h1, intro=intro, table=table, tips=tips, faqs=faqs, related=related, tail=TAIL)
        write(f"{slug}/index.html", html)
    write_index(); write_sitemap()
if __name__=="__main__": main()

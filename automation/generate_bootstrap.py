# automation/generate_bootstrap.py
# Genera un sitio estatico en /public leyendo configuracion de automation/bootstrap.json
# - Si el JSON trae amazon_access_key/secret -> intenta PA-API SearchItems (cabeceras firmadas)
# - Si no, publica sin precios ni bullets (solo botones "Ver precio" con tu tag)

import os, json, re, datetime, hashlib, hmac, requests
from jinja2 import Template

CONFIG_PATH = os.environ.get("BOOTSTRAP_JSON_PATH", "automation/bootstrap.json")
os.makedirs("public/static", exist_ok=True)

HEAD = """<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title_tag }}</title>
<meta name="description" content="{{ meta_description }}">
<link rel="stylesheet" href="/static/style.css">
</head><body><header><a href="/">AutoNicho</a></header><main>"""
TAIL = """</main><footer><p>(c) AutoNicho - Enlaces patrocinados (afiliado).</p></footer></body></html>"""

POST_TMPL = Template("""{{ head }}
<article>
<h1>{{ h1 }}</h1>
<p>{{ intro }}</p>
{{ table }}
<section><h2>Cómo elegir</h2><ul>{% for t in tips %}<li>{{ t }}</li>{% endfor %}</ul></section>
<section><h2>Preguntas frecuentes</h2>{% for q,a in faqs %}<h3>{{ q }}</h3><p>{{ a }}</p>{% endfor %}</section>
<nav><p>También puede interesarte: {% for slug, title in related %}<a href="/{{ slug }}/">{{ title }}</a>{% if not loop.last %} · {% endif %}{% endfor %}</p></nav>
</article>{{ tail }}""")

INDEX_TMPL = Template("""{{ head }}
<h1>{{ site_title }}</h1>
<ul>
{% for slug, title, desc in posts %}
<li><a href="/{{ slug }}/">{{ title }}</a><br><small>{{ desc }}</small></li>
{% endfor %}
</ul>{{ tail }}""")

STYLE = "body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;margin:0;padding:0;line-height:1.6}header,footer{background:#f6f6f7;padding:12px 16px}main{max-width:920px;margin:0 auto;padding:16px}table{width:100%;border-collapse:collapse;margin:16px 0}th,td{border:1px solid #ddd;padding:8px;text-align:left}.bb-btn{display:inline-block;padding:8px 12px;border:1px solid #111;border-radius:8px;text-decoration:none}.bb-price{font-weight:600}"

def write(path, content):
    path = os.path.join("public", path.lstrip("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def load_posts_list():
    idx=[]
    for root,_,files in os.walk("public"):
        for f in files:
            if f=="index.html" and root!="public":
                slug=root.replace("public","").strip("/")
                txt=open(os.path.join(root,f),"r",encoding="utf-8").read()
                t=re.search(r"<h1>(.*?)</h1>",txt,re.S); d=re.search(r"<p>(.*?)</p>",txt,re.S)
                idx.append((slug, t.group(1) if t else slug, (d.group(1)[:160]+"...") if d else ""))
    return sorted(idx)[:200]

# --------- PA-API helpers (solo si hay claves) ----------
AWS_REGION="eu-west-1"; HOST="webservices.amazon.es"; SERVICE="ProductAdvertisingAPI"
def _sign(key,msg): return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
def _sig_key(key,dateStamp,regionName,serviceName):
    kDate=_sign(("AWS4"+key).encode("utf-8"),dateStamp)
    kRegion=_sign(kDate,regionName); kService=_sign(kRegion,serviceName)
    return _sign(kService,"aws4_request")
def _pa_call(path,payload,amz_target,access_key,secret_key):
    now=datetime.datetime.utcnow(); amz_date=now.strftime("%Y%m%dT%H%M%SZ"); date_stamp=now.strftime("%Y%m%d")
    endpoint=f"https://{HOST}{path}"; body=json.dumps(payload)
    canonical_headers=( "content-encoding:amz-1.0\ncontent-type:application/json; charset=utf-8\n"
                        f"host:{HOST}\n"+"x-amz-date:"+amz_date+"\n"+"x-amz-target:"+amz_target+"\n")
    signed_headers="content-encoding;content-type;host;x-amz-date;x-amz-target"
    payload_hash=hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request="POST\n{}\n{}\n{}\n{}\n{}".format(path,"",canonical_headers,signed_headers,payload_hash)
    algorithm="AWS4-HMAC-SHA256"; scope=f"{date_stamp}/{AWS_REGION}/{SERVICE}/aws4_request"
    string_to_sign="{}\n{}\n{}\n{}".format(algorithm,amz_date,scope,hashlib.sha256(canonical_request.encode("utf-8")).hexdigest())
    signing_key=_sig_key(secret_key,date_stamp,AWS_REGION,SERVICE)
    signature=hmac.new(signing_key,string_to_sign.encode("utf-8"),hashlib.sha256).hexdigest()
    headers={
        "content-encoding":"amz-1.0","content-type":"application/json; charset=utf-8",
        "x-amz-date":amz_date,"x-amz-target":amz_target,
        "Authorization":f"{algorithm} Credential={access_key}/{scope}, SignedHeaders={signed_headers}, Signature={signature}",
        "Accept":"application/json",
    }
    r=requests.post(endpoint,data=body,headers=headers,timeout=30); r.raise_for_status(); return r.json()

def paapi_search_items(tag, kw, access, secret, count=10):
    payload={"Keywords":kw,"SearchIndex":"All","ItemCount":count,"PartnerTag":tag,"PartnerType":"Associates",
             "Resources":["Images.Primary.Medium","ItemInfo.Title","ItemInfo.Features","Offers.Listings.Price","Offers.Listings.Availability"]}
    target="com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
    return _pa_call("/paapi5/searchitems", payload, target, access, secret)

# --------------------------------------------------------

def table_from_items(items, tag):
    rows=[]
    for it in items.get("ItemsResult",{}).get("Items",[]):
        asin=it.get("ASIN","")
        title=(it.get("ItemInfo",{}).get("Title",{}).get("DisplayValue") or asin)[:100]
        feats=it.get("ItemInfo",{}).get("Features",{}).get("DisplayValues") or []
        bullets="<ul>"+"".join([f"<li>{b}</li>" for b in feats[:5]])+"</ul>" if feats else ""
        price=it.get("Offers",{}).get("Listings",[{}])[0].get("Price",{}).get("DisplayAmount","Consultar")
        avail=it.get("Offers",{}).get("Listings",[{}])[0].get("Availability",{}).get("Message","")
        link=f"https://www.amazon.es/dp/{asin}?tag={tag}"
        rows.append(f"<tr><td><strong>{title}</strong>{bullets}</td><td><span class='bb-price'>{price}</span></td><td>{avail}</td><td><a class='bb-btn' rel='sponsored nofollow' target='_blank' href='{link}'>Ver precio</a></td></tr>")
    if not rows:
        return "<p>Sin datos de PA-API hoy. Usa el botón para ver precio actualizado en Amazon.</p>"
    return "<table><thead><tr><th>Modelo</th><th>Precio</th><th>Disponibilidad</th><th></th></tr></thead><tbody>"+"".join(rows)+"</tbody></table>"

def table_links_only(tag, keywords):
    # Fallback sin PA-API: 6 enlaces directos a búsquedas en Amazon (compliant y evergreen)
    rows=[]
    for kw in keywords[:6]:
        link=f"https://www.amazon.es/s?k={requests.utils.quote(kw)}&tag={tag}"
        rows.append(f"<tr><td><strong>{kw.title()}</strong></td><td>-</td><td>-</td><td><a class='bb-btn' rel='sponsored nofollow' target='_blank' href='{link}'>Ver opciones</a></td></tr>")
    return "<table><thead><tr><th>Búsqueda</th><th>Precio</th><th>Disponibilidad</th><th></th></tr></thead><tbody>"+"".join(rows)+"</tbody></table>"

def main():
    cfg=json.load(open(CONFIG_PATH,"r",encoding="utf-8"))
    tag=cfg.get("amazon_partner_tag","").strip()
    access=cfg.get("amazon_access_key","").strip()
    secret=cfg.get("amazon_secret_key","").strip()
    site_title=cfg.get("site_title","AutoNicho")
    cats=cfg.get("categories",[])[:3]

    # estilo
    write("static/style.css", STYLE)

    posts_meta=[]

    for cat in cats:
        slug=cat["slug"]; title=cat["title"]; kws=cat.get("keywords",[])
        h1=title; intro="Comparativa generada automáticamente. Haz clic para ver precio actualizado en Amazon."
        tips=["Define presupuesto y tamaño.","Revisa garantía y repuestos.","Evita extras que no usarás."]
        faqs=[("¿Cambian los precios?","Sí, Amazon los actualiza."),("¿Afecta el afiliado al precio?","No."),("¿Cómo elegimos?","Disponibilidad, reputación y especificaciones.")]
        # tabla
        if access and secret:
            items={"ItemsResult":{"Items":[]}}
            try:
                for kw in kws[:2]:
                    res=paapi_search_items(tag, kw, access, secret, count=6)
                    items["ItemsResult"]["Items"] += res.get("ItemsResult",{}).get("Items",[])
            except Exception:
                pass
            table=table_from_items(items, tag)
        else:
            table=table_links_only(tag, kws if kws else [title])

        # related
        related=[(s,t) for s,t,_ in posts_meta[:3]]
        head=Template(HEAD).render(title_tag=title, meta_description=f"Guía rápida: {title}.", )
        html=POST_TMPL.render(head=head, h1=h1, intro=intro, table=table, tips=tips, faqs=faqs, related=related, tail=TAIL)
        write(f"{slug}/index.html", html)
        posts_meta.append((slug,title,"Selección automática y enlaces directos a Amazon."))

    # index
    head=Template(HEAD).render(title_tag=site_title, meta_description="Listas y comparativas automatizadas, sin intervención.",)
    index=INDEX_TMPL.render(head=head, posts=posts_meta, site_title=site_title, tail=TAIL)
    write("index.html", index)

if __name__ == "__main__":
    main()

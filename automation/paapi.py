# automation/paapi.py
import hashlib, hmac, datetime, json, requests, os

AWS_REGION = "eu-west-1"
HOST = "webservices.amazon.es"
SERVICE = "ProductAdvertisingAPI"

ACCESS_KEY = os.environ.get("AMAZON_ACCESS_KEY", "")
SECRET_KEY = os.environ.get("AMAZON_SECRET_KEY", "")
PARTNER_TAG = os.environ.get("AMAZON_PARTNER_TAG", "")

def _sign(key, msg): 
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def _sig_key(key, dateStamp, regionName, serviceName):
    kDate = _sign(("AWS4" + key).encode("utf-8"), dateStamp)
    kRegion = _sign(kDate, regionName)
    kService = _sign(kRegion, serviceName)
    kSigning = _sign(kService, "aws4_request")
    return kSigning

def _call(path, payload, amz_target):
    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    endpoint = f"https://{HOST}{path}"
    body = json.dumps(payload)

    # --- Canonical request (incluye x-amz-target) ---
    canonical_uri = path
    canonical_querystring = ""
    canonical_headers = (
        "content-encoding:amz-1.0\n"
        "content-type:application/json; charset=utf-8\n"
        f"host:{HOST}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-target:{amz_target}\n"
    )
    signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
    payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request = (
        "POST\n{}\n{}\n{}\n{}\n{}".format(
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        )
    )

    # --- String to sign ---
    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{AWS_REGION}/{SERVICE}/aws4_request"
    string_to_sign = "{}\n{}\n{}\n{}".format(
        algorithm,
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    )

    signing_key = _sig_key(SECRET_KEY, date_stamp, AWS_REGION, SERVICE)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    headers = {
        "content-encoding": "amz-1.0",
        "content-type": "application/json; charset=utf-8",
        "x-amz-date": amz_date,
        "x-amz-target": amz_target,
        "Authorization": f"{algorithm} Credential={ACCESS_KEY}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}",
        "Accept": "application/json",
    }

    r = requests.post(endpoint, data=body, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def paapi_get_items(asins):
    payload = {
        "ItemIds": asins,
        "PartnerTag": PARTNER_TAG,
        "PartnerType": "Associates",
        "Resources": [
            "Images.Primary.Medium",
            "ItemInfo.Title",
            "ItemInfo.Features",
            "Offers.Listings.Price",
            "Offers.Listings.Availability",
        ],
    }
    target = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems"
    return _call("/paapi5/getitems", payload, target)

def paapi_search_items(keywords, item_count=10):
    payload = {
        "Keywords": keywords,
        "SearchIndex": "All",
        "ItemCount": item_count,
        "PartnerTag": PARTNER_TAG,
        "PartnerType": "Associates",
        "Resources": [
            "Images.Primary.Medium",
            "ItemInfo.Title",
            "ItemInfo.Features",
            "Offers.Listings.Price",
            "Offers.Listings.Availability",
        ],
    }
    target = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
    return _call("/paapi5/searchitems", payload, target)

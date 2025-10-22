import hashlib, hmac, datetime, json, requests, os
AWS_REGION = "eu-west-1"
HOST = "webservices.amazon.es"
ENDPOINT = f"https://{HOST}/paapi5/getitems"
SERVICE = "ProductAdvertisingAPI"
ACCESS_KEY = os.environ.get("AMAZON_ACCESS_KEY", "")
SECRET_KEY = os.environ.get("AMAZON_SECRET_KEY", "")
PARTNER_TAG = os.environ.get("AMAZON_PARTNER_TAG", "")
def sign(key, msg): return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
def get_signature_key(key, dateStamp, regionName, serviceName):
    kDate = sign(("AWS4" + key).encode('utf-8'), dateStamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    kSigning = sign(kService, "aws4_request")
    return kSigning
def paapi_get_items(asins):
    now = datetime.datetime.utcnow()
    amz_date = now.strftime('%Y%m%dT%H%M%SZ'); date_stamp = now.strftime('%Y%m%d')
    payload = {"ItemIds": asins, "PartnerTag": PARTNER_TAG, "PartnerType": "Associates",
               "Resources": ["Images.Primary.Medium","ItemInfo.Title","ItemInfo.Features","Offers.Listings.Price","Offers.Listings.Availability"]}
    body = json.dumps(payload)
    canonical_uri = "/paapi5/getitems"; canonical_querystring = ""
    canonical_headers = f"content-encoding:amz-1.0\ncontent-type:application/json; charset=utf-8\nhost:{HOST}\nx-amz-date:{amz_date}\n"
    signed_headers = "content-encoding;content-type;host;x-amz-date"
    import hashlib as _hl
    payload_hash = _hl.sha256(body.encode('utf-8')).hexdigest()
    canonical_request = "POST\n{}\n{}\n{}\n{}\n{}".format(canonical_uri, canonical_querystring, canonical_headers, signed_headers, payload_hash)
    algorithm = "AWS4-HMAC-SHA256"; credential_scope = f"{date_stamp}/{AWS_REGION}/{SERVICE}/aws4_request"
    string_to_sign = "{}\n{}\n{}\n{}".format(algorithm, amz_date, credential_scope, _hl.sha256(canonical_request.encode('utf-8')).hexdigest())
    signing_key = get_signature_key(SECRET_KEY, date_stamp, AWS_REGION, SERVICE)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {"content-encoding":"amz-1.0","content-type":"application/json; charset=utf-8","x-amz-date":amz_date,
               "Authorization": f"{algorithm} Credential={ACCESS_KEY}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"}
    r = requests.post(ENDPOINT, data=body, headers=headers, timeout=30); r.raise_for_status(); return r.json()

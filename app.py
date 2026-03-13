from flask import Flask, request, jsonify, render_template
import requests, json, time, base64, os, random
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# ---------- API URLs ----------
TOKEN_URL = "https://jwt-1api-production-c29d.up.railway.app"
SPAM_URL = "https://all-aapi-production.up.railway.app"
INFO_URL = "https://info-api-production-d187.up.railway.app"

ACCOUNTS_FILE = "accounts.json"
TOKEN_FILE = "token.json"

# ---------- SESSION ----------
session = requests.Session()
retry = Retry(total=4, backoff_factor=0.3, status_forcelist=[500,502,503,504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

# ---------- TOKEN UTILS ----------
def load_tokens():
    if not os.path.exists(TOKEN_FILE): return {}
    try:
        with open(TOKEN_FILE,"r") as f: return json.load(f)
    except: return {}

def save_tokens(data):
    with open(TOKEN_FILE,"w") as f: json.dump(data,f)

def token_expired(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return time.time() > data["exp"]
    except: return True

def request_token(uid,password):
    try:
        r = session.get(TOKEN_URL+"/api/token",params={"uid":uid,"password":password},timeout=10)
        j = r.json()
        if j.get("token"):
            tokens = load_tokens()
            tokens[str(uid)] = j["token"]
            save_tokens(tokens)
            return j["token"]
    except: pass
    return None

def get_token(uid,password):
    uid=str(uid)
    tokens=load_tokens()
    if uid in tokens and not token_expired(tokens[uid]): return tokens[uid]
    return request_token(uid,password)

# ---------- WEB PAGES ----------
@app.route("/") 
def home(): return render_template("index.html")

@app.route("/spam") 
def spam_page(): return render_template("spam.html")

@app.route("/info") 
def info_page(): return render_template("info.html")

# ---------- FAST SPAM ENGINE ----------
@app.route("/api/spam_add",methods=["POST"])
def spam_add():
    data = request.get_json(force=True)
    target = data.get("target")
    limit = int(data.get("limit",5))

    if not os.path.exists(ACCOUNTS_FILE):
        return jsonify({"status":"failed","error":"accounts.json missing"})

    with open(ACCOUNTS_FILE) as f:
        accounts = json.load(f)

    random.shuffle(accounts)
    accounts = accounts[:limit]

    success=0; failed=0; duplicate=0; logs=[]

    def send_request(acc):
        uid=acc.get("uid"); password=acc.get("password")
        token = get_token(uid,password)
        if not token: return {"uid":uid,"status":"token_failed"}
        try:
            res = session.get(SPAM_URL+"/add_friend",params={"token":token,"player_id":target},timeout=10).json()
            status=res.get("status","failed")
        except: status="failed"
        return {"uid":uid,"status":status}

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(send_request,accounts))

    for r in results:
        if r["status"]=="success": success+=1
        elif r["status"]=="duplicate": duplicate+=1
        else: failed+=1
        logs.append(r)

    return jsonify({"success":success,"failed":failed,"duplicate":duplicate,"total":len(results),"logs":logs})

# ---------- PLAYER INFO API ----------
@app.route("/api/info",methods=["POST"])
def info():
    data=request.get_json(force=True)
    uid=data.get("uid")
    if not uid: return jsonify({"status":"failed","error":"UID missing"})
    try:
        r = session.get(INFO_URL+"/get",params={"uid":uid,"region":"IND"},timeout=6)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"status":"failed","error":str(e)})

# ---------- SERVER ----------
if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)

from flask import Flask, request, jsonify, render_template
import requests, json, time, os, random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

BASE_URL = "https://all-aapi-production.up.railway.app"
INFO_URL = "https://info-api-production-d187.up.railway.app"
ACCOUNTS_FILE = "accounts.json"
TOKEN_FILE = "token.json"

# ---------------- Session ----------------
session = requests.Session()
retry = Retry(total=3, backoff_factor=0.3)
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

# ---------------- Token Utils ----------------
def load_tokens():
    if not os.path.exists(TOKEN_FILE):
        return {}
    try:
        return json.load(open(TOKEN_FILE))
    except:
        return {}

def save_tokens(data):
    with open(TOKEN_FILE,"w") as f:
        json.dump(data, f, indent=2)

def token_expired(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return time.time() > data.get("exp", 0)
    except:
        return True

def request_token(uid,password):
    try:
        r = session.get(f"{BASE_URL}/token", params={"uid": uid,"password": password}, timeout=5)
        j = r.json()
        if j.get("status")=="success":
            tokens = load_tokens()
            tokens[str(uid)] = j["token"]
            save_tokens(tokens)
            return j["token"]
    except:
        pass
    return None

def get_token(uid,password):
    uid = str(uid)
    tokens = load_tokens()
    if uid in tokens and not token_expired(tokens[uid]):
        return tokens[uid]
    return request_token(uid,password)

# ---------------- Pages ----------------
@app.route("/")
def home():
    return render_template("index.html")

# ---------------- SPAM API ----------------
@app.route("/api/spam_add", methods=["POST"])
def spam_add():
    try:
        data = request.json or {}
        target = data.get("target")
        limit = int(data.get("limit") or 0)
        if not target or limit <= 0:
            return jsonify({"success":0,"failed":0,"duplicate":0,"total":0,"error":"Invalid input"})

        if not os.path.exists(ACCOUNTS_FILE):
            return jsonify({"success":0,"failed":0,"duplicate":0,"total":0,"error":"accounts.json missing"})

        accounts = json.load(open(ACCOUNTS_FILE))
        random.shuffle(accounts)

        success = failed = duplicate = used = 0
        logs = []

        for acc in accounts:
            if used >= limit:
                break

            uid = acc.get("uid")
            password = acc.get("password")

            token = get_token(uid,password)
            if not token:
                failed += 1
                logs.append({"uid": uid, "status": "token_failed"})
                used += 1
                continue

            try:
                res = session.get(BASE_URL+"/add_friend", params={"token": token,"player_id":target}, timeout=8)
                res_json = res.json() if res.text else {}
            except:
                failed += 1
                logs.append({"uid": uid, "status": "timeout"})
                used += 1
                continue

            status = res_json.get("status","failed")
            if status=="success":
                success += 1
            elif status=="duplicate":
                duplicate += 1
            else:
                failed += 1

            logs.append({"uid": uid, "status": status})
            used += 1
            time.sleep(0.2)

        return jsonify({
            "success": success,
            "failed": failed,
            "duplicate": duplicate,
            "total": used,
            "logs": logs
        })

    except Exception as e:
        # Always return JSON to avoid frontend crash
        return jsonify({
            "success":0,
            "failed":0,
            "duplicate":0,
            "total":0,
            "error": str(e)
        })

# ---------------- PLAYER INFO API ----------------
@app.route("/api/info", methods=["POST"])
def info():
    try:
        uid = request.json.get("uid")
        if not uid:
            return jsonify({"status":"failed","error":"UID missing"})

        r = session.get(f"{INFO_URL}/get", params={"uid":uid,"region":"IND"}, timeout=5)
        return jsonify(r.json() if r.text else {"status":"failed","error":"Empty response"})
    except Exception as e:
        return jsonify({"status":"failed","error": str(e)})

# ---------------- START SERVER ----------------
if __name__=="__main__":
    port = int(os.environ.get("PORT",8080))
    app.run(host="0.0.0.0", port=port)

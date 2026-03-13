from flask import Flask, request, jsonify, render_template
import requests, json, time, os, random, base64
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

BASE_URL = "http://127.0.0.1:5999"
INFO_URL = "https://info-api-production-d187.up.railway.app"
ACCOUNTS_FILE = "accounts.json"
TOKEN_FILE = "token.json"

# ---------------- Session ----------------
session = requests.Session()
retry = Retry(total=3, backoff_factor=0.3)
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)
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
                r = session.get(BASE_URL+"/add_friend", params={"token": token,"player_id":target}, timeout=8)
                print("UID:", uid, "Raw Response:", r.text)  # DEBUG LOG
                res_json = r.json() if r.text else {}
            except Exception as e:
                failed += 1
                logs.append({"uid": uid, "status": "timeout"})
                used += 1
                print("UID:", uid, "Request Exception:", e)
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
        print("Spam API Exception:", e)
        return jsonify({"success":0,"failed":0,"duplicate":0,"total":0,"error": str(e)})

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
        print("Info API Exception:", e)
        return jsonify({"status":"failed","error": str(e)})

# ---------------- START SERVER ----------------
if __name__=="__main__":
    port = int(os.environ.get("PORT",8080))
    app.run(host="0.0.0.0", port=port)

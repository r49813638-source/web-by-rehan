from flask import Flask, request, jsonify, render_template
import requests
import json
import time
import base64
import os
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

BASE_URL = "https://all-aapi-production.up.railway.app"
INFO_URL = "https://info-api-production-d187.up.railway.app"

ACCOUNTS_FILE = "accounts.json"
TOKEN_FILE = "token.json"

# -------- Session Setup --------
session = requests.Session()
retry = Retry(total=3, backoff_factor=0.3)
adapter = HTTPAdapter(max_retries=retry)

session.mount("http://", adapter)
session.mount("https://", adapter)

# ---------------- TOKEN UTILS ----------------

def load_tokens():
    if not os.path.exists(TOKEN_FILE):
        return {}

    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_tokens(data):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)

def token_expired(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)

        data = json.loads(base64.urlsafe_b64decode(payload))

        return time.time() > data["exp"]

    except:
        return True

def request_token(uid, password):

    try:
        r = session.get(
            BASE_URL + "/token",
            params={
                "uid": uid,
                "password": password
            },
            timeout=5
        )

        j = r.json()

        if j.get("status") == "success":

            tokens = load_tokens()
            tokens[str(uid)] = j["token"]

            save_tokens(tokens)

            return j["token"]

    except:
        pass

    return None

def get_token(uid, password):

    uid = str(uid)

    tokens = load_tokens()

    if uid in tokens and not token_expired(tokens[uid]):
        return tokens[uid]

    return request_token(uid, password)

# ---------------- WEB PAGES ----------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/spam")
def spam_page():
    return render_template("spam.html")

@app.route("/info")
def info_page():
    return render_template("info.html")

# ---------------- SPAM API ----------------

@app.route("/api/spam_add", methods=["POST"])
def spam_add():

    data = request.json

    target = data["target"]
    limit = int(data["limit"])

    accounts = json.load(open(ACCOUNTS_FILE))

    random.shuffle(accounts)

    success = 0
    failed = 0
    duplicate = 0
    used = 0

    logs = []

    for acc in accounts:

        if used >= limit:
            break

        uid = acc["uid"]
        password = acc["password"]

        token = get_token(uid, password)

        if not token:

            failed += 1

            logs.append({
                "uid": uid,
                "status": "token_failed"
            })

            used += 1
            continue

        try:

            res = session.get(
                BASE_URL + "/add_friend",
                params={
                    "token": token,
                    "player_id": target
                },
                timeout=5
            ).json()

            status = res.get("status", "failed")

        except:

            status = "failed"

        if status == "success":
            success += 1

        elif status == "duplicate":
            duplicate += 1

        else:
            failed += 1

        logs.append({
            "uid": uid,
            "status": status
        })

        used += 1

        time.sleep(0.3)

    return jsonify({
        "success": success,
        "failed": failed,
        "duplicate": duplicate,
        "total": used,
        "logs": logs
    })

# ---------------- PLAYER INFO API ----------------

@app.route("/api/info", methods=["POST"])
def info():

    uid = request.json.get("uid")

    if not uid:
        return jsonify({
            "status": "failed",
            "error": "UID missing"
        })

    try:

        r = session.get(
            f"{INFO_URL}/get",
            params={
                "uid": uid,
                "region": "IND"
            },
            timeout=5
        )

        return jsonify(r.json())

    except Exception as e:

        return jsonify({
            "status": "failed",
            "error": str(e)
        })

# ---------------- START SERVER ----------------

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )

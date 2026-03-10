from flask import Flask, request, jsonify, render_template
import requests
import json
import time
import base64
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

app = Flask(__name__)

BASE_URL = "https://all-aapi-production.up.railway.app"

ACCOUNTS_FILE = "accounts.json"
TOKEN_FILE = "token.json"

INFO_UID = "4423796135"
INFO_PASS = "REHANN9383U383_77AJZ_BY_SPIDEERIO_GAMING_52U0M"

session = requests.Session()

lock = Lock()
used_accounts = set()

# ---------------- TOKEN FUNCTIONS ----------------

def load_tokens():
    if not os.path.exists(TOKEN_FILE):
        return {}

    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_tokens(data):
    try:
        with lock:
            with open(TOKEN_FILE, "w") as f:
                json.dump(data, f, indent=2)
    except:
        pass

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
            params={"uid": uid, "password": password},
            timeout=10
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

# ---------------- WORKER ----------------

def process_account(acc, target):

    uid = str(acc["uid"])
    password = acc["password"]

    with lock:
        if uid in used_accounts:
            return {"uid": uid, "status": "skipped"}

    token = get_token(uid, password)

    if not token:
        return {"uid": uid, "status": "token_failed"}

    try:

        r = session.get(
            BASE_URL + "/add_friend",
            params={
                "token": token,
                "player_id": target
            },
            timeout=10
        )

        j = r.json()

        status = j.get("status", "failed")

        if status == "success":
            with lock:
                used_accounts.add(uid)

        return {"uid": uid, "status": status}

    except:
        return {"uid": uid, "status": "failed"}

# ---------------- SPAM API ----------------

@app.route("/api/spam_add", methods=["POST"])
def spam_add():

    data = request.json

    target = data.get("target")
    limit = int(data.get("limit", 0))

    if not os.path.exists(ACCOUNTS_FILE):
        return jsonify({"error": "accounts.json missing"})

    try:
        with open(ACCOUNTS_FILE) as f:
            accounts = json.load(f)
    except:
        return jsonify({"error": "accounts.json invalid"})

    random.shuffle(accounts)
    accounts = accounts[:limit]

    used_accounts.clear()

    success = 0
    failed = 0
    duplicate = 0

    logs = []

    THREADS = 60

    with ThreadPoolExecutor(max_workers=THREADS) as executor:

        futures = [
            executor.submit(process_account, acc, target)
            for acc in accounts
        ]

        for future in as_completed(futures):

            result = future.result()

            status = result["status"]

            if status == "success":
                success += 1
            elif status == "duplicate":
                duplicate += 1
            else:
                failed += 1

            logs.append(result)

    return jsonify({
        "success": success,
        "failed": failed,
        "duplicate": duplicate,
        "total": len(accounts),
        "logs": logs
    })

# ---------------- INFO API ----------------

@app.route("/api/info", methods=["POST"])
def info():

    uid = request.json.get("uid")

    token = get_token(INFO_UID, INFO_PASS)

    if not token:
        return jsonify({"status": "failed"})

    try:

        r = session.get(
            BASE_URL + "/get_player_info",
            params={
                "token": token,
                "player_id": uid
            },
            timeout=10
        )

        return jsonify(r.json())

    except:
        return jsonify({"status": "failed"})

# ---------------- START SERVER ----------------

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

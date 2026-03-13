from flask import Flask, request, jsonify, render_template
import requests, json, time, base64, os, random

app = Flask(__name__)

BASE_URL = "https://all-aapi-production.up.railway.app"
INFO_URL = "http://info-api-production-d71d.up.railway.app"
ACCOUNTS_FILE = "accounts.json"
TOKEN_FILE = "token.json"

session = requests.Session()

# ---------------- TOKEN UTILS ----------------

def load_tokens():
    if not os.path.exists(TOKEN_FILE):
        return {}
    try:
        return json.load(open(TOKEN_FILE))
    except:
        return {}

def save_tokens(data):
    json.dump(data, open(TOKEN_FILE, "w"), indent=2)

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

# ---------------- PAGES ----------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/spam")
def spam_page():
    return render_template("spam.html")

@app.route("/info")
def info_page():
    return render_template("info.html")

# ---------------- SPAM REQUEST API ----------------

@app.route("/api/spam_add", methods=["POST"])
def spam_add():
    data = request.json
    target = data["target"]
    limit = int(data["limit"])

    accounts = json.load(open(ACCOUNTS_FILE))
    random.shuffle(accounts)

    success = failed = duplicate = used = 0
    logs = []

    for acc in accounts:
        if used >= limit:
            break

        uid = acc["uid"]
        password = acc["password"]

        token = get_token(uid, password)
        if not token:
            failed += 1
            logs.append({"uid": uid, "status": "token_failed"})
            used += 1
            continue

        res = session.get(
            BASE_URL + "/add_friend",
            params={"token": token, "player_id": target},
            timeout=5
        ).json()

        status = res.get("status", "failed")
        if status == "success":
            success += 1
        elif status == "duplicate":
            duplicate += 1
        else:
            failed += 1

        logs.append({"uid": uid, "status": status})
        used += 1
        time.sleep(0.3)

    return jsonify({
        "success": success,
        "failed": failed,
        "duplicate": duplicate,
        "total": used,
        "logs": logs
    })

# ---------------- INFO API ----------------
@app.route("/api/info", methods=["POST"])
def info():
    uid = request.json.get("uid")
    if not uid:
        return jsonify({"status": "failed", "error": "UID missing"})

    try:
        # region fixed as IND
        r = session.get(f"http://info-api-production-d71d.up.railway.app/get", 
                        params={"uid": uid, "region": "IND"}, timeout=5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)})

# ---------------- START ----------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

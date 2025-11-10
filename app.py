from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime, timedelta
import io
import pandas as pd
import os
import json
import base64

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # change this to a secure random string

# ---------- Users (example) ----------
users = {
    "Avinash": "8105",
    "Abhishek": "7846",
    "Mantu": "1234"
}

# ---------- Google Sheets setup ----------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds_json_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
if creds_json_env:
    creds_info = json.loads(creds_json_env)
    CREDS = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
else:
    SA_FILE = "flasksheetapp-ba4cac5e3c9d.json"
    if not os.path.exists(SA_FILE):
        raise Exception("No service account credentials found. "
                        "Set GOOGLE_CREDENTIALS_JSON env or place JSON file locally.")
    CREDS = Credentials.from_service_account_file(SA_FILE, scopes=SCOPES)

client = gspread.authorize(CREDS)
SPREADSHEET_ID = "1cXrVgzv8f_xL8xrQaHX48SWaNiGcVqsZ1W4sBv3nK1g"
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# ---------------- Helper functions ----------------
def capitalize_first(text):
    return text.strip().capitalize() if text else ""


def calculate_effort_time(start_time, end_time):
    try:
        fmt = "%H:%M"
        s = datetime.strptime(start_time, fmt)
        e = datetime.strptime(end_time, fmt)
        delta = e - s
        if delta.total_seconds() < 0:
            delta += timedelta(days=1)
        total_minutes = int(delta.total_seconds() // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours:02d}:{minutes:02d}"
    except Exception:
        return "N/A"


def _parse_date_flexible(s):
    """Try to handle multiple date formats."""
    if not s:
        raise ValueError("Empty date")
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    if " " in s:
        return _parse_date_flexible(s.split(" ")[0])
    raise ValueError(f"Unknown date format: {s!r}")


def generate_request_id_for_sheet_position(n, row_date=None):
    """Generate SR\<Mon>\<NNN> for given index n (1-based)."""
    if row_date is None:
        row_date = datetime.now().date()
    month_abbr = row_date.strftime("%b")
    return f"SR\\{month_abbr}\\{n:03d}"

# ---------------- Login routes ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username in users and users[username] == password:
            session["username"] = username
            return redirect(url_for("home"))
        return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

# ---------------- Main routes ----------------
@app.route("/")
def home():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["username"])


@app.route("/submit", methods=["POST"])
def submit_form():
    if "username" not in session:
        return redirect(url_for("login"))

    # read inputs
    date_str = request.form.get("created_date", "")
    start_time_str = request.form.get("start_time", "")
    end_time_str = request.form.get("end_time", "")
    user_name = capitalize_first(request.form.get("user_name", ""))
    process = capitalize_first(request.form.get("process", ""))
    reported_by = capitalize_first(request.form.get("reported_by", ""))
    issue_category = capitalize_first(request.form.get("issue_category", ""))
    sub_category = capitalize_first(request.form.get("sub_category", ""))
    remarks = request.form.get("remarks", "").strip()

    # format date/time
    try:
        created_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        created_date = _parse_date_flexible(date_str).strftime("%d/%m/%Y")

    try:
        start_time = datetime.strptime(start_time_str, "%H:%M").strftime("%H:%M:%S")
    except Exception:
        start_time = start_time_str
    try:
        end_time = datetime.strptime(end_time_str, "%H:%M").strftime("%H:%M:%S")
    except Exception:
        end_time = end_time_str

    # auto fields
    sl_no = len(sheet.get_all_records()) + 1
    req_id = generate_request_id_for_sheet_position(sl_no)
    effort_time = calculate_effort_time(start_time_str, end_time_str)
    priority = "Medium"
    technician = session["username"]
    request_status = "CLOSED"

    new_row = [
        sl_no, req_id, created_date, start_time, end_time,
        user_name, process, reported_by, priority, technician,
        issue_category, sub_category, effort_time, request_status, remarks
    ]
    sheet.append_row(new_row)
    return redirect(url_for("home"))

# ---------------- View & Filter ----------------
@app.route("/view")
def view_data():
    if "username" not in session:
        return redirect(url_for("login"))

    records = sheet.get_all_values()
    if len(records) > 1:
        headers = records[0]
        data = records[1:]
        tech_col = None
        for i, h in enumerate(headers):
            if h.strip().lower() == "technician name":
                tech_col = i
                break
        if tech_col is not None:
            data = [row for row in data if len(row) > tech_col and row[tech_col] == session["username"]]
    else:
        headers, data = [], []

    return render_template("view.html", headers=headers, data=data, user=session["username"])


@app.route("/filter", methods=["POST"])
def filter_data():
    if "username" not in session:
        return redirect(url_for("login"))

    start_date = request.form.get("start_date", "").strip()
    end_date = request.form.get("end_date", "").strip()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception:
        start_dt = _parse_date_flexible(start_date)
        end_dt = _parse_date_flexible(end_date)

    records = sheet.get_all_values()
    headers = records[0] if records else []
    data = records[1:] if len(records) > 1 else []

    date_col, tech_col = None, None
    for i, h in enumerate(headers):
        if h.strip().lower() == "created date":
            date_col = i
        if h.strip().lower() == "technician name":
            tech_col = i

    filtered = []
    for row in data:
        try:
            if date_col is None or tech_col is None:
                continue
            if len(row) <= max(date_col, tech_col):
                continue
            if row[tech_col] != session["username"]:
                continue
            row_date = _parse_date_flexible(row[date_col])
            if start_dt <= row_date <= end_dt:
                filtered.append(row)
        except Exception:
            continue

    return render_template("view.html", headers=headers, data=filtered,
                           start=start_date, end=end_date, user=session["username"])

# ---------------- Excel Download ----------------
@app.route("/download", methods=["POST"])
def download_excel():
    if "username" not in session:
        return redirect(url_for("login"))

    start_date = request.form.get("start_date", "").strip()
    end_date = request.form.get("end_date", "").strip()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception:
        start_dt = _parse_date_flexible(start_date)
        end_dt = _parse_date_flexible(end_date)

    records = sheet.get_all_values()
    if not records:
        return "No data in sheet", 400
    headers, data_rows = records[0], records[1:]

    date_col, tech_col = None, None
    for i, h in enumerate(headers):
        if h.strip().lower() == "created date":
            date_col = i
        if h.strip().lower() == "technician name":
            tech_col = i

    filtered = []
    for row in data_rows:
        if len(row) <= max(date_col, tech_col):
            continue
        if row[tech_col] != session["username"]:
            continue
        try:
            row_date = _parse_date_flexible(row[date_col])
            if start_dt <= row_date <= end_dt:
                filtered.append((row, row_date))
        except Exception:
            continue

    if not filtered:
        df_empty = pd.DataFrame(columns=headers)
        output = io.BytesIO()
        df_empty.to_excel(output, index=False, sheet_name="Filtered Data")
        output.seek(0)
        return send_file(output, as_attachment=True,
                         download_name=f"{session['username']}_data_{start_date}_to_{end_date}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    rows_only = [r for r, _ in filtered]
    df = pd.DataFrame(rows_only, columns=headers)
    for col in ["Sl No", "Request/Complaint ID"]:
        if col in df.columns:
            df.drop(columns=[col], inplace=True)

    df.insert(0, "Sl No", range(1, len(df) + 1))
    request_ids = [generate_request_id_for_sheet_position(i, row_date=d)
                   for i, (_, d) in enumerate(filtered, start=1)]
    df.insert(1, "Request/Complaint ID", request_ids)

    remaining = [h for h in headers if h not in ("Sl No", "Request/Complaint ID")]
    df = df[["Sl No", "Request/Complaint ID"] + [c for c in remaining if c in df.columns]]

    output = io.BytesIO()
    df.to_excel(output, index=False, sheet_name="Filtered Data")
    output.seek(0)
    filename = f"{session['username']}_data_{start_date}_to_{end_date}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------- User Settings / Profile ----------------
SETTINGS_DIR = "user_data"
UPLOAD_DIR = "static/uploads"
os.makedirs(SETTINGS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route('/save_settings', methods=['POST'])
def save_settings():
    if "username" not in session:
        return "Unauthorized", 403
    username = session["username"]
    data = request.json
    user_settings_path = os.path.join(SETTINGS_DIR, f"{username}.json")
    with open(user_settings_path, 'w') as f:
        json.dump(data, f)
    return {"status": "ok"}


@app.route('/get_settings')
def get_settings():
    if "username" not in session:
        return "Unauthorized", 403
    username = session["username"]
    user_settings_path = os.path.join(SETTINGS_DIR, f"{username}.json")
    if os.path.exists(user_settings_path):
        with open(user_settings_path) as f:
            return json.load(f)
    else:
        return {"profilePic": "static/default_profile.png",
                "backgroundImg": "static/default_bg.jpg",
                "theme": "default"}


@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect(url_for("login"))
    username = session["username"]
    user_settings_path = os.path.join(SETTINGS_DIR, f"{username}.json")
    if os.path.exists(user_settings_path):
        with open(user_settings_path) as f:
            user_settings = json.load(f)
    else:
        user_settings = {}
    return render_template("profile.html", user=username, settings=user_settings)


if __name__ == "__main__":
    app.run(debug=True)

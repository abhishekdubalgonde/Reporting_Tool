from flask import Flask, render_template, request, redirect, url_for
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import io
import pandas as pd
from flask import send_file

app = Flask(__name__)

# Google Sheets API setup
import os, json
from dotenv import load_dotenv
load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Load credentials securely from environment variable
creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if creds_json:
    info = json.loads(creds_json)
    CREDS = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(CREDS)
else:
    raise Exception("Missing Google credentials in environment variable.")

client = gspread.authorize(CREDS)

# Replace with your Google Sheet ID (from the URL)
SPREADSHEET_ID = "1cXrVgzv8f_xL8xrQaHX48SWaNiGcVqsZ1W4sBv3nK1g"
sheet = client.open_by_key(SPREADSHEET_ID).sheet1


def generate_request_id():
    """Generate auto-incremented request ID like REQ-0001"""
    all_records = sheet.get_all_records()
    req_number = len(all_records) + 1
    month_abbr = datetime.now().strftime("%b")  # e.g., 'Oct'
    return f"SR\\{month_abbr}\\{req_number:03d}"


def calculate_effort_time(start_time, end_time):
    """Calculate difference between start and end times"""
    try:
        fmt = "%H:%M"
        start_dt = datetime.strptime(start_time, fmt)
        end_dt = datetime.strptime(end_time, fmt)
        delta = end_dt - start_dt

        total_minutes = int(delta.total_seconds() // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60

        return f"{hours:02d}:{minutes:02d}"  # e.g., 0:32
    except Exception:
        return "N/A"

def capitalize_first(text):
    """Capitalize only the first letter of a text input"""
    return text.strip().capitalize() if text else ""

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/submit", methods=["POST"])
def submit_form():
    # Read form data
    date_str = request.form["created_date"]
    start_time_str = request.form["start_time"]
    end_time_str = request.form["end_time"]
    user_name = capitalize_first(request.form["user_name"])
    process = capitalize_first(request.form["process"])
    reported_by = capitalize_first(request.form["reported_by"])
    issue_category = capitalize_first(request.form["issue_category"])
    sub_category = capitalize_first(request.form["sub_category"])
    remarks = capitalize_first(request.form["remarks"])

    # ✅ Convert to formatted date/time
    created_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    start_time = datetime.strptime(start_time_str, "%H:%M").strftime("%H:%M:%S")
    end_time = datetime.strptime(end_time_str, "%H:%M").strftime("%H:%M:%S")

    # Auto fields
    sl_no = len(sheet.get_all_records()) + 1
    req_id = generate_request_id()
    effort_time = calculate_effort_time(start_time_str, end_time_str)
    priority = "Medium"
    technician = "Abhishek"
    request_status = "CLOSED"

    # Add to Google Sheet
    new_row = [
        sl_no, req_id, created_date, start_time, end_time, user_name, process,
        reported_by, priority, technician, issue_category, sub_category,
        effort_time, request_status, remarks
    ]
    sheet.append_row(new_row)
    return redirect(url_for("home"))

@app.route("/view")
def view_data():
    # Fetch all data from sheet (including header row)
    records = sheet.get_all_values()

    if len(records) > 1:
        headers = records[0]
        data = records[1:]
    else:
        headers = []
        data = []

    return render_template("view.html", headers=headers, data=data)
@app.route("/filter", methods=["POST"])
def filter_data():
    start_date = request.form["start_date"]
    end_date = request.form["end_date"]

    # Convert to datetime objects for filtering
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    records = sheet.get_all_values()
    headers = records[0]
    data = records[1:]

    # Index of "Created Date" column
    date_col = headers.index("Created Date")

    filtered = []
    for row in data:
        try:
            row_date = datetime.strptime(row[date_col], "%d/%m/%Y")
            if start_dt <= row_date <= end_dt:
                filtered.append(row)
        except Exception:
            continue

    return render_template("view.html", headers=headers, data=filtered, start=start_date, end=end_date)
@app.route("/download", methods=["POST"])
def download_excel():
    start_date = request.form["start_date"]
    end_date = request.form["end_date"]

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    records = sheet.get_all_values()
    headers = records[0]
    data = records[1:]

    date_col = headers.index("Created Date")

    filtered = []
    for row in data:
        try:
            row_date = datetime.strptime(row[date_col], "%d/%m/%Y")
            if start_dt <= row_date <= end_dt:
                filtered.append(row)
        except Exception:
            continue

    # Convert to DataFrame
    df = pd.DataFrame(filtered, columns=headers)

    # Save to an in-memory Excel file
    output = io.BytesIO()
    df.to_excel(output, index=False, sheet_name="Filtered Data")
    output.seek(0)

    filename = f"SheetData_{start_date}_to_{end_date}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    app.run(debug=True)

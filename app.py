import os
import json
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static")
CORS(app)

DEMO_MODE = os.getenv("DEMO_MODE", "True").lower() == "true"
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")

# ---------------------------------------------------------------------------
# Google Sheets column layout
# ---------------------------------------------------------------------------
DEALS_HEADERS = [
    "ID", "Менеджер", "Клиент", "Статус", "Название сделки",
    "Описание", "Сумма начислено", "Сумма оплачено",
    "Дата акта", "Дата создания", "Месяц",
]
JOURNAL_HEADERS = ["Дата/Время", "Пользователь", "Действие", "Детали"]
USERS_HEADERS = ["Telegram ID", "Имя", "Роль"]

# ---------------------------------------------------------------------------
# Demo data (used when DEMO_MODE=True or Google Sheets is unavailable)
# ---------------------------------------------------------------------------
_demo_deals = [
    {
        "id": "DEAL001", "manager": "Иванов Иван", "client": "ООО Рога и Копыта",
        "status": "Активная", "deal_name": "Поставка оборудования",
        "description": "Поставка производственного оборудования",
        "amount_charged": "500000", "amount_paid": "250000",
        "act_date": "2026-03-15", "created_at": "2026-03-01", "month": "2026-03", "row": 2,
    },
    {
        "id": "DEAL002", "manager": "Петрова Анна", "client": "АО Альфа",
        "status": "Завершённая", "deal_name": "Монтаж системы",
        "description": "Монтаж и настройка системы видеонаблюдения",
        "amount_charged": "320000", "amount_paid": "320000",
        "act_date": "2026-02-28", "created_at": "2026-02-10", "month": "2026-02", "row": 3,
    },
    {
        "id": "DEAL003", "manager": "Иванов Иван", "client": "ЗАО Бета",
        "status": "Активная", "deal_name": "Техническое обслуживание",
        "description": "Ежеквартальное ТО оборудования",
        "amount_charged": "180000", "amount_paid": "0",
        "act_date": "", "created_at": "2026-03-05", "month": "2026-03", "row": 4,
    },
    {
        "id": "DEAL004", "manager": "Сидоров Пётр", "client": "ИП Гамма",
        "status": "Завершённая", "deal_name": "Разработка ПО",
        "description": "Разработка корпоративного портала",
        "amount_charged": "750000", "amount_paid": "750000",
        "act_date": "2026-01-31", "created_at": "2026-01-15", "month": "2026-01", "row": 5,
    },
    {
        "id": "DEAL005", "manager": "Петрова Анна", "client": "ООО Дельта",
        "status": "Активная", "deal_name": "Консалтинг",
        "description": "Управленческий консалтинг Q1",
        "amount_charged": "200000", "amount_paid": "100000",
        "act_date": "", "created_at": "2026-03-10", "month": "2026-03", "row": 6,
    },
]

_demo_journal = [
    {
        "timestamp": "2026-03-10 14:32:00", "user": "Иванов Иван",
        "action": "Создание сделки", "details": "Сделка DEAL005: Консалтинг",
    },
    {
        "timestamp": "2026-03-05 09:15:00", "user": "Иванов Иван",
        "action": "Создание сделки", "details": "Сделка DEAL003: Техническое обслуживание",
    },
    {
        "timestamp": "2026-02-28 17:00:00", "user": "Петрова Анна",
        "action": "Редактирование сделки", "details": "Сделка DEAL002: изменены поля",
    },
    {
        "timestamp": "2026-02-10 11:00:00", "user": "Петрова Анна",
        "action": "Создание сделки", "details": "Сделка DEAL002: Монтаж системы",
    },
]

_demo_users = [
    {"telegram_id": "111111111", "name": "Иванов Иван", "role": "manager"},
    {"telegram_id": "222222222", "name": "Петрова Анна", "role": "manager"},
    {"telegram_id": "333333333", "name": "Бухгалтер Главный", "role": "accountant"},
]

# ---------------------------------------------------------------------------
# Google Sheets helpers
# ---------------------------------------------------------------------------

def _get_sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    return gspread.authorize(creds)


def _get_spreadsheet():
    client = _get_sheets_client()
    return client.open_by_key(SPREADSHEET_ID)


def _ensure_sheets(spreadsheet):
    """Create required worksheets with headers if they don't exist."""
    names = {ws.title for ws in spreadsheet.worksheets()}
    if "Сделки" not in names:
        ws = spreadsheet.add_worksheet(title="Сделки", rows=1000, cols=len(DEALS_HEADERS))
        ws.append_row(DEALS_HEADERS)
    if "Журнал действий" not in names:
        ws = spreadsheet.add_worksheet(title="Журнал действий", rows=1000, cols=len(JOURNAL_HEADERS))
        ws.append_row(JOURNAL_HEADERS)
    if "Пользователи" not in names:
        ws = spreadsheet.add_worksheet(title="Пользователи", rows=200, cols=len(USERS_HEADERS))
        ws.append_row(USERS_HEADERS)


def _log_action(spreadsheet, user, action, details=""):
    try:
        ws = spreadsheet.worksheet("Журнал действий")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([now, user, action, details])
    except Exception as exc:
        app.logger.warning("Could not log action: %s", exc)


def _row_to_deal(row, idx):
    while len(row) < len(DEALS_HEADERS):
        row.append("")
    return {
        "row": idx,
        "id": row[0],
        "manager": row[1],
        "client": row[2],
        "status": row[3],
        "deal_name": row[4],
        "description": row[5],
        "amount_charged": row[6],
        "amount_paid": row[7],
        "act_date": row[8],
        "created_at": row[9],
        "month": row[10],
    }


def _apply_filters(deals):
    manager_f = request.args.get("manager", "").strip().lower()
    client_f = request.args.get("client", "").strip().lower()
    status_f = request.args.get("status", "").strip()
    month_f = request.args.get("month", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    if manager_f:
        deals = [d for d in deals if manager_f in d["manager"].lower()]
    if client_f:
        deals = [d for d in deals if client_f in d["client"].lower()]
    if status_f:
        deals = [d for d in deals if d["status"] == status_f]
    if month_f:
        deals = [d for d in deals if d["month"] == month_f]
    if date_from:
        deals = [d for d in deals if d["created_at"] >= date_from]
    if date_to:
        deals = [d for d in deals if d["created_at"] <= date_to]
    return deals


# ---------------------------------------------------------------------------
# Routes — static
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ---------------------------------------------------------------------------
# Routes — user role
# ---------------------------------------------------------------------------

@app.route("/api/user-role")
def get_user_role():
    user_id = request.args.get("user_id", "").strip()
    user_name = request.args.get("user_name", "").strip()

    if DEMO_MODE or not SPREADSHEET_ID:
        for u in _demo_users:
            if u["telegram_id"] == user_id:
                return jsonify({"role": u["role"], "name": u["name"]})
        return jsonify({"role": "manager", "name": user_name or "Пользователь"})

    try:
        spreadsheet = _get_spreadsheet()
        _ensure_sheets(spreadsheet)
        ws = spreadsheet.worksheet("Пользователи")
        rows = ws.get_all_values()
        for row in rows[1:]:
            if row and row[0] == user_id:
                return jsonify({"role": row[2] if len(row) > 2 else "manager",
                                "name": row[1] if len(row) > 1 else user_name})
        return jsonify({"role": "manager", "name": user_name or "Пользователь"})
    except Exception as exc:
        app.logger.error("user-role error: %s", exc)
        return jsonify({"role": "manager", "name": user_name or "Пользователь"})


# ---------------------------------------------------------------------------
# Routes — deals
# ---------------------------------------------------------------------------

@app.route("/api/deals", methods=["GET"])
def get_deals():
    if DEMO_MODE or not SPREADSHEET_ID:
        deals = [dict(d) for d in _demo_deals]
        return jsonify(_apply_filters(deals))

    try:
        spreadsheet = _get_spreadsheet()
        _ensure_sheets(spreadsheet)
        ws = spreadsheet.worksheet("Сделки")
        all_rows = ws.get_all_values()
        deals = [_row_to_deal(list(r), i + 2)
                 for i, r in enumerate(all_rows[1:]) if r and r[0]]
        return jsonify(_apply_filters(deals))
    except Exception as exc:
        app.logger.error("get_deals error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/deals", methods=["POST"])
def create_deal():
    data = request.get_json() or {}
    now = datetime.now()
    deal_id = str(uuid.uuid4())[:8].upper()
    month = now.strftime("%Y-%m")
    created_at = now.strftime("%Y-%m-%d")

    new_deal = {
        "id": deal_id,
        "manager": data.get("manager", ""),
        "client": data.get("client", ""),
        "status": data.get("status", "Активная"),
        "deal_name": data.get("deal_name", ""),
        "description": data.get("description", ""),
        "amount_charged": data.get("amount_charged", ""),
        "amount_paid": data.get("amount_paid", ""),
        "act_date": data.get("act_date", ""),
        "created_at": created_at,
        "month": month,
        "row": len(_demo_deals) + 2,
    }

    if DEMO_MODE or not SPREADSHEET_ID:
        _demo_deals.append(new_deal)
        _demo_journal.insert(0, {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "user": data.get("user", "Неизвестно"),
            "action": "Создание сделки",
            "details": f"Сделка {deal_id}: {data.get('deal_name', '')}",
        })
        return jsonify({"success": True, "id": deal_id})

    try:
        spreadsheet = _get_spreadsheet()
        _ensure_sheets(spreadsheet)
        ws = spreadsheet.worksheet("Сделки")
        row = [
            deal_id, new_deal["manager"], new_deal["client"], new_deal["status"],
            new_deal["deal_name"], new_deal["description"],
            new_deal["amount_charged"], new_deal["amount_paid"],
            new_deal["act_date"], created_at, month,
        ]
        ws.append_row(row)
        _log_action(spreadsheet, data.get("user", "Неизвестно"),
                    "Создание сделки", f"Сделка {deal_id}: {data.get('deal_name', '')}")
        return jsonify({"success": True, "id": deal_id})
    except Exception as exc:
        app.logger.error("create_deal error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/deals/<deal_id>", methods=["PUT"])
def update_deal(deal_id):
    data = request.get_json() or {}
    role = data.get("role", "manager")
    user = data.get("user", "Неизвестно")

    # Fields any role can update
    common_fields = ["client", "status", "deal_name", "description"]
    # Extra fields only accountant can update
    accountant_fields = ["manager", "amount_charged", "amount_paid", "act_date"]

    if DEMO_MODE or not SPREADSHEET_ID:
        for deal in _demo_deals:
            if deal["id"] == deal_id:
                for field in common_fields:
                    if field in data:
                        deal[field] = data[field]
                if role == "accountant":
                    for field in accountant_fields:
                        if field in data:
                            deal[field] = data[field]
                _demo_journal.insert(0, {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user": user,
                    "action": "Редактирование сделки",
                    "details": f"Сделка {deal_id}: изменены поля",
                })
                return jsonify({"success": True})
        return jsonify({"error": "Deal not found"}), 404

    try:
        spreadsheet = _get_spreadsheet()
        ws = spreadsheet.worksheet("Сделки")
        all_rows = ws.get_all_values()

        target_row = None
        for i, row in enumerate(all_rows):
            if row and row[0] == deal_id:
                target_row = i + 1
                break
        if target_row is None:
            return jsonify({"error": "Deal not found"}), 404

        # Column letter map (1-indexed -> A=1)
        col_map = {
            "manager": "B", "client": "C", "status": "D",
            "deal_name": "E", "description": "F",
            "amount_charged": "G", "amount_paid": "H", "act_date": "I",
        }

        fields_to_update = list(common_fields)
        if role == "accountant":
            fields_to_update += accountant_fields

        for field in fields_to_update:
            if field in data and field in col_map:
                ws.update(f"{col_map[field]}{target_row}", [[data[field]]])

        _log_action(spreadsheet, user, "Редактирование сделки",
                    f"Сделка {deal_id}: изменены поля")
        return jsonify({"success": True})
    except Exception as exc:
        app.logger.error("update_deal error: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Routes — dashboard
# ---------------------------------------------------------------------------

@app.route("/api/dashboard")
def get_dashboard():
    def _stats(deals):
        total = len(deals)
        active = sum(1 for d in deals if d.get("status") == "Активная")
        completed = sum(1 for d in deals if d.get("status") == "Завершённая")
        charged = paid = 0.0
        for d in deals:
            try:
                charged += float(str(d.get("amount_charged", "") or "0").replace(",", "."))
            except ValueError:
                pass
            try:
                paid += float(str(d.get("amount_paid", "") or "0").replace(",", "."))
            except ValueError:
                pass
        return {"total": total, "active": active, "completed": completed,
                "total_charged": charged, "total_paid": paid}

    if DEMO_MODE or not SPREADSHEET_ID:
        return jsonify(_stats(_demo_deals))

    try:
        spreadsheet = _get_spreadsheet()
        _ensure_sheets(spreadsheet)
        ws = spreadsheet.worksheet("Сделки")
        all_rows = ws.get_all_values()
        deals = [_row_to_deal(list(r), i + 2)
                 for i, r in enumerate(all_rows[1:]) if r and r[0]]
        return jsonify(_stats(deals))
    except Exception as exc:
        app.logger.error("dashboard error: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Routes — journal
# ---------------------------------------------------------------------------

@app.route("/api/journal")
def get_journal():
    if DEMO_MODE or not SPREADSHEET_ID:
        return jsonify(_demo_journal[:50])

    try:
        spreadsheet = _get_spreadsheet()
        _ensure_sheets(spreadsheet)
        ws = spreadsheet.worksheet("Журнал действий")
        all_rows = ws.get_all_values()
        entries = []
        for row in reversed(all_rows[1:]):
            if row and row[0]:
                entries.append({
                    "timestamp": row[0],
                    "user": row[1] if len(row) > 1 else "",
                    "action": row[2] if len(row) > 2 else "",
                    "details": row[3] if len(row) > 3 else "",
                })
        return jsonify(entries[:50])
    except Exception as exc:
        app.logger.error("journal error: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Routes — filter helpers
# ---------------------------------------------------------------------------

@app.route("/api/managers")
def get_managers():
    if DEMO_MODE or not SPREADSHEET_ID:
        return jsonify(sorted({d["manager"] for d in _demo_deals if d["manager"]}))

    try:
        spreadsheet = _get_spreadsheet()
        _ensure_sheets(spreadsheet)
        ws = spreadsheet.worksheet("Сделки")
        all_rows = ws.get_all_values()
        managers = sorted({r[1] for r in all_rows[1:] if r and r[0] and len(r) > 1 and r[1]})
        return jsonify(managers)
    except Exception as exc:
        app.logger.error("managers error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/clients")
def get_clients():
    if DEMO_MODE or not SPREADSHEET_ID:
        return jsonify(sorted({d["client"] for d in _demo_deals if d["client"]}))

    try:
        spreadsheet = _get_spreadsheet()
        _ensure_sheets(spreadsheet)
        ws = spreadsheet.worksheet("Сделки")
        all_rows = ws.get_all_values()
        clients = sorted({r[2] for r in all_rows[1:] if r and r[0] and len(r) > 2 and r[2]})
        return jsonify(clients)
    except Exception as exc:
        app.logger.error("clients error: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)

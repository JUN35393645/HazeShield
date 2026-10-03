from __future__ import annotations

import os
import random
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Generator

import requests

CONFIG = {
    "trigger_threshold": 150,
    "consecutive_days": 2,
    "payout_per_day": 30.0,
    "max_payout_days_per_season": 5,
    "referral_reward": 5.0,
    "group_price_per_worker": 12.5,
}
ZONES = [
    ("Klang Valley", "Selangor"),
    ("Kuching", "Sarawak"),
    ("Sri Aman", "Sarawak"),
    ("Johor Bahru", "Johor"),
    ("Penang", "Penang"),
    ("Ipoh", "Perak"),
    ("Kota Kinabalu", "Sabah"),
]
DATABASE_PATH = Path(os.environ.get("HAZESHIELD_DATABASE_PATH", Path(__file__).with_name("hazeshield.db")))


def normalize_api_base_url(value: str) -> str:
    base_url = value.rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        scheme = "http" if ":" in base_url else "https"
        base_url = f"{scheme}://{base_url}"
    return base_url


API_BASE_URL = normalize_api_base_url(
    os.environ.get("HAZESHIELD_API_URL", "http://127.0.0.1:8000/api/v1")
)


def request_api(
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str | None = None,
) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    try:
        response = requests.request(
            method, f"{API_BASE_URL}{path}", json=payload, headers=headers, timeout=10
        )
        response.raise_for_status()
    except requests.HTTPError as error:
        try:
            detail = error.response.json().get("detail")
        except (AttributeError, ValueError):
            detail = None
        raise RuntimeError(str(detail or error)) from error
    except requests.RequestException as error:
        raise RuntimeError(f"Backend API request failed: {error}") from error
    return response.json()


@contextmanager
def connect() -> Generator[sqlite3.Connection, None, None]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ensure_demo_customer(db: sqlite3.Connection) -> None:
    zone_id = db.execute("SELECT id FROM zones WHERE name='Kota Kinabalu'").fetchone()[0]
    customer = db.execute("SELECT id FROM users WHERE referral_code='HAZE-CUSTOMER'").fetchone()
    if customer is None:
        db.execute(
            "INSERT INTO users(name, role, zone_id, referral_code, occupation, occupation_other) "
            "VALUES (?, 'customer', ?, ?, 'Other', 'Outdoor worker')",
            ("Demo Customer", zone_id, "HAZE-CUSTOMER"),
        )
    starter = db.execute("SELECT id FROM users WHERE referral_code='HAZE-STARTER'").fetchone()
    if starter is None:
        starter_zone_id = db.execute("SELECT id FROM zones WHERE name='Ipoh'").fetchone()[0]
        db.execute(
            "INSERT INTO users(name, role, zone_id, referral_code, occupation, occupation_other) "
            "VALUES (?, 'customer', ?, ?, 'Other', 'Street market seller')",
            ("Demo New Customer", starter_zone_id, "HAZE-STARTER"),
        )


def init_database() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS zones (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                zone_id INTEGER REFERENCES zones(id), wallet TEXT DEFAULT 'Touch n Go',
                referral_code TEXT NOT NULL UNIQUE, email TEXT, password_hash TEXT,
                occupation TEXT, occupation_other TEXT, company_name TEXT
            );
            CREATE TABLE IF NOT EXISTS employer_memberships (
                id INTEGER PRIMARY KEY, employer_id INTEGER NOT NULL REFERENCES users(id),
                customer_id INTEGER NOT NULL REFERENCES users(id), status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL, UNIQUE(employer_id, customer_id)
            );
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, plan_type TEXT NOT NULL,
                price REAL NOT NULL, description TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                plan_id INTEGER NOT NULL REFERENCES plans(id), zone_id INTEGER NOT NULL REFERENCES zones(id),
                status TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
                sponsor_user_id INTEGER REFERENCES users(id),
                sponsor_policy_id INTEGER REFERENCES policies(id),
                auto_renew INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY, zone_id INTEGER NOT NULL REFERENCES zones(id),
                reading_date TEXT NOT NULL, api_value INTEGER NOT NULL, source TEXT NOT NULL,
                UNIQUE(zone_id, reading_date)
            );
            CREATE TABLE IF NOT EXISTS trigger_events (
                id INTEGER PRIMARY KEY, zone_id INTEGER NOT NULL REFERENCES zones(id),
                start_date TEXT NOT NULL, end_date TEXT NOT NULL, days_above_threshold INTEGER NOT NULL,
                UNIQUE(zone_id, start_date)
            );
            CREATE TABLE IF NOT EXISTS payouts (
                id INTEGER PRIMARY KEY, policy_id INTEGER NOT NULL REFERENCES policies(id),
                trigger_event_id INTEGER NOT NULL REFERENCES trigger_events(id),
                payout_date TEXT NOT NULL, amount REAL NOT NULL, wallet TEXT NOT NULL,
                status TEXT NOT NULL, paid_at TEXT NOT NULL,
                UNIQUE(policy_id, payout_date)
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                message TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                policy_id INTEGER NOT NULL REFERENCES policies(id), amount REAL NOT NULL,
                method TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY, actor_id INTEGER REFERENCES users(id), action TEXT NOT NULL,
                details TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_readings_zone_date ON readings(zone_id, reading_date);
            CREATE INDEX IF NOT EXISTS idx_policies_zone_status ON policies(zone_id, status);
            """
        )
        user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
        for column, definition in (
            ("email", "TEXT"),
            ("password_hash", "TEXT"),
            ("occupation", "TEXT"),
            ("occupation_other", "TEXT"),
            ("company_name", "TEXT"),
        ):
            if column not in user_columns:
                db.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
        policy_columns = {row["name"] for row in db.execute("PRAGMA table_info(policies)")}
        for column, definition in (
            ("sponsor_user_id", "INTEGER REFERENCES users(id)"),
            ("sponsor_policy_id", "INTEGER REFERENCES policies(id)"),
        ):
            if column not in policy_columns:
                db.execute(f"ALTER TABLE policies ADD COLUMN {column} {definition}")
        db.execute(
            "UPDATE users SET role='customer', occupation=CASE referral_code "
            "WHEN 'HAZE-AMINA' THEN 'Delivery rider' "
            "WHEN 'HAZE-JUNWEI' THEN 'E-hailing driver' "
            "WHEN 'HAZE-KAVITHA' THEN 'Food vendor' ELSE COALESCE(occupation, 'Other') END "
            "WHERE role='worker'"
        )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique "
            "ON users(email COLLATE NOCASE) WHERE email IS NOT NULL"
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_memberships_customer ON employer_memberships(customer_id, status)")
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            ensure_demo_customer(db)
            return
        for name, state in ZONES:
            db.execute("INSERT INTO zones(name, state) VALUES (?, ?)", (name, state))
        db.executemany(
            "INSERT INTO plans(name, plan_type, price, description) VALUES (?, ?, ?, ?)",
            [
                ("Monthly", "monthly", 15.0, "Flexible cover, billed monthly"),
                ("Haze season", "seasonal", 60.0, "July to September coverage"),
                ("Worker group", "group", 250.0, "20 workers, RM12.50 per worker"),
            ],
        )
        zone_ids = {row["name"]: row["id"] for row in db.execute("SELECT id, name FROM zones")}
        demo_users = [
            ("Amina Rahman", "customer", "Klang Valley", "HAZE-AMINA"),
            ("Jun Wei", "customer", "Kuching", "HAZE-JUNWEI"),
            ("Kavitha Devi", "customer", "Penang", "HAZE-KAVITHA"),
            ("Demo Employer", "employer", "Klang Valley", "HAZE-EMPLOYER"),
            ("Demo Admin", "admin", "Klang Valley", "HAZE-ADMIN"),
        ]
        for name, role, zone_name, code in demo_users:
            db.execute(
                "INSERT INTO users(name, role, zone_id, referral_code) VALUES (?, ?, ?, ?)",
                (name, role, zone_ids[zone_name], code),
            )
        monthly_id = db.execute("SELECT id FROM plans WHERE plan_type='monthly'").fetchone()[0]
        today = date.today()
        end_date = today + timedelta(days=30)
        for user_id in (1, 2, 3):
            user_zone = db.execute("SELECT zone_id FROM users WHERE id=?", (user_id,)).fetchone()[0]
            policy_cursor = db.execute(
                "INSERT INTO policies(user_id, plan_id, zone_id, status, start_date, end_date) VALUES (?, ?, ?, 'active', ?, ?)",
                (user_id, monthly_id, user_zone, today.isoformat(), end_date.isoformat()),
            )
            db.execute(
                "INSERT INTO payments(user_id, policy_id, amount, method, status, created_at) VALUES (?, ?, 15, 'Touch n Go', 'paid', ?)",
                (user_id, policy_cursor.lastrowid, today.isoformat()),
            )
        rng = random.Random(3130)
        for zone_name, zone_id in zone_ids.items():
            for offset in range(59, -1, -1):
                reading_date = today - timedelta(days=offset)
                value = rng.randint(25, 115)
                if zone_name == "Klang Valley" and reading_date in (
                    today - timedelta(days=10), today - timedelta(days=9), today - timedelta(days=8)
                ):
                    value = 158 + offset % 17
                db.execute(
                    "INSERT INTO readings(zone_id, reading_date, api_value, source) VALUES (?, ?, ?, 'SIMULATED')",
                    (zone_id, reading_date.isoformat(), value),
                )
        ensure_demo_customer(db)


def get_zones() -> list[sqlite3.Row]:
    with connect() as db:
        return db.execute("SELECT * FROM zones ORDER BY name").fetchall()


def get_users(role: str | None = None) -> list[sqlite3.Row]:
    with connect() as db:
        if role:
            return db.execute("SELECT * FROM users WHERE role=? ORDER BY id", (role,)).fetchall()
        return db.execute("SELECT * FROM users ORDER BY id").fetchall()


def get_reading(zone_id: int, on_date: date | None = None) -> int | None:
    with connect() as db:
        if on_date:
            row = db.execute(
                "SELECT api_value FROM readings WHERE zone_id=? AND reading_date=?",
                (zone_id, on_date.isoformat()),
            ).fetchone()
        else:
            row = db.execute(
                "SELECT api_value FROM readings WHERE zone_id=? ORDER BY reading_date DESC LIMIT 1",
                (zone_id,),
            ).fetchone()
    return row[0] if row else None


def band_for(api_value: int | None) -> tuple[str, str, str]:
    if api_value is None:
        return "No reading", "#68736e", "#eef0ed"
    if api_value <= 100:
        return "Good / moderate", "#176b52", "#e5f3ed"
    if api_value <= 150:
        return "Sensitive groups", "#9a6500", "#fff2d2"
    if api_value <= 200:
        return "Unhealthy", "#b64d24", "#ffebe2"
    return "Very unhealthy", "#a52d43", "#f9e6eb"


def trailing_streak(zone_id: int, end_date: date) -> int:
    streak = 0
    with connect() as db:
        for offset in range(15):
            check_date = end_date - timedelta(days=offset)
            row = db.execute(
                "SELECT api_value FROM readings WHERE zone_id=? AND reading_date=?",
                (zone_id, check_date.isoformat()),
            ).fetchone()
            if row is None or row[0] <= CONFIG["trigger_threshold"]:
                break
            streak += 1
    return streak


def evaluate_zone(zone_id: int, as_of: date) -> dict[str, Any]:
    first_day = as_of - timedelta(days=CONFIG["consecutive_days"] - 1)
    dates = [first_day + timedelta(days=offset) for offset in range(CONFIG["consecutive_days"])]
    with connect() as db:
        values: list[int] = []
        for check_date in dates:
            row = db.execute(
                "SELECT api_value FROM readings WHERE zone_id=? AND reading_date=?",
                (zone_id, check_date.isoformat()),
            ).fetchone()
            if row is None:
                return {"triggered": False, "missing": True, "payouts": 0, "event_id": None}
            values.append(row[0])
        if not all(value > CONFIG["trigger_threshold"] for value in values):
            return {"triggered": False, "missing": False, "payouts": 0, "event_id": None}

        event = db.execute(
            "SELECT * FROM trigger_events WHERE zone_id=? AND end_date=? ORDER BY id DESC LIMIT 1",
            (zone_id, as_of.isoformat()),
        ).fetchone()
        if event:
            event_id = event["id"]
            payout_dates = [as_of]
        else:
            previous = as_of - timedelta(days=1)
            event = db.execute(
                "SELECT * FROM trigger_events WHERE zone_id=? AND end_date=? ORDER BY id DESC LIMIT 1",
                (zone_id, previous.isoformat()),
            ).fetchone()
            if event:
                db.execute(
                    "UPDATE trigger_events SET end_date=?, days_above_threshold=days_above_threshold+1 WHERE id=?",
                    (as_of.isoformat(), event["id"]),
                )
                event_id = event["id"]
                payout_dates = [as_of]
            else:
                event = db.execute(
                    "SELECT * FROM trigger_events WHERE zone_id=? AND start_date=?",
                    (zone_id, first_day.isoformat()),
                ).fetchone()
                if event:
                    event_id = event["id"]
                    payout_dates = [as_of]
                else:
                    cursor = db.execute(
                        "INSERT INTO trigger_events(zone_id, start_date, end_date, days_above_threshold) VALUES (?, ?, ?, ?)",
                        (zone_id, first_day.isoformat(), as_of.isoformat(), CONFIG["consecutive_days"]),
                    )
                    event_id = cursor.lastrowid
                    payout_dates = dates

        policies = db.execute(
            "SELECT p.*, u.wallet FROM policies p JOIN users u ON u.id=p.user_id "
            "WHERE p.zone_id=? AND p.status='active' AND p.start_date<=? AND p.end_date>=? "
            "AND u.role='customer'",
            (zone_id, as_of.isoformat(), first_day.isoformat()),
        ).fetchall()
        payout_count = 0
        for policy in policies:
            for payout_date in payout_dates:
                if payout_date.isoformat() < policy["start_date"] or payout_date.isoformat() > policy["end_date"]:
                    continue
                season_start = date(payout_date.year, 7, 1).isoformat()
                season_end = date(payout_date.year, 9, 30).isoformat()
                paid_days = db.execute(
                    "SELECT COUNT(*) FROM payouts WHERE policy_id=? AND payout_date BETWEEN ? AND ?",
                    (policy["id"], season_start, season_end),
                ).fetchone()[0]
                if paid_days >= CONFIG["max_payout_days_per_season"]:
                    continue
                cursor = db.execute(
                    "INSERT OR IGNORE INTO payouts(policy_id, trigger_event_id, payout_date, amount, wallet, status, paid_at) "
                    "VALUES (?, ?, ?, ?, ?, 'paid', ?)",
                    (
                        policy["id"], event_id, payout_date.isoformat(), CONFIG["payout_per_day"],
                        policy["wallet"], datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                if cursor.rowcount:
                    payout_count += 1
                    db.execute(
                        "INSERT INTO notifications(user_id, message, created_at) VALUES (?, ?, ?)",
                        (policy["user_id"], "Haze trigger confirmed. Your RM30 payout is on its way.", datetime.now().isoformat(timespec="seconds")),
                    )
        return {"triggered": True, "missing": False, "payouts": payout_count, "event_id": event_id}


def inject_reading(zone_id: int, reading_date: date, api_value: int, actor_id: int) -> dict[str, Any]:
    with connect() as db:
        db.execute(
            "INSERT INTO readings(zone_id, reading_date, api_value, source) VALUES (?, ?, ?, 'SIMULATED') "
            "ON CONFLICT(zone_id, reading_date) DO UPDATE SET api_value=excluded.api_value, source='SIMULATED'",
            (zone_id, reading_date.isoformat(), api_value),
        )
        db.execute(
            "INSERT INTO audit_logs(actor_id, action, details, created_at) VALUES (?, 'inject_api', ?, ?)",
            (actor_id, f"zone={zone_id}; date={reading_date}; api={api_value}", datetime.now().isoformat(timespec="seconds")),
        )
    return evaluate_zone(zone_id, reading_date)


def buy_policy(user: sqlite3.Row, plan_id: int, zone_id: int) -> None:
    with connect() as db:
        plan = db.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
        start = date.today()
        if plan["plan_type"] == "seasonal":
            season_start = date(start.year, 7, 1)
            season_end = date(start.year, 9, 30)
            if start > season_end:
                season_start = date(start.year + 1, 7, 1)
                season_end = date(start.year + 1, 9, 30)
            start = max(start, season_start)
            end = season_end
        else:
            end = start + timedelta(days=30)
        cursor = db.execute(
            "INSERT INTO policies(user_id, plan_id, zone_id, status, start_date, end_date) VALUES (?, ?, ?, 'active', ?, ?)",
            (user["id"], plan_id, zone_id, start.isoformat(), end.isoformat()),
        )
        db.execute(
            "INSERT INTO payments(user_id, policy_id, amount, method, status, created_at) VALUES (?, ?, ?, ?, 'paid', ?)",
            (user["id"], cursor.lastrowid, plan["price"], user["wallet"], datetime.now().isoformat(timespec="seconds")),
        )


def reset_demo() -> None:
    DATABASE_PATH.unlink(missing_ok=True)
    init_database()


def money(amount: float) -> str:
    return f"RM{amount:,.2f}"


def render_styles(st_module: Any) -> None:
    st_module.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
        :root { --ink:#172d26; --muted:#66746d; --green:#176b52; --lime:#c7e76b; --coral:#ee7658; --paper:#f6f7f1; }
        html, body, [class*="css"] { font-family:'DM Sans',sans-serif; color:var(--ink); }
        .stApp { background: radial-gradient(ellipse at 92% 2%, #e2f0dc 0, transparent 35%), var(--paper); }
        h1,h2,h3 { font-family:'Manrope','DM Sans',sans-serif; letter-spacing:0 !important; color:var(--ink); }
        .block-container { max-width:1180px; padding-top:1.7rem; padding-bottom:3rem; }
        [data-testid="stSidebar"] { background:#173c31; }
        [data-testid="stSidebar"] * { color:#f2f7eb !important; }
        [data-testid="stSidebar"] [data-baseweb="select"] * { color:#172d26 !important; }
        div[data-testid="stMetric"] { background:#fff; border:1px solid #e7e9df; border-radius:8px; padding:16px 18px; }
        div[data-testid="stMetricLabel"] { color:#66746d; }
        div[data-testid="stMetricValue"] { color:#176b52; font-family:'Manrope',sans-serif; }
        .eyebrow { color:#176b52; font-size:.76rem; font-weight:700; text-transform:uppercase; letter-spacing:1px; }
        .hero { padding:24px 0 12px; }
        .hero h1 { font-size:2.45rem; line-height:1.08; margin:8px 0; }
        .hero p { max-width:650px; color:#66746d; font-size:1.05rem; }
        .public-hero { margin:18px 0 22px; padding:42px 44px; border-radius:12px; color:#fff; background:linear-gradient(112deg,#173c31 0%,#23664f 68%,#b85d43 100%); }
        .public-hero .eyebrow { color:#d5f08a; }
        .public-hero h1 { max-width:780px; margin:14px 0; color:#fff; font-size:3rem; line-height:1.06; }
        .public-hero p { max-width:680px; color:#e2eee5; font-size:1.08rem; }
        .air-panel { min-height:188px; padding:24px; border:1px solid #e7e9df; border-radius:10px; background:#fff; }
        .air-value { margin:14px 0 8px; font-family:'Manrope',sans-serif; font-size:4rem; line-height:1; font-weight:800; }
        .air-band { display:inline-block; padding:6px 10px; border-radius:6px; font-weight:700; }
        .plan-price { margin:10px 0; color:#176b52; font-family:'Manrope',sans-serif; font-size:2rem; font-weight:800; }
        .notice { border-left:4px solid #c7e76b; background:#fff; padding:14px 16px; border-radius:0 8px 8px 0; color:#354a40; }
        .api-number { font-family:'Manrope',sans-serif; font-size:3.4rem; line-height:1; font-weight:800; }
        .small-muted { color:#66746d; font-size:.9rem; }
        .stButton > button { border-radius:6px; min-height:42px; font-weight:700; }
        @media (max-width:650px) { .block-container { padding:1rem 1rem 2rem; } .hero h1,.public-hero h1 { font-size:2rem; } .public-hero { padding:28px 22px; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    global st
    import streamlit as st

    st.set_page_config(page_title="HazeShield | Haze cover for every workday", page_icon="🌿", layout="wide")
    render_styles(st)
    try:
        config_data = request_api("/config")
    except RuntimeError as error:
        st.error(f"Backend API is unavailable. Start it with `uvicorn backend.main:api --reload`. {error}")
        st.stop()

    with st.sidebar:
        st.markdown("<div style='font-family:Manrope;font-size:1.55rem;font-weight:800'>Haze<span style='color:#c7e76b'>Shield</span></div>", unsafe_allow_html=True)
        st.caption("Parametric cover for outdoor workers")
        language = st.selectbox("Language / Bahasa", ["English", "Bahasa Malaysia"])
        role_label = "Choose demo profile" if language == "English" else "Pilih profil demo"
        selected_role = st.radio(role_label, ["Worker", "Employer", "Admin"], horizontal=True)
        role_key = selected_role.lower()
        profiles = request_api(f"/users?role={role_key}")
        selected_user = st.selectbox("Demo account", profiles, format_func=lambda item: item["name"])
        if role_key == "worker":
            pages = ["Home", "Zones", "My cover", "Payouts", "Help"]
        elif role_key == "employer":
            pages = ["Group cover", "Zones", "Help"]
        else:
            pages = ["Overview", "Simulation", "Audit log", "Zones", "Help"]
        page = st.radio("Navigate", pages, label_visibility="collapsed")
        st.divider()
        st.caption("DEMO MODE · Payments and transfers are simulated")

    zones = request_api("/zones")
    zone_by_id = {row["id"]: row for row in zones}
    user_zone = zone_by_id[selected_user["zone_id"]]
    title = "Your haze cover, at a glance" if role_key == "worker" else "HazeShield control room"
    if language == "Bahasa Malaysia" and role_key == "worker":
        title = "Perlindungan jerebu anda, sepintas lalu"
    st.markdown(
        f"<div class='hero'><div class='eyebrow'>Malaysian worker protection · {date.today():%d %b %Y}</div><h1>{title}</h1>"
        "<p>Automatic support when unhealthy air keeps you from earning outdoors.</p></div>",
        unsafe_allow_html=True,
    )

    if page == "Home":
        zone_dashboard = request_api(f"/zones/{user_zone['id']}/dashboard")
        user_dashboard = request_api(f"/users/{selected_user['id']}/dashboard")
        latest_record = zone_dashboard["latest"]
        latest = latest_record["api_value"] if latest_record else None
        band, band_color, band_bg = band_for(latest)
        policies = [policy for policy in user_dashboard["policies"] if policy["status"] == "active"]
        history = zone_dashboard["history"]
        left, right = st.columns([1.15, 1])
        with left:
            st.markdown(f"<div class='notice'><span class='eyebrow'>{user_zone['name']} · API TODAY</span><br>"
                        f"<span class='api-number' style='color:{band_color}'>{latest if latest is not None else '—'}</span>"
                        f"<br><span style='background:{band_bg};color:{band_color};padding:5px 9px;border-radius:99px;font-weight:700'>{band}</span></div>",
                        unsafe_allow_html=True)
            st.write("")
            st.markdown("**Two-day trigger tracker**")
            streak = zone_dashboard["streak"]
            progress = min(streak, config_data["consecutive_days"]) / config_data["consecutive_days"]
            st.progress(progress, text=f"{min(streak, 2)} of 2 consecutive days above API 150")
            st.caption("Demo payouts use the two-day rule. Imported live-feed readings do not trigger payouts.")
        with right:
            if history:
                st.markdown("**Air quality · last 30 days**")
                st.line_chart({"API": {row["reading_date"]: row["api_value"] for row in reversed(history)}}, height=210)
            if policies:
                st.markdown(f"**Active cover** · {policies[0]['plan_name']}")
                st.caption(f"Covered through {policies[0]['end_date']} · RM30 per qualifying day")
            else:
                st.warning("No active cover for this account.")
                if st.button("Explore cover", type="primary"):
                    st.info("Choose My cover in the navigation to compare plans.")
        a, b, c = st.columns(3)
        a.metric("Paid to your wallet", money(user_dashboard["payout_total"]))
        b.metric("Qualifying days", user_dashboard["payout_count"])
        c.metric("Your zone", user_zone["name"])
        source_name = latest_record["source"] if latest_record else "No reading"
        st.caption(f"Reading source: {source_name}. Live-feed values are display-only until an official source and index scale are verified.")

    elif page == "Zones":
        st.markdown("### Zone board")
        st.caption("Readings and source status are provided by the backend API.")
        rows = []
        for zone in zones:
            snapshot = request_api(f"/zones/{zone['id']}/dashboard")
            latest_record = snapshot["latest"]
            api_value = latest_record["api_value"] if latest_record else None
            band, _, _ = band_for(api_value)
            progress = snapshot["streak"]
            source_name = latest_record["source"] if latest_record else "No reading"
            rows.append({"Zone": zone["name"], "State": zone["state"], "API": api_value, "Band": band,
                         "Source": source_name,
                         "Trigger progress": f"{min(progress, 2)} / 2 days"})
        st.dataframe(rows, hide_index=True, use_container_width=True)
        feed_status = config_data["feed"]
        st.info(f"Data mode: {config_data['data_mode']} · live provider: {config_data['live_provider']}.")
        if feed_status["last_error"]:
            st.warning(f"Live feed polling failed: {feed_status['last_error']}")
        st.caption("Imported live readings are display-only. Trigger and payout processing remains disabled for them.")

    elif page == "My cover":
        st.markdown("### Choose your cover")
        st.write("One simple premium. A fixed payout when the air crosses the trigger.")
        plans = request_api("/plans")
        plan_columns = st.columns(2)
        for index, plan in enumerate(plans):
            if plan["plan_type"] == "group":
                continue
            with plan_columns[index % 2]:
                st.markdown(f"#### {plan['name']}")
                st.markdown(f"<span class='api-number' style='font-size:2rem'>{money(plan['price'])}</span>"
                            f"<span class='small-muted'> / {'month' if plan['plan_type']=='monthly' else 'season'}</span>",
                            unsafe_allow_html=True)
                st.write(plan["description"])
                if st.button(f"Select {plan['name']}", key=f"plan-{plan['id']}", type="primary"):
                    st.session_state["chosen_plan_id"] = plan["id"]
        plan_id = st.session_state.get("chosen_plan_id")
        if plan_id:
            chosen = next(plan for plan in plans if plan["id"] == plan_id)
            with st.form("purchase_policy"):
                zone_choice = st.selectbox("Covered zone", zones, index=next(i for i, row in enumerate(zones) if row["id"] == selected_user["zone_id"]), format_func=lambda row: row["name"])
                wallet_choice = st.selectbox("Payout wallet", ["Touch n Go", "GrabPay", "Boost"])
                confirm = st.form_submit_button(f"Pay {money(chosen['price'])} · Demo payment", type="primary")
            if confirm:
                request_api("/policies", "POST", {
                    "user_id": selected_user["id"],
                    "plan_id": plan_id,
                    "zone_id": zone_choice["id"],
                    "wallet": wallet_choice,
                })
                st.success("Cover activated. Demo payment recorded as simulated.")
        st.markdown("#### Your active policies")
        policies = request_api(f"/users/{selected_user['id']}/dashboard")["policies"]
        if policies:
            st.dataframe([{"Plan": p["plan_name"], "Zone": zone_by_id[p["zone_id"]]["name"], "Status": p["status"], "Ends": p["end_date"]} for p in policies], hide_index=True, use_container_width=True)

    elif page == "Payouts":
        st.markdown("### Payout history")
        user_dashboard = request_api(f"/users/{selected_user['id']}/dashboard")
        payouts = user_dashboard["payouts"]
        if payouts:
            st.dataframe([dict(row) for row in payouts], hide_index=True, use_container_width=True)
        else:
            st.info("No payouts yet. If your zone records API above 150 for two days in a row, an eligible active policy is paid automatically.")
        alerts = user_dashboard["alerts"]
        if alerts:
            st.markdown("#### Recent alerts")
            for alert in alerts:
                st.markdown(f"• {alert['message']}  \n<small>{alert['created_at']}</small>", unsafe_allow_html=True)

    elif page == "Group cover":
        st.markdown("### Cover a whole crew")
        st.write("Keep your outdoor team protected under one monthly group plan.")
        workers = st.number_input("Number of workers", min_value=1, max_value=500, value=20, step=1)
        total = workers * config_data["group_price_per_worker"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Workers", f"{workers}")
        col2.metric("Per worker / month", money(config_data["group_price_per_worker"]))
        col3.metric("Estimated monthly total", money(total))
        st.markdown("**Included** · automatic zone trigger · RM30 per qualifying day · simulated wallet transfer")
        st.caption("Demo quote only. Worker roster, CSV onboarding and consolidated billing are not connected in this prototype.")

    elif page == "Simulation":
        st.markdown("### Admin · inject an API reading")
        st.markdown("<div class='notice'>SIMULATED ONLY · This tool writes demo readings to the local SQLite database and immediately evaluates the trigger.</div>", unsafe_allow_html=True)
        with st.form("inject_form"):
            zone = st.selectbox("Zone", zones, format_func=lambda row: row["name"])
            reading_day = st.date_input("Reading date", value=date.today())
            api_value = st.number_input("API value", min_value=0, max_value=1000, value=160, step=1)
            submitted = st.form_submit_button("Inject reading and check trigger", type="primary")
        if submitted:
            result = request_api("/readings/simulate", "POST", {
                "zone_id": zone["id"],
                "reading_date": reading_day.isoformat(),
                "api_value": int(api_value),
                "actor_id": selected_user["id"],
            })
            if result["missing"]:
                st.warning("A neighboring day's reading is missing. No trigger or payout was created.")
            elif result["triggered"]:
                st.success(f"Trigger confirmed · event #{result['event_id']} · {result['payouts']} new payout(s) of RM30 created.")
            else:
                streak = request_api(
                    f"/zones/{zone['id']}/dashboard?as_of={reading_day.isoformat()}"
                )["streak"]
                st.info(f"Reading stored. Trigger not confirmed yet · {min(streak, 2)} of 2 consecutive qualifying days.")
        st.markdown("#### Demo sequence")
        st.write("Choose a date with an available reading on the previous day, inject API 160, then inject API 165 for the next day.")
        st.caption("Payouts are simulated instantly. Each active policy is capped at five paid days during July-September.")

    elif page == "Overview":
        overview = request_api("/admin/overview")
        a, b, c, d = st.columns(4)
        a.metric("Active policies", overview["active_policies"])
        b.metric("Demo premiums", money(overview["paid_premiums"]))
        c.metric("Simulated payouts", money(overview["paid_payouts"]))
        d.metric("Trigger events", overview["trigger_events"])
        st.markdown("### Zones at a glance")
        rows = [{"Zone": zone["name"], "API": zone["api_value"], "Band": band_for(zone["api_value"])[0]} for zone in overview["zones"]]
        st.dataframe(rows, hide_index=True, use_container_width=True)
        st.caption("Loss ratio and official-source figures are omitted because this prototype uses illustrative demo data.")

    elif page == "Audit log":
        st.markdown("### Admin audit trail")
        logs = request_api("/admin/audit")
        st.dataframe([dict(row) for row in logs], hide_index=True, use_container_width=True)
        if st.button("Reset demo data", type="secondary"):
            request_api("/admin/reset", "POST", {"actor_id": selected_user["id"]})
            st.success("Local demo database reset to its seeded state. Refresh the page to continue.")

    elif page == "Help":
        st.markdown("### How the payout works")
        steps = st.columns(3)
        steps[0].markdown("**01 · Enrol**  \nChoose your work zone and activate a plan.")
        steps[1].markdown("**02 · Threshold**  \nAPI must be above 150 for two consecutive days.")
        steps[2].markdown("**03 · Receive**  \nRM30 per qualifying day is sent to your selected wallet.")
        st.divider()
        st.markdown("**Does this need a claim?** Demo payouts are created by the simulated trigger flow.  \n**Is this a real insurance product?** No. HazeShield is a coursework prototype and not an offer of insurance.  \n**Are payments real?** No. Payments and transfers are simulated. An external readings feed can be configured, but imported readings do not trigger payouts.")
        st.markdown("For support, contact your project team.")


def get_plans() -> list[sqlite3.Row]:
    with connect() as db:
        return db.execute("SELECT * FROM plans ORDER BY id").fetchall()


if __name__ == "__main__":
    raise SystemExit("The combined frontend has been retired. Run customer_app.py or admin_app.py instead.")
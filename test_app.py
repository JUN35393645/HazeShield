import tempfile
import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import app
import admin_app
import customer_app
from fastapi import HTTPException
from PIL import Image
from backend import feed
from backend.security import hash_password, issue_session_token, session_user_id, verify_password
from backend.main import get_config as api_get_config
from backend.main import get_zones as api_get_zones
from backend.main import health as api_health
from backend.main import (
    AccountCreation,
    EmployerMemberAdd,
    LoginRequest,
    PolicyPurchase,
    PolicyStatusUpdate,
    add_employer_member,
    anonymize_user_account,
    admin_account,
    create_policy_for_account,
    ensure_demo_credentials,
    login_account,
    public_account,
    register_account,
    remove_employer_member,
    update_policy_status,
    user_dashboard_data,
)
from backend.main import zone_dashboard as api_zone_dashboard


class HazeShieldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        app.DATABASE_PATH = Path(self.temp_dir.name) / "test.db"
        app.init_database()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_api_band_boundaries(self) -> None:
        self.assertEqual(app.band_for(100)[0], "Good / moderate")
        self.assertEqual(app.band_for(101)[0], "Sensitive groups")
        self.assertEqual(app.band_for(150)[0], "Sensitive groups")
        self.assertEqual(app.band_for(151)[0], "Unhealthy")
        self.assertEqual(app.band_for(200)[0], "Unhealthy")
        self.assertEqual(app.band_for(201)[0], "Very unhealthy")

    def test_air_quality_stickers_follow_api_severity_bands(self) -> None:
        self.assertIsNone(customer_app.air_quality_sticker(None))
        self.assertEqual(customer_app.air_quality_sticker(100).name, "Good_display.png")
        self.assertEqual(customer_app.air_quality_sticker(101).name, "Moderate_display.png")
        self.assertEqual(customer_app.air_quality_sticker(150).name, "Moderate_display.png")
        self.assertEqual(customer_app.air_quality_sticker(151).name, "Bad_display.png")

    def test_admin_chart_axis_scales_with_account_counts(self) -> None:
        small_counts = [{"Zone": "Ipoh", "Customers": 1}]
        larger_counts = [
            {"Zone": "Ipoh", "Customers": 8},
            {"Zone": "Klang Valley", "Customers": 15},
        ]
        self.assertEqual(admin_app.chart_y_axis_max(small_counts, "Customers"), 1)
        self.assertEqual(admin_app.chart_y_axis_max(larger_counts, "Customers"), 15)

    def test_area_chart_keys_change_with_zone_and_readings(self) -> None:
        history = [{"reading_date": "2026-10-01", "api_value": 80}]
        changed_history = [{"reading_date": "2026-10-01", "api_value": 160}]
        self.assertNotEqual(customer_app.api_chart_key(1, history), customer_app.api_chart_key(2, history))
        self.assertNotEqual(customer_app.api_chart_key(1, history), customer_app.api_chart_key(1, changed_history))

    def test_api_base_url_normalizes_render_internal_hostport(self) -> None:
        self.assertEqual(
            app.normalize_api_base_url("hazeshield-api:10000"),
            "http://hazeshield-api:10000/api/v1",
        )
        self.assertEqual(
            app.normalize_api_base_url("hazeshield-api.onrender.com"),
            "https://hazeshield-api.onrender.com/api/v1",
        )
        self.assertEqual(
            app.normalize_api_base_url("http://127.0.0.1:8000/api/v1/"),
            "http://127.0.0.1:8000/api/v1",
        )
        self.assertEqual(
            app.normalize_api_base_url("https://hazeshield-api.onrender.com/api/v1"),
            "https://hazeshield-api.onrender.com/api/v1",
        )

    def test_password_hash_and_session_token_validation(self) -> None:
        password_hash = hash_password("correct horse battery")
        self.assertNotEqual(password_hash, "correct horse battery")
        self.assertTrue(verify_password("correct horse battery", password_hash))
        self.assertFalse(verify_password("wrong password", password_hash))

        token = issue_session_token(42)
        self.assertEqual(session_user_id(token), 42)
        self.assertIsNone(session_user_id(token + "tampered"))

    def test_backend_api_exposes_seeded_readings(self) -> None:
        self.assertEqual(api_health()["status"], "ok")
        self.assertEqual(api_get_config()["data_mode"], "simulated")
        self.assertEqual(len(api_get_zones()), 7)
        self.assertEqual(api_zone_dashboard(1)["latest"]["source"], "SIMULATED")

    def test_default_zone_has_a_bad_sticker_reading_today(self) -> None:
        default_zone = app.get_zones()[0]
        self.assertEqual(default_zone["name"], "Ipoh")
        reading = app.get_reading(default_zone["id"], date.today())
        self.assertGreater(reading, 150)
        self.assertEqual(customer_app.air_quality_sticker(reading).name, "Bad_display.png")

    def test_air_quality_sticker_assets_share_a_fixed_canvas(self) -> None:
        sticker_paths = [
            customer_app.air_quality_sticker(reading)
            for reading in (50, 120, 180)
        ]
        self.assertTrue(all(path is not None and path.is_file() for path in sticker_paths))
        dimensions = []
        for path in sticker_paths:
            if path is not None:
                with Image.open(path) as image:
                    dimensions.append(image.size)
        self.assertEqual(dimensions, [(500, 500)] * 3)

    def test_demo_accounts_are_not_duplicated_on_database_reinitialization(self) -> None:
        initial_ids = [user["id"] for user in app.get_users()]
        app.init_database()
        app.init_database()
        self.assertEqual([user["id"] for user in app.get_users()], initial_ids)

    def test_legacy_worker_database_migrates_without_losing_policy(self) -> None:
        legacy_path = self.temp_dir.name + "\\legacy.db"
        previous_path = app.DATABASE_PATH
        app.DATABASE_PATH = Path(legacy_path)
        try:
            legacy_connection = sqlite3.connect(legacy_path)
            with legacy_connection as db:
                db.executescript(
                    "CREATE TABLE zones(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, state TEXT NOT NULL);"
                    "CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, "
                    "zone_id INTEGER, wallet TEXT DEFAULT 'Touch n Go', referral_code TEXT NOT NULL UNIQUE);"
                    "CREATE TABLE plans(id INTEGER PRIMARY KEY, name TEXT NOT NULL, plan_type TEXT NOT NULL, "
                    "price REAL NOT NULL, description TEXT NOT NULL);"
                    "CREATE TABLE policies(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, plan_id INTEGER NOT NULL, "
                    "zone_id INTEGER NOT NULL, status TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, "
                    "auto_renew INTEGER NOT NULL DEFAULT 1);"
                )
                db.executemany("INSERT INTO zones(id,name,state) VALUES(?,?,?)", [
                    (index, name, state) for index, (name, state) in enumerate(app.ZONES, start=1)
                ])
                db.executemany("INSERT INTO plans VALUES(?,?,?,?,?)", [
                    (1, "Monthly", "monthly", 15, "Monthly demo"),
                    (2, "Haze season", "seasonal", 60, "Seasonal demo"),
                    (3, "Worker group", "group", 250, "Group demo"),
                ])
                db.executemany("INSERT INTO users VALUES(?,?,?,?,?,?)", [
                    (1, "Legacy Worker", "worker", 1, "Touch n Go", "HAZE-AMINA"),
                    (2, "Legacy Employer", "employer", 1, "Touch n Go", "HAZE-EMPLOYER"),
                    (3, "Legacy Admin", "admin", 1, "Touch n Go", "HAZE-ADMIN"),
                ])
                today = date.today().isoformat()
                db.execute(
                    "INSERT INTO policies(id,user_id,plan_id,zone_id,status,start_date,end_date) VALUES(1,1,1,1,'active',?,?)",
                    (today, today),
                )
            legacy_connection.close()
            app.init_database()
            migrated = app.get_users("customer")[0]
            self.assertEqual(migrated["role"], "customer")
            self.assertEqual(migrated["occupation"], "Delivery rider")
            with app.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM policies WHERE id=1").fetchone()[0], 1)
                columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
            self.assertIn("password_hash", columns)
            self.assertIn("account_status", columns)
        finally:
            app.DATABASE_PATH = previous_path

    def test_registered_customer_can_purchase_individual_plan(self) -> None:
        customer = app.get_users("customer")[0]
        profile = public_account(customer)
        monthly_plan = next(plan for plan in app.get_plans() if plan["plan_type"] == "monthly")
        result = create_policy_for_account(PolicyPurchase(
            plan_id=monthly_plan["id"],
            zone_id=customer["zone_id"], wallet="GrabPay",
        ), profile)
        self.assertEqual(result["status"], "demo_purchase_recorded")
        with app.connect() as db:
            purchases = db.execute(
                "SELECT COUNT(*) FROM policies WHERE user_id=?", (customer["id"],)
            ).fetchone()[0]
        self.assertEqual(purchases, 2)

    def test_new_account_starts_unprotected_then_becomes_protected(self) -> None:
        zone = app.get_zones()[0]
        registration = register_account(AccountCreation(
            name="New Demo User", email="new.demo@gmail.com", password="Password123!",
            zone_id=zone["id"], account_type="individual", occupation="Other",
            occupation_other="Street artist",
        ))
        account = registration["account"]
        self.assertEqual(account["role"], "customer")
        dashboard = user_dashboard_data(account["id"])
        self.assertEqual(dashboard["protection_status"], "Not Protected")
        self.assertEqual(dashboard["payments"], [])

        monthly_plan = next(plan for plan in app.get_plans() if plan["plan_type"] == "monthly")
        create_policy_for_account(PolicyPurchase(
            plan_id=monthly_plan["id"],
            zone_id=zone["id"], wallet="Touch n Go",
        ), account)
        dashboard = user_dashboard_data(account["id"])
        self.assertEqual(dashboard["protection_status"], "Protected")
        self.assertEqual(len(dashboard["payments"]), 1)
        with self.assertRaises(HTTPException):
            register_account(AccountCreation(
                name="Duplicate Account", email="NEW.DEMO@gmail.com", password="Password123!",
                zone_id=zone["id"], account_type="individual", occupation="Other",
                occupation_other="Artist",
            ))
        with self.assertRaises(HTTPException):
            register_account(AccountCreation(
                name="Non Gmail", email="person@example.com", password="Password123!",
                zone_id=zone["id"], account_type="individual", occupation="Other",
                occupation_other="Artist",
            ))

    def test_admin_policy_changes_are_audited_and_reject_non_admins(self) -> None:
        with app.connect() as db:
            policy_id = db.execute("SELECT id FROM policies WHERE user_id=1 LIMIT 1").fetchone()[0]
        customer = public_account(app.get_users("customer")[0])
        admin = app.get_users("admin")[0]
        with self.assertRaises(HTTPException):
            admin_account(customer)

        result = update_policy_status(
            policy_id, PolicyStatusUpdate(status="cancelled"), public_account(admin)
        )
        self.assertEqual(result["status"], "cancelled")
        with app.connect() as db:
            audit = db.execute(
                "SELECT action FROM audit_logs WHERE actor_id=? ORDER BY id DESC LIMIT 1",
                (admin["id"],),
            ).fetchone()
        self.assertEqual(audit["action"], "policy_status_change")

    def test_admin_anonymizes_account_and_retains_financial_history(self) -> None:
        zone = next(item for item in app.get_zones() if item["name"] == "Klang Valley")
        registration = register_account(AccountCreation(
            name="Privacy Test User", email="privacy.test@gmail.com", password="StrongPass123!",
            zone_id=zone["id"], account_type="individual", occupation="Delivery rider",
        ))
        customer = registration["account"]
        monthly_plan = next(plan for plan in app.get_plans() if plan["plan_type"] == "monthly")
        create_policy_for_account(PolicyPurchase(
            plan_id=monthly_plan["id"], zone_id=zone["id"], wallet="Touch n Go",
        ), customer)
        first_day = date.today() + timedelta(days=2)
        app.inject_reading(zone["id"], first_day, 160, 5)
        payout_result = app.inject_reading(zone["id"], first_day + timedelta(days=1), 165, 5)
        self.assertGreaterEqual(payout_result["payouts"], 2)

        admin = public_account(app.get_users("admin")[0])
        with self.assertRaises(HTTPException):
            anonymize_user_account(customer["id"], customer)
        self.assertEqual(anonymize_user_account(customer["id"], admin)["status"], "anonymized")

        with app.connect() as db:
            account = db.execute("SELECT * FROM users WHERE id=?", (customer["id"],)).fetchone()
            policy = db.execute("SELECT status FROM policies WHERE user_id=?", (customer["id"],)).fetchone()
            payment = db.execute("SELECT method FROM payments WHERE user_id=?", (customer["id"],)).fetchone()
            payouts = db.execute(
                "SELECT wallet FROM payouts JOIN policies ON policies.id=payouts.policy_id "
                "WHERE policies.user_id=?",
                (customer["id"],),
            ).fetchall()
            audit = db.execute(
                "SELECT action FROM audit_logs WHERE actor_id=? ORDER BY id DESC LIMIT 1",
                (admin["id"],),
            ).fetchone()
        self.assertEqual(account["account_status"], "deleted")
        self.assertIsNone(account["email"])
        self.assertIsNone(account["password_hash"])
        self.assertEqual(policy["status"], "cancelled")
        self.assertEqual(payment["method"], "Anonymized")
        self.assertEqual(len(payouts), 2)
        self.assertTrue(all(row["wallet"] == "Anonymized" for row in payouts))
        self.assertEqual(audit["action"], "account_anonymized")
        self.assertNotIn(customer["id"], [row["id"] for row in app.get_users("customer")])
        with self.assertRaises(HTTPException):
            login_account(LoginRequest(email=customer["email"], password="StrongPass123!"))

    def test_employer_can_add_existing_account_and_sponsor_coverage(self) -> None:
        zone = app.get_zones()[0]
        member_result = register_account(AccountCreation(
            name="Existing Member", email="member.demo@gmail.com", password="Password123!",
            zone_id=zone["id"], account_type="individual", occupation="Delivery rider",
        ))
        employer_result = register_account(AccountCreation(
            name="Demo Business", email="business.demo@gmail.com", password="Password123!",
            zone_id=zone["id"], account_type="employer", company_name="Demo Business Sdn Bhd",
        ))
        employer = employer_result["account"]
        member = member_result["account"]
        with self.assertRaises(HTTPException):
            add_employer_member(EmployerMemberAdd(email="unknown.demo@gmail.com"), employer)
        self.assertEqual(
            add_employer_member(EmployerMemberAdd(email=member["email"]), employer)["status"],
            "member_added",
        )
        group_plan = next(plan for plan in app.get_plans() if plan["plan_type"] == "group")
        create_policy_for_account(PolicyPurchase(
            plan_id=group_plan["id"], zone_id=zone["id"], wallet="Touch n Go",
        ), employer)
        self.assertEqual(user_dashboard_data(member["id"])["protection_status"], "Protected")
        payment_count_before = user_dashboard_data(employer["id"])["payments"]
        with self.assertRaises(HTTPException):
            create_policy_for_account(PolicyPurchase(
                plan_id=group_plan["id"], zone_id=zone["id"], wallet="Touch n Go",
            ), employer)
        self.assertEqual(user_dashboard_data(employer["id"])["payments"], payment_count_before)
        self.assertEqual(remove_employer_member(member["id"], employer)["status"], "member_removed")
        self.assertEqual(user_dashboard_data(member["id"])["protection_status"], "Not Protected")
        with app.connect() as db:
            parent_policy_id = db.execute(
                "SELECT id FROM policies WHERE user_id=? AND sponsor_policy_id IS NULL "
                "ORDER BY id DESC LIMIT 1",
                (employer["id"],),
            ).fetchone()[0]
        admin = public_account(app.get_users("admin")[0])
        update_policy_status(parent_policy_id, PolicyStatusUpdate(status="cancelled"), admin)
        update_policy_status(parent_policy_id, PolicyStatusUpdate(status="active"), admin)
        self.assertEqual(user_dashboard_data(member["id"])["protection_status"], "Not Protected")
        self.assertEqual(
            add_employer_member(EmployerMemberAdd(email=member["email"]), employer)["status"],
            "member_added",
        )
        self.assertEqual(user_dashboard_data(member["id"])["protection_status"], "Protected")

    def test_group_employer_is_not_a_payout_recipient(self) -> None:
        employer = public_account(app.get_users("employer")[0])
        group_plan = next(plan for plan in app.get_plans() if plan["plan_type"] == "group")
        with self.assertRaises(HTTPException):
            create_policy_for_account(PolicyPurchase(
                plan_id=group_plan["id"], zone_id=employer["zone_id"], wallet="Touch n Go",
            ), employer)
        with app.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM payments WHERE user_id=?", (employer["id"],)).fetchone()[0], 0)
            db.execute(
                "INSERT INTO policies(user_id, plan_id, zone_id, status, start_date, end_date) "
                "VALUES (?, ?, ?, 'active', ?, ?)",
                (employer["id"], group_plan["id"], employer["zone_id"], date.today().isoformat(),
                 (date.today() + timedelta(days=30)).isoformat()),
            )
        first_day = date.today() + timedelta(days=100)
        self.assertFalse(app.inject_reading(employer["zone_id"], first_day, 160, 5)["triggered"])
        app.inject_reading(employer["zone_id"], first_day + timedelta(days=1), 165, 5)
        with app.connect() as db:
            employer_payouts = db.execute(
                "SELECT COUNT(*) FROM payouts pa JOIN policies p ON p.id=pa.policy_id WHERE p.user_id=?",
                (employer["id"],),
            ).fetchone()[0]
        self.assertEqual(employer_payouts, 0)

    def test_demo_login_checks_password(self) -> None:
        ensure_demo_credentials()
        session = login_account(LoginRequest(email="amina.demo@gmail.com", password="HazeDemo123!"))
        self.assertEqual(session["account"]["role"], "customer")
        starter = login_account(LoginRequest(email="new.customer.demo@gmail.com", password="HazeDemo123!"))
        self.assertEqual(user_dashboard_data(starter["account"]["id"])["protection_status"], "Not Protected")
        with self.assertRaises(HTTPException):
            login_account(LoginRequest(email="amina.demo@gmail.com", password="incorrect"))

    def test_zone_dashboard_streak_uses_requested_date(self) -> None:
        first_day = date.today() + timedelta(days=100)
        with app.connect() as db:
            db.executemany(
                "INSERT INTO readings(zone_id, reading_date, api_value, source) VALUES (1, ?, 160, 'TEST')",
                [(first_day.isoformat(),), ((first_day + timedelta(days=1)).isoformat(),)],
            )
        self.assertEqual(api_zone_dashboard(1, first_day + timedelta(days=1))["streak"], 2)

    def test_imported_feed_readings_are_display_only(self) -> None:
        response = Mock()
        response.json.return_value = {
            "readings": [{"zone": "Klang Valley", "reading_date": date.today().isoformat(), "api_value": 163}]
        }
        response.raise_for_status.return_value = None
        with patch.object(feed, "FEED_URL", "https://feed.example.test/readings"), \
             patch.object(feed, "FEED_SOURCE", "TEST_SOURCE"), \
             patch("backend.feed.requests.get", return_value=response):
            self.assertEqual(feed.poll_once(), 1)

        with app.connect() as db:
            reading = db.execute(
                "SELECT api_value, source FROM readings WHERE zone_id=1 AND reading_date=?",
                (date.today().isoformat(),),
            ).fetchone()
            self.assertEqual(db.execute("SELECT COUNT(*) FROM trigger_events").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM payouts").fetchone()[0], 0)
        self.assertEqual(reading["api_value"], 163)
        self.assertEqual(reading["source"], "TEST_SOURCE")

    def test_missing_reading_does_not_trigger(self) -> None:
        result = app.inject_reading(1, date.today() + timedelta(days=100), 160, 5)
        self.assertTrue(result["missing"])
        with app.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM trigger_events").fetchone()[0], 0)

    def test_trigger_extension_and_repeated_runs_are_idempotent(self) -> None:
        first_day = date.today()
        next_day = first_day + timedelta(days=1)
        final_day = first_day + timedelta(days=2)

        first = app.inject_reading(1, first_day, 160, 5)
        self.assertFalse(first["triggered"])
        confirmed = app.inject_reading(1, next_day, 165, 5)
        self.assertTrue(confirmed["triggered"])
        self.assertEqual(confirmed["payouts"], 2)

        duplicate = app.inject_reading(1, next_day, 165, 5)
        self.assertEqual(duplicate["event_id"], confirmed["event_id"])
        self.assertEqual(duplicate["payouts"], 0)

        extended = app.inject_reading(1, final_day, 170, 5)
        self.assertEqual(extended["event_id"], confirmed["event_id"])
        self.assertEqual(extended["payouts"], 1)
        duplicate_extension = app.inject_reading(1, final_day, 170, 5)
        self.assertEqual(duplicate_extension["payouts"], 0)

        with app.connect() as db:
            event = db.execute("SELECT * FROM trigger_events").fetchone()
            payout_count = db.execute("SELECT COUNT(*) FROM payouts").fetchone()[0]
        self.assertEqual(event["days_above_threshold"], 3)
        self.assertEqual(payout_count, 3)

    def test_streak_counts_backwards_without_reading_future(self) -> None:
        today = date.today()
        app.inject_reading(1, today - timedelta(days=1), 160, 5)
        app.inject_reading(1, today, 165, 5)
        self.assertEqual(app.trailing_streak(1, today), 2)

    def test_seeded_premiums_are_included_in_admin_total(self) -> None:
        with app.connect() as db:
            premium_total = db.execute("SELECT SUM(amount) FROM payments WHERE status='paid'").fetchone()[0]
        self.assertEqual(premium_total, 45)

    def test_seasonal_policy_uses_next_valid_season(self) -> None:
        today = date.today()
        user = app.get_users("customer")[0]
        seasonal_plan = next(plan for plan in app.get_plans() if plan["plan_type"] == "seasonal")
        app.buy_policy(user, seasonal_plan["id"], user["zone_id"])
        with app.connect() as db:
            policy = db.execute(
                "SELECT start_date, end_date FROM policies WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (user["id"],),
            ).fetchone()
        start = date.fromisoformat(policy["start_date"])
        end = date.fromisoformat(policy["end_date"])
        if today > date(today.year, 9, 30):
            expected_start = date(today.year + 1, 7, 1)
        elif today < date(today.year, 7, 1):
            expected_start = date(today.year, 7, 1)
        else:
            expected_start = today
        self.assertEqual(start, expected_start)
        self.assertEqual(end, date(start.year, 9, 30))


if __name__ == "__main__":
    unittest.main()
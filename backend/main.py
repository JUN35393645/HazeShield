from __future__ import annotations

import asyncio
import re
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import app as domain
from backend import feed
from backend.security import hash_password, issue_session_token, session_user_id, verify_password


OCCUPATIONS = (
    "Delivery rider",
    "E-hailing driver",
    "Food vendor",
    "Market trader",
    "Construction worker",
    "Outdoor service worker",
    "Other",
)
bearer_scheme = HTTPBearer(auto_error=False)


async def poll_live_feed() -> None:
    while True:
        try:
            await asyncio.to_thread(feed.poll_once)
        except Exception as error:
            feed.record_failure(error)
        await asyncio.sleep(feed.FEED_POLL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    domain.init_database()
    ensure_demo_credentials()
    task = asyncio.create_task(poll_live_feed()) if feed.FEED_URL else None
    try:
        yield
    finally:
        if task is not None:
            task.cancel()


api = FastAPI(title="HazeShield API", version="1.0.0", lifespan=lifespan)


class PolicyPurchase(BaseModel):
    plan_id: int = Field(gt=0)
    zone_id: int = Field(gt=0)
    wallet: str


class AccountCreation(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=6, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    zone_id: int = Field(gt=0)
    account_type: Literal["individual", "employer"]
    occupation: str | None = None
    occupation_other: str | None = Field(default=None, max_length=80)
    company_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(min_length=6, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class SimulatedReading(BaseModel):
    zone_id: int = Field(gt=0)
    reading_date: date
    api_value: int = Field(ge=0, le=1000)


class PolicyStatusUpdate(BaseModel):
    status: Literal["active", "cancelled"]


class EmployerMemberAdd(BaseModel):
    email: str = Field(min_length=6, max_length=254)


def rows_as_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def public_account(row: Any) -> dict[str, Any]:
    return {
        key: row[key]
        for key in ("id", "name", "email", "role", "zone_id", "occupation", "occupation_other", "company_name")
    }


def authenticated_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in required")
    user_id = session_user_id(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    with domain.connect() as db:
        account = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if account is None or account["account_status"] != "active":
        raise HTTPException(status_code=401, detail="Account no longer exists")
    return public_account(account)


def admin_account(account: dict[str, Any] = Depends(authenticated_account)) -> dict[str, Any]:
    if account["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return account


def ensure_demo_credentials() -> None:
    demo_accounts = {
        "HAZE-AMINA": ("amina.demo@gmail.com", "Delivery rider", None, None, "HazeDemo123!"),
        "HAZE-JUNWEI": ("jun.wei.demo@gmail.com", "E-hailing driver", None, None, "HazeDemo123!"),
        "HAZE-KAVITHA": ("kavitha.demo@gmail.com", "Food vendor", None, None, "HazeDemo123!"),
        "HAZE-CUSTOMER": ("customer.demo@gmail.com", "Other", "Outdoor worker", None, "HazeDemo123!"),
        "HAZE-STARTER": ("new.customer.demo@gmail.com", "Other", "Street market seller", None, "HazeDemo123!"),
        "HAZE-EMPLOYER": ("employer.demo@gmail.com", None, None, "Demo Employer Co.", "HazeDemo123!"),
        "HAZE-ADMIN": ("admin.demo@gmail.com", None, None, None, "AdminDemo123!"),
    }
    with domain.connect() as db:
        for referral_code, (email, occupation, occupation_other, company_name, password) in demo_accounts.items():
            user = db.execute(
                "SELECT id, password_hash, account_status FROM users WHERE referral_code=?",
                (referral_code,),
            ).fetchone()
            if user is None or user["password_hash"] or user["account_status"] != "active":
                continue
            db.execute(
                "UPDATE users SET email=?, password_hash=?, occupation=COALESCE(occupation, ?), "
                "occupation_other=COALESCE(occupation_other, ?), company_name=COALESCE(company_name, ?) "
                "WHERE id=?",
                (email, hash_password(password), occupation, occupation_other, company_name, user["id"]),
            )


def register_account(payload: AccountCreation) -> dict[str, Any]:
    name = payload.name.strip()
    email = payload.email.strip().lower()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Name must contain at least two non-space characters")
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@gmail\.com", email):
        raise HTTPException(status_code=422, detail="Use a Gmail address ending in @gmail.com")
    if payload.zone_id not in {zone["id"] for zone in domain.get_zones()}:
        raise HTTPException(status_code=404, detail="Zone not found")
    if payload.account_type == "individual":
        if payload.occupation not in OCCUPATIONS:
            raise HTTPException(status_code=422, detail="Choose a listed occupation")
        if payload.occupation == "Other" and not (payload.occupation_other or "").strip():
            raise HTTPException(status_code=422, detail="Describe your occupation")
        role = "customer"
        company_name = None
    else:
        if not (payload.company_name or "").strip():
            raise HTTPException(status_code=422, detail="Company name is required for employer accounts")
        role = "employer"
        company_name = payload.company_name.strip()
    with domain.connect() as db:
        if db.execute("SELECT 1 FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone():
            raise HTTPException(status_code=409, detail="An account with this Gmail address already exists")
        cursor = db.execute(
            "INSERT INTO users(name, role, zone_id, referral_code, email, password_hash, occupation, occupation_other, company_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name, role, payload.zone_id, f"HS-{uuid.uuid4().hex[:10].upper()}",
                email, hash_password(payload.password), payload.occupation,
                (payload.occupation_other or "").strip() or None, company_name,
            ),
        )
        account = db.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
    profile = public_account(account)
    return {"access_token": issue_session_token(profile["id"]), "token_type": "bearer", "account": profile}


def login_account(payload: LoginRequest) -> dict[str, Any]:
    email = payload.email.strip().lower()
    with domain.connect() as db:
        account = db.execute(
            "SELECT * FROM users WHERE email=? COLLATE NOCASE AND account_status='active'",
            (email,),
        ).fetchone()
    if account is None or not verify_password(payload.password, account["password_hash"] or ""):
        raise HTTPException(status_code=401, detail="Gmail or password is incorrect")
    profile = public_account(account)
    return {"access_token": issue_session_token(profile["id"]), "token_type": "bearer", "account": profile}


@api.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_mode": "simulated"}


@api.get("/api/v1/config")
def get_config() -> dict[str, Any]:
    feed_status = feed.status()
    mode = "live_feed_configured" if feed_status["configured"] else "simulated"
    return {**domain.CONFIG, "data_mode": mode, "live_provider": feed_status["source"], "feed": feed_status}


@api.get("/api/v1/zones")
def get_zones() -> list[dict[str, Any]]:
    return rows_as_dicts(domain.get_zones())


@api.get("/api/v1/users")
def get_users(
    role: str | None = None,
    _: dict[str, Any] = Depends(admin_account),
) -> list[dict[str, Any]]:
    return [public_account(row) for row in domain.get_users(role)]


def anonymize_user_account(user_id: int, actor: dict[str, Any]) -> dict[str, str]:
    if actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    with domain.connect() as db:
        target = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if target is None or target["account_status"] != "active":
            raise HTTPException(status_code=404, detail="Active account not found")
        if target["role"] == "admin":
            raise HTTPException(status_code=409, detail="Admin accounts cannot be deleted here")

        policy_ids = [
            row["id"] for row in db.execute(
                "SELECT id FROM policies WHERE user_id=? OR sponsor_user_id=? "
                "OR sponsor_policy_id IN (SELECT id FROM policies WHERE user_id=? OR sponsor_user_id=?)",
                (user_id, user_id, user_id, user_id),
            ).fetchall()
        ]
        if policy_ids:
            placeholders = ",".join("?" for _ in policy_ids)
            cancelled = db.execute(
                f"UPDATE policies SET status='cancelled' WHERE id IN ({placeholders}) AND status!='cancelled'",
                policy_ids,
            ).rowcount
            db.execute(
                f"UPDATE payouts SET wallet='Anonymized' WHERE policy_id IN ({placeholders})",
                policy_ids,
            )
            db.execute(
                f"UPDATE payments SET method='Anonymized' WHERE policy_id IN ({placeholders})",
                policy_ids,
            )
        else:
            cancelled = 0
        db.execute(
            "UPDATE employer_memberships SET status='removed' "
            "WHERE employer_id=? OR customer_id=?",
            (user_id, user_id),
        )
        db.execute("DELETE FROM notifications WHERE user_id=?", (user_id,))
        db.execute(
            "UPDATE users SET name=?, email=NULL, password_hash=NULL, zone_id=NULL, wallet=NULL, "
            "occupation=NULL, occupation_other=NULL, company_name=NULL, "
            "account_status='deleted' WHERE id=?",
            (f"Deleted account {user_id}", user_id),
        )
        db.execute(
            "INSERT INTO audit_logs(actor_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (
                actor["id"],
                "account_anonymized",
                f"account_id={user_id}; role={target['role']}; policies_cancelled={cancelled}",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    return {"status": "anonymized"}


@api.delete("/api/v1/admin/users/{user_id}")
def delete_admin_user(
    user_id: int,
    account: dict[str, Any] = Depends(admin_account),
) -> dict[str, str]:
    return anonymize_user_account(user_id, account)


@api.get("/api/v1/plans")
def get_plans() -> list[dict[str, Any]]:
    return rows_as_dicts(domain.get_plans())


@api.post("/api/v1/auth/register", status_code=201)
def create_account(payload: AccountCreation) -> dict[str, Any]:
    return register_account(payload)


@api.post("/api/v1/auth/login")
def sign_in(payload: LoginRequest) -> dict[str, Any]:
    return login_account(payload)


@api.get("/api/v1/auth/me")
def get_current_account(account: dict[str, Any] = Depends(authenticated_account)) -> dict[str, Any]:
    return account


@api.get("/api/v1/zones/{zone_id}/dashboard")
def zone_dashboard(zone_id: int, as_of: date | None = None) -> dict[str, Any]:
    with domain.connect() as db:
        zone = db.execute("SELECT id FROM zones WHERE id=?", (zone_id,)).fetchone()
        if zone is None:
            raise HTTPException(status_code=404, detail="Zone not found")
        latest = db.execute(
            "SELECT reading_date, api_value, source FROM readings WHERE zone_id=? ORDER BY reading_date DESC LIMIT 1",
            (zone_id,),
        ).fetchone()
        history = db.execute(
            "SELECT reading_date, api_value FROM readings WHERE zone_id=? ORDER BY reading_date DESC LIMIT 30",
            (zone_id,),
        ).fetchall()
    return {
        "latest": dict(latest) if latest else None,
        "history": rows_as_dicts(history),
        "streak": domain.trailing_streak(zone_id, as_of or date.today()),
    }


def user_dashboard_data(user_id: int) -> dict[str, Any]:
    with domain.connect() as db:
        user = db.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        policies = db.execute(
            "SELECT p.*, pl.name AS plan_name, sponsor.name AS covered_by "
            "FROM policies p JOIN plans pl ON pl.id=p.plan_id "
            "LEFT JOIN users sponsor ON sponsor.id=p.sponsor_user_id "
            "WHERE p.user_id=? OR p.sponsor_user_id=? ORDER BY p.id DESC",
            (user_id, user_id),
        ).fetchall()
        payouts = db.execute(
            "SELECT pa.payout_date, pa.amount, pa.wallet, pa.status, z.name AS zone "
            "FROM payouts pa JOIN policies p ON p.id=pa.policy_id JOIN zones z ON z.id=p.zone_id "
            "WHERE p.user_id=? ORDER BY pa.payout_date DESC",
            (user_id,),
        ).fetchall()
        alerts = db.execute(
            "SELECT message, created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (user_id,),
        ).fetchall()
        payments = db.execute(
            "SELECT pay.created_at, pay.amount, pay.method, pay.status, pl.name AS plan_name "
            "FROM payments pay JOIN policies p ON p.id=pay.policy_id JOIN plans pl ON pl.id=p.plan_id "
            "WHERE pay.user_id=? ORDER BY pay.created_at DESC",
            (user_id,),
        ).fetchall()
        protected = db.execute(
            "SELECT COUNT(*) FROM policies WHERE (user_id=? OR sponsor_user_id=?) "
            "AND status='active' AND start_date<=? AND end_date>=?",
            (user_id, user_id, date.today().isoformat(), date.today().isoformat()),
        ).fetchone()[0] > 0
        payout_stats = db.execute(
            "SELECT COALESCE(SUM(pa.amount),0) AS total, COUNT(*) AS count FROM payouts pa "
            "JOIN policies p ON p.id=pa.policy_id WHERE p.user_id=?",
            (user_id,),
        ).fetchone()
    return {
        "policies": rows_as_dicts(policies),
        "payouts": rows_as_dicts(payouts),
        "alerts": rows_as_dicts(alerts),
        "payments": rows_as_dicts(payments),
        "payout_total": payout_stats["total"],
        "payout_count": payout_stats["count"],
        "protection_status": "Protected" if protected else "Not Protected",
    }


@api.get("/api/v1/users/{user_id}/dashboard")
def user_dashboard(
    user_id: int,
    account: dict[str, Any] = Depends(authenticated_account),
) -> dict[str, Any]:
    if account["id"] != user_id and account["role"] != "admin":
        raise HTTPException(status_code=403, detail="You can only view your own account")
    return user_dashboard_data(user_id)


def activate_employer_coverage(employer_id: int, customer_id: int, parent_policy: Any) -> None:
    with domain.connect() as db:
        customer = db.execute("SELECT zone_id FROM users WHERE id=? AND role='customer'", (customer_id,)).fetchone()
        if customer is None:
            return
        existing = db.execute(
            "SELECT id FROM policies WHERE sponsor_policy_id=? AND user_id=?",
            (parent_policy["id"], customer_id),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE policies SET status='active', start_date=?, end_date=? WHERE id=?",
                (parent_policy["start_date"], parent_policy["end_date"], existing["id"]),
            )
            return
        db.execute(
            "INSERT INTO policies(user_id, plan_id, zone_id, status, start_date, end_date, sponsor_user_id, sponsor_policy_id) "
            "VALUES (?, ?, ?, 'active', ?, ?, ?, ?)",
            (
                customer_id, parent_policy["plan_id"], parent_policy["zone_id"],
                parent_policy["start_date"], parent_policy["end_date"], employer_id, parent_policy["id"],
            ),
        )


def create_policy_for_account(payload: PolicyPurchase, account: dict[str, Any]) -> dict[str, str]:
    if account["role"] not in {"customer", "employer"}:
        raise HTTPException(status_code=403, detail="This account cannot purchase a plan")
    with domain.connect() as db:
        user = db.execute("SELECT * FROM users WHERE id=?", (account["id"],)).fetchone()
        plan = db.execute("SELECT id, plan_type FROM plans WHERE id=?", (payload.plan_id,)).fetchone()
        zone = db.execute("SELECT id FROM zones WHERE id=?", (payload.zone_id,)).fetchone()
        if plan is None or zone is None:
            raise HTTPException(status_code=404, detail="Plan or zone not found")
        if account["role"] == "customer" and plan["plan_type"] == "group":
            raise HTTPException(status_code=422, detail="Group plans require an employer account")
        if account["role"] == "employer" and plan["plan_type"] != "group":
            raise HTTPException(status_code=422, detail="Employers must choose a group plan")
        if plan["plan_type"] == "group":
            member_count = db.execute(
                "SELECT COUNT(*) FROM employer_memberships WHERE employer_id=? AND status='active'",
                (account["id"],),
            ).fetchone()[0]
            if member_count == 0:
                raise HTTPException(status_code=422, detail="Add at least one existing individual account before buying group cover")
            if member_count > 20:
                raise HTTPException(status_code=422, detail="The demo group plan covers up to 20 individual accounts")
            active_group = db.execute(
                "SELECT 1 FROM policies p JOIN plans pl ON pl.id=p.plan_id "
                "WHERE p.user_id=? AND p.sponsor_policy_id IS NULL AND p.status='active' "
                "AND pl.plan_type='group' AND p.start_date<=? AND p.end_date>=? LIMIT 1",
                (account["id"], date.today().isoformat(), date.today().isoformat()),
            ).fetchone()
            if active_group:
                raise HTTPException(status_code=409, detail="An active group plan already covers this employer's roster")
        db.execute("UPDATE users SET wallet=? WHERE id=?", (payload.wallet, account["id"]))
        user = db.execute("SELECT * FROM users WHERE id=?", (account["id"],)).fetchone()

    domain.buy_policy(user, payload.plan_id, payload.zone_id)
    if plan["plan_type"] == "group":
        with domain.connect() as db:
            parent_policy = db.execute(
                "SELECT * FROM policies WHERE user_id=? AND plan_id=? AND sponsor_policy_id IS NULL ORDER BY id DESC LIMIT 1",
                (account["id"], payload.plan_id),
            ).fetchone()
            members = db.execute(
                "SELECT customer_id FROM employer_memberships WHERE employer_id=? AND status='active'",
                (account["id"],),
            ).fetchall()
        for member in members:
            activate_employer_coverage(account["id"], member["customer_id"], parent_policy)
    return {"status": "demo_purchase_recorded"}


@api.get("/api/v1/employer/members")
def employer_members(account: dict[str, Any] = Depends(authenticated_account)) -> list[dict[str, Any]]:
    if account["role"] != "employer":
        raise HTTPException(status_code=403, detail="Employer account required")
    with domain.connect() as db:
        members = db.execute(
            "SELECT u.id, u.name, u.email, u.occupation, m.status, m.created_at "
            "FROM employer_memberships m JOIN users u ON u.id=m.customer_id "
            "WHERE m.employer_id=? ORDER BY u.name",
            (account["id"],),
        ).fetchall()
    return [
        {**dict(member), "protection_status": user_dashboard_data(member["id"])["protection_status"]}
        for member in members
    ]


@api.post("/api/v1/employer/members", status_code=201)
def add_employer_member(
    payload: EmployerMemberAdd,
    account: dict[str, Any] = Depends(authenticated_account),
) -> dict[str, Any]:
    if account["role"] != "employer":
        raise HTTPException(status_code=403, detail="Employer account required")
    email = payload.email.strip().lower()
    with domain.connect() as db:
        customer = db.execute(
            "SELECT id FROM users WHERE email=? COLLATE NOCASE AND role='customer'", (email,)
        ).fetchone()
        if customer is None:
            raise HTTPException(status_code=404, detail="No existing individual account has that Gmail address")
        existing = db.execute(
            "SELECT id, status FROM employer_memberships WHERE employer_id=? AND customer_id=?",
            (account["id"], customer["id"]),
        ).fetchone()
        if existing and existing["status"] == "active":
            raise HTTPException(status_code=409, detail="This account is already on the employer roster")
        member_count = db.execute(
            "SELECT COUNT(*) FROM employer_memberships WHERE employer_id=? AND status='active'",
            (account["id"],),
        ).fetchone()[0]
        if member_count >= 20:
            raise HTTPException(status_code=422, detail="The demo group plan supports up to 20 individual accounts")
        if existing:
            db.execute(
                "UPDATE employer_memberships SET status='active', created_at=? WHERE id=?",
                (datetime.now().isoformat(timespec="seconds"), existing["id"]),
            )
        else:
            db.execute(
                "INSERT INTO employer_memberships(employer_id, customer_id, status, created_at) "
                "VALUES (?, ?, 'active', ?)",
                (account["id"], customer["id"], datetime.now().isoformat(timespec="seconds")),
            )
        active_group_policies = db.execute(
            "SELECT p.* FROM policies p JOIN plans pl ON pl.id=p.plan_id "
            "WHERE p.user_id=? AND p.sponsor_policy_id IS NULL AND p.status='active' "
            "AND pl.plan_type='group' AND p.start_date<=? AND p.end_date>=?",
            (account["id"], date.today().isoformat(), date.today().isoformat()),
        ).fetchall()
    for policy in active_group_policies:
        activate_employer_coverage(account["id"], customer["id"], policy)
    return {"status": "member_added", "customer_id": customer["id"]}


@api.delete("/api/v1/employer/members/{customer_id}")
def remove_employer_member(
    customer_id: int,
    account: dict[str, Any] = Depends(authenticated_account),
) -> dict[str, str]:
    if account["role"] != "employer":
        raise HTTPException(status_code=403, detail="Employer account required")
    with domain.connect() as db:
        membership = db.execute(
            "SELECT id FROM employer_memberships WHERE employer_id=? AND customer_id=? AND status='active'",
            (account["id"], customer_id),
        ).fetchone()
        if membership is None:
            raise HTTPException(status_code=404, detail="Active employer membership not found")
        db.execute("UPDATE employer_memberships SET status='removed' WHERE id=?", (membership["id"],))
        db.execute(
            "UPDATE policies SET status='cancelled' WHERE sponsor_user_id=? AND user_id=?",
            (account["id"], customer_id),
        )
    return {"status": "member_removed"}


@api.get("/api/v1/admin/overview")
def admin_overview(_: dict[str, Any] = Depends(admin_account)) -> dict[str, Any]:
    with domain.connect() as db:
        stats = {
            "active_policies": db.execute("SELECT COUNT(*) FROM policies WHERE status='active'").fetchone()[0],
            "paid_premiums": db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid'").fetchone()[0],
            "paid_payouts": db.execute("SELECT COALESCE(SUM(amount),0) FROM payouts").fetchone()[0],
            "trigger_events": db.execute("SELECT COUNT(*) FROM trigger_events").fetchone()[0],
        }
    stats["zones"] = [
        {**dict(zone), "api_value": domain.get_reading(zone["id"])}
        for zone in domain.get_zones()
    ]
    return stats


@api.get("/api/v1/admin/audit")
def admin_audit(_: dict[str, Any] = Depends(admin_account)) -> list[dict[str, Any]]:
    with domain.connect() as db:
        logs = db.execute(
            "SELECT action, details, created_at FROM audit_logs ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return rows_as_dicts(logs)


@api.post("/api/v1/policies", status_code=201)
def purchase_policy(
    payload: PolicyPurchase,
    account: dict[str, Any] = Depends(authenticated_account),
) -> dict[str, str]:
    return create_policy_for_account(payload, account)


@api.post("/api/v1/readings/simulate")
def simulate_reading(
    payload: SimulatedReading,
    account: dict[str, Any] = Depends(admin_account),
) -> dict[str, Any]:
    with domain.connect() as db:
        zone = db.execute("SELECT id FROM zones WHERE id=?", (payload.zone_id,)).fetchone()
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    return domain.inject_reading(payload.zone_id, payload.reading_date, payload.api_value, account["id"])


@api.patch("/api/v1/admin/policies/{policy_id}")
def update_policy_status(
    policy_id: int,
    payload: PolicyStatusUpdate,
    account: dict[str, Any] = Depends(admin_account),
) -> dict[str, str]:
    with domain.connect() as db:
        policy = db.execute(
            "SELECT id, status, sponsor_policy_id, user_id FROM policies WHERE id=?", (policy_id,)
        ).fetchone()
        if policy is None:
            raise HTTPException(status_code=404, detail="Policy not found")
        db.execute("UPDATE policies SET status=? WHERE id=?", (payload.status, policy_id))
        if policy["sponsor_policy_id"] is None:
            if payload.status == "cancelled":
                db.execute("UPDATE policies SET status='cancelled' WHERE sponsor_policy_id=?", (policy_id,))
            else:
                db.execute(
                    "UPDATE policies SET status='active' WHERE sponsor_policy_id=? AND user_id IN "
                    "(SELECT customer_id FROM employer_memberships WHERE employer_id=? AND status='active')",
                    (policy_id, policy["user_id"]),
                )
        db.execute(
            "INSERT INTO audit_logs(actor_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (
                account["id"],
                "policy_status_change",
                f"policy={policy_id}; status={payload.status}",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    return {"status": payload.status}


@api.post("/api/v1/admin/reset")
def reset_demo(_: dict[str, Any] = Depends(admin_account)) -> dict[str, str]:
    domain.reset_demo()
    ensure_demo_credentials()
    return {"status": "reset"}

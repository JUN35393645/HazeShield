from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from app import band_for, money, render_styles, request_api


OCCUPATIONS = [
    "Delivery rider", "E-hailing driver", "Food vendor", "Market trader",
    "Construction worker", "Outdoor service worker", "Other",
]
APP_DIRECTORY = Path(__file__).resolve().parent


def render_brand() -> None:
    with st.container(key="brand_logo"):
        st.image(str(APP_DIRECTORY / "HazeShield Logo.png"), width=360)


def air_quality_sticker(reading: int | None) -> Path | None:
    if reading is None:
        return None
    if reading <= 100:
        name = "Good.png"
    elif reading <= 150:
        name = "Moderate.png"
    else:
        name = "Bad.png"
    return APP_DIRECTORY / name


def set_account_session(auth_result: dict) -> None:
    st.session_state["access_token"] = auth_result["access_token"]
    st.session_state["account"] = auth_result["account"]


def policy_is_current(policy: dict, today: date | None = None) -> bool:
    current_date = (today or date.today()).isoformat()
    return policy["status"] == "active" and policy["start_date"] <= current_date <= policy["end_date"]


def go_to_signup(plan: dict, account_type: str) -> None:
    st.session_state["preferred_plan_id"] = plan["id"]
    st.session_state["account_type"] = account_type
    st.session_state["go_get_protection"] = True
    st.rerun()


def render_api_chart(history: list[dict], height: int = 250) -> None:
    values = [
        {"reading_date": row["reading_date"], "api_value": row["api_value"]}
        for row in history
    ]
    if not values:
        return
    y_max = max(150, max(row["api_value"] for row in values)) * 1.1
    st.vega_lite_chart(
        spec={
            "data": {"values": values},
            "width": "container",
            "height": height,
            "encoding": {
                "x": {
                    "field": "reading_date",
                    "type": "temporal",
                    "axis": {"title": None, "grid": False, "labelAngle": 0},
                },
                "y": {
                    "field": "api_value",
                    "type": "quantitative",
                    "axis": {"title": "API index", "gridColor": "#e7e9df"},
                    "scale": {"domain": [0, y_max]},
                },
            },
            "layer": [
                {"mark": {"type": "area", "color": "#176b52", "opacity": 0.1}},
                {
                    "mark": {
                        "type": "line",
                        "color": "#176b52",
                        "strokeWidth": 3,
                        "point": {"filled": True, "color": "#176b52", "size": 48},
                    },
                    "encoding": {
                        "tooltip": [
                            {"field": "reading_date", "type": "temporal", "title": "Date"},
                            {"field": "api_value", "type": "quantitative", "title": "API"},
                        ]
                    },
                },
                {
                    "mark": {"type": "rule", "color": "#ee7658", "strokeDash": [6, 4], "strokeWidth": 2},
                    "encoding": {
                        "x": {"field": "reading_date", "type": "temporal", "aggregate": "min"},
                        "x2": {"field": "reading_date", "type": "temporal", "aggregate": "max"},
                        "y": {"datum": 150},
                    },
                },
            ],
            "config": {
                "view": {"stroke": None},
                "axis": {
                    "labelColor": "#66746d",
                    "titleColor": "#66746d",
                    "labelFont": "DM Sans",
                    "titleFont": "DM Sans",
                },
            },
        },
        use_container_width=True,
    )


def sign_up(zones: list[dict], plans: list[dict]) -> None:
    account_type = st.radio("Account type", ["Individual", "Employer"], horizontal=True, key="account_type")
    account_plans = [
        plan for plan in plans
        if (plan["plan_type"] == "group") == (account_type == "Employer")
    ]
    preferred_plan_id = st.session_state.get("preferred_plan_id")
    default_plan_index = next(
        (index for index, plan in enumerate(account_plans) if plan["id"] == preferred_plan_id),
        0,
    )
    with st.form("signup_form"):
        name = st.text_input("Full name")
        email = st.text_input("Gmail address", placeholder="you@gmail.com")
        password = st.text_input("Password", type="password", help="Use at least 8 characters.")
        confirm_password = st.text_input("Confirm password", type="password")
        zone = st.selectbox("Primary zone", zones, format_func=lambda item: f"{item['name']}, {item['state']}")
        package = st.selectbox(
            "Preferred package",
            account_plans,
            index=default_plan_index,
            format_func=lambda item: f"{item['name']} · {money(item['price'])}",
        )
        if account_type == "Individual":
            occupation = st.selectbox("Occupation", OCCUPATIONS)
            occupation_other = st.text_input("Tell us your occupation", disabled=occupation != "Other")
            company_name = None
        else:
            occupation = None
            occupation_other = None
            company_name = st.text_input("Business name")
        submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
    if st.button("Already have an account? Sign in", key="signup_signin_link"):
        st.session_state["go_sign_in"] = True
        st.rerun()
    if not submitted:
        return
    if password != confirm_password:
        st.error("The passwords do not match.")
        return
    payload = {
        "name": name, "email": email, "password": password, "zone_id": zone["id"],
        "account_type": account_type.lower(), "occupation": occupation,
        "occupation_other": occupation_other, "company_name": company_name,
    }
    try:
        st.session_state["preferred_plan_id"] = package["id"]
        set_account_session(request_api("/auth/register", "POST", payload))
        st.session_state["account_notice"] = "Account created. Your status is Not Protected until cover is activated."
        st.rerun()
    except RuntimeError as error:
        st.error(str(error))


def sign_in() -> None:
    with st.form("signin_form"):
        email = st.text_input("Gmail address", placeholder="you@gmail.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        try:
            auth_result = request_api("/auth/login", "POST", {"email": email, "password": password})
            if auth_result["account"]["role"] == "admin":
                st.error("Admin accounts sign in through the Admin console.")
                return
            set_account_session(auth_result)
            st.rerun()
        except RuntimeError as error:
            st.error(str(error))


def public_home(zones: list[dict], plans: list[dict]) -> None:
    if st.button("Get Protection Now", type="primary", use_container_width=True):
        st.session_state["go_get_protection"] = True
        st.rerun()
    st.caption("Plan information is indicative. This site does not issue insurance cover or transfer funds.")

    st.markdown("### Haze can interrupt a workday")
    st.write("Haze can irritate the eyes and airways, make outdoor work harder, and disrupt the hours people rely on to earn. HazeShield explores a clear, pre-defined support trigger with personal or employer-sponsored cover.")
    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("Trigger threshold", f"API {150}")
    metric_b.metric("Qualifying period", "2 days")
    metric_c.metric("Indicative support", money(30), "per qualifying day")

    st.markdown("### Check the latest air-quality readings")
    zone = st.selectbox("Choose a zone", zones, format_func=lambda item: f"{item['name']} · {item['state']}", key="public_zone")
    snapshot = request_api(f"/zones/{zone['id']}/dashboard")
    latest = snapshot["latest"]
    reading = latest["api_value"] if latest else None
    label, color, background = band_for(reading)
    reading_source = latest["source"] if latest else "not available"
    if reading_source == "SIMULATED":
        reading_source = "HazeShield local data"
    reading_column, chart_column = st.columns([0.8, 1.8])
    with reading_column:
        with st.container(border=True):
            st.markdown(
                f"<span class='eyebrow'>{zone['name']} · {latest['reading_date'] if latest else 'NO READING'}</span>",
                unsafe_allow_html=True,
            )
            number_column, sticker_column = st.columns([1, 1])
            with number_column:
                st.markdown(
                    f"<div class='air-value' style='color:{color}'>{reading if reading is not None else '—'}</div>"
                    f"<span class='air-band' style='background:{background};color:{color}'>{label}</span>",
                    unsafe_allow_html=True,
                )
            sticker = air_quality_sticker(reading)
            if sticker is not None and sticker.is_file():
                with sticker_column:
                    st.image(str(sticker), width=160)
        st.caption(f"Source: {reading_source}. Readings are not official health guidance.")
    with chart_column:
        history = list(reversed(snapshot["history"]))
        if history:
            with st.container(border=True):
                st.caption("Daily API index · dashed line marks the API 150 trigger threshold")
                render_api_chart(history)

    st.markdown("### Choose a starting point")
    plan_columns = st.columns(len(plans))
    for column, plan in zip(plan_columns, plans):
        with column:
            with st.container(border=True):
                st.markdown(f"#### {plan['name']}")
                st.markdown(f"<div class='plan-price'>{money(plan['price'])}</div>", unsafe_allow_html=True)
                st.caption(plan["description"])
                account_type = "Employer" if plan["plan_type"] == "group" else "Individual"
                st.caption(f"{account_type} package")
                if st.button(f"Choose {plan['name']}", key=f"home_plan_{plan['id']}", use_container_width=True):
                    go_to_signup(plan, account_type)


def individual_account(profile: dict, zones: list[dict], plans: list[dict], token: str) -> None:
    dashboard = request_api(f"/users/{profile['id']}/dashboard", token=token)
    individual_plans = [plan for plan in plans if plan["plan_type"] != "group"]
    zone_by_id = {zone["id"]: zone for zone in zones}
    active_policy = next((policy for policy in dashboard["policies"] if policy_is_current(policy)), None)
    zone_id = active_policy["zone_id"] if active_policy else profile["zone_id"]
    zone = zone_by_id[zone_id]
    history = request_api(f"/zones/{zone_id}/dashboard")["history"]
    if active_policy and active_policy.get("covered_by"):
        st.info(f"Your cover is sponsored by {active_policy['covered_by']}.")
    st.metric("Protection status", dashboard["protection_status"], "Active cover" if active_policy else "Choose a plan to activate cover")
    if active_policy:
        st.markdown(f"**Current plan:** {active_policy['plan_name']} · through {active_policy['end_date']}")
    st.markdown(f"**Occupation:** {profile.get('occupation_other') or profile.get('occupation') or 'Not set'} · **Primary zone:** {zone['name']}")
    if history:
        st.markdown("### Zone trend")
        with st.container(border=True):
            st.caption("Daily API index · dashed line marks the API 150 trigger threshold")
            render_api_chart(list(reversed(history)), height=220)

    st.markdown("### Personal plans")
    preferred_plan_id = st.session_state.pop("preferred_plan_id", None)
    default_plan_index = next(
        (index for index, plan in enumerate(individual_plans) if plan["id"] == preferred_plan_id),
        0,
    )
    with st.form("individual_purchase"):
        plan = st.selectbox(
            "Choose a plan",
            individual_plans,
            index=default_plan_index,
            format_func=lambda item: f"{item['name']} · {money(item['price'])}",
        )
        covered_zone = st.selectbox("Covered zone", zones, index=next(
            (index for index, item in enumerate(zones) if item["id"] == zone_id), 0
        ), format_func=lambda item: f"{item['name']}, {item['state']}")
        wallet = st.selectbox("Payout wallet", ["Touch n Go", "GrabPay", "Boost"])
        submitted = st.form_submit_button("Select plan", type="primary")
    if submitted:
        try:
            request_api("/policies", "POST", {
                "plan_id": plan["id"], "zone_id": covered_zone["id"], "wallet": wallet,
            }, token=token)
            st.success("Plan selection recorded. Refreshing your account.")
            st.rerun()
        except RuntimeError as error:
            st.error(str(error))

    st.markdown("### Payment history")
    if dashboard["payments"]:
        st.dataframe(dashboard["payments"], hide_index=True, use_container_width=True)
    else:
        st.info("No payments yet. Your account remains Not Protected until a plan is activated.")
    st.markdown("### Payout history")
    if dashboard["payouts"]:
        st.dataframe(dashboard["payouts"], hide_index=True, use_container_width=True)
    else:
        st.caption("No payouts recorded.")


def employer_account(profile: dict, zones: list[dict], plans: list[dict], token: str) -> None:
    dashboard = request_api(f"/users/{profile['id']}/dashboard", token=token)
    members = request_api("/employer/members", token=token)
    st.markdown(f"### {profile['company_name'] or profile['name']}")
    current_group = next((policy for policy in dashboard["policies"] if policy["sponsor_policy_id"] is None and policy["status"] == "active"), None)
    first, second, third = st.columns(3)
    first.metric("Group cover", "Active" if current_group else "Not active")
    second.metric("Team members", len([member for member in members if member["status"] == "active"]))
    third.metric("Covered members", len([member for member in members if member["protection_status"] == "Protected"]))

    st.markdown("### Add an existing individual account")
    st.caption("The person must already have registered an individual account with this Gmail address.")
    with st.form("add_employer_member"):
        member_email = st.text_input("Member Gmail address", placeholder="worker@gmail.com")
        submitted = st.form_submit_button("Add to team", type="primary")
    if submitted:
        try:
            request_api("/employer/members", "POST", {"email": member_email}, token=token)
            st.success("Existing account added to your team.")
            st.rerun()
        except RuntimeError as error:
            st.error(str(error))

    st.markdown("### Team roster")
    if members:
        st.dataframe([
            {"Name": member["name"], "Gmail": member["email"], "Occupation": member["occupation"],
             "Membership": member["status"], "Protection": member["protection_status"]}
            for member in members
        ], hide_index=True, use_container_width=True)
        removable = [member for member in members if member["status"] == "active"]
        if removable:
            member = st.selectbox("Remove a team member", removable, format_func=lambda item: item["name"])
            if st.button("Remove member", type="secondary"):
                try:
                    request_api(f"/employer/members/{member['id']}", "DELETE", token=token)
                    st.success("Member removed; employer-sponsored cover has been cancelled.")
                    st.rerun()
                except RuntimeError as error:
                    st.error(str(error))
    else:
        st.info("Your roster is empty. Add an existing individual account by Gmail address.")

    st.markdown("### Employer group plan")
    group_plans = [plan for plan in plans if plan["plan_type"] == "group"]
    if group_plans:
        group_plan = group_plans[0]
        st.markdown(f"**{group_plan['name']}** · {money(group_plan['price'])} · {group_plan['description']}")
        zone = st.selectbox("Work zone", zones, format_func=lambda item: f"{item['name']}, {item['state']}", key="employer_zone")
        if st.button("Select group plan", type="primary", disabled=not members):
            try:
                request_api("/policies", "POST", {
                    "plan_id": group_plan["id"], "zone_id": zone["id"], "wallet": "Touch n Go",
                }, token=token)
                st.success("Group plan selection recorded. Refreshing your account.")
                st.rerun()
            except RuntimeError as error:
                st.error(str(error))
    if dashboard["payments"]:
        st.markdown("### Employer payment history")
        st.dataframe(dashboard["payments"], hide_index=True, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="HazeShield · Protection for outdoor work", page_icon="🌿", layout="wide")
    render_styles(st)
    try:
        zones = request_api("/zones")
        plans = request_api("/plans")
    except RuntimeError as error:
        st.error(f"Backend API unavailable. Start `python -m uvicorn backend.main:api`. {error}")
        st.stop()

    token = st.session_state.get("access_token")
    account = None
    if token:
        try:
            account = request_api("/auth/me", token=token)
            st.session_state["account"] = account
        except RuntimeError:
            st.session_state.pop("access_token", None)
            st.session_state.pop("account", None)
            token = None

    if account is None:
        if st.session_state.pop("go_get_protection", False):
            st.session_state["public_navigation"] = "Get protection"
        if st.session_state.pop("go_sign_in", False):
            st.session_state["public_navigation"] = "Sign in"
        render_brand()
        page = st.radio(
            "Navigate",
            ["Home", "Plans", "Sign in", "Get protection"],
            horizontal=True,
            key="public_navigation",
            label_visibility="collapsed",
            width="stretch",
        )
        if page == "Home":
            st.markdown(
                f"<section class='public-hero'><div class='eyebrow'>HazeShield · MALAYSIA · {date.today():%d %b %Y}</div>"
                "<h1>When the air turns hazy,<br>your income needs a backup.</h1>"
                "<p>Browse practical personal plans, understand the haze trigger, and find protection for outdoor work.</p></section>",
                unsafe_allow_html=True,
            )
            public_home(zones, plans)
        elif page == "Plans":
            st.markdown("<div class='hero'><div class='eyebrow'>PROTECTION PLANS</div><h1>Plans for uncertain workdays</h1><p>Choose personal cover or a group package for your team.</p></div>", unsafe_allow_html=True)
            st.markdown("### Choose a protection package")
            individual_plans = [plan for plan in plans if plan["plan_type"] != "group"]
            all_plans = individual_plans + [plan for plan in plans if plan["plan_type"] == "group"]
            columns = st.columns(len(all_plans))
            for column, plan in zip(columns, all_plans):
                with column:
                    with st.container(border=True):
                        st.markdown(f"#### {plan['name']}")
                        st.markdown(f"<div class='plan-price'>{money(plan['price'])}</div>", unsafe_allow_html=True)
                        st.write(plan["description"])
                        account_type = "Employer" if plan["plan_type"] == "group" else "Individual"
                        st.caption(f"{account_type} package")
                        if st.button(f"Choose {plan['name']}", key=f"plans_plan_{plan['id']}", use_container_width=True):
                            go_to_signup(plan, account_type)
        elif page == "Sign in":
            st.markdown("<div class='hero'><div class='eyebrow'>ACCOUNT</div><h1>Welcome back</h1><p>Sign in using your Gmail address and password.</p></div>", unsafe_allow_html=True)
            sign_in()
        else:
            st.markdown("<div class='hero'><div class='eyebrow'>GET PROTECTION</div><h1>Create your account</h1><p>Choose personal cover or set up an employer account for your team.</p></div>", unsafe_allow_html=True)
            sign_up(zones, plans)
            st.caption("Creating an account does not activate cover. This site does not issue coverage or transfer funds.")
        return

    render_brand()
    st.markdown(
        f"<div class='hero'><div class='eyebrow'>{account['role'].upper()} ACCOUNT</div>"
        f"<h1>Welcome, {account['name']}</h1><p>Manage your HazeShield account and coverage.</p></div>",
        unsafe_allow_html=True,
    )
    if st.button("Sign out"):
        st.session_state.pop("access_token", None)
        st.session_state.pop("account", None)
        st.rerun()
    try:
        if account["role"] == "customer":
            individual_account(account, zones, plans, token)
        elif account["role"] == "employer":
            employer_account(account, zones, plans, token)
        else:
            st.info("Use the separate Admin console to manage the platform.")
    except RuntimeError as error:
        st.error(str(error))


if __name__ == "__main__":
    main()

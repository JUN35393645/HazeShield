from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import streamlit as st

from app import money, render_styles, request_api


APP_DIRECTORY = Path(__file__).resolve().parent


def render_bar_chart(
    rows: list[dict[str, str | int]],
    category: str,
    value: str,
    split_by: str | None = None,
) -> None:
    if not rows:
        st.info("Not enough account data to display this chart yet.")
        return
    encoding: dict[str, object] = {
        "x": {
            "field": category,
            "type": "nominal",
            "sort": "-y",
            "axis": {"title": None, "labelAngle": -25},
        },
        "y": {
            "field": value,
            "type": "quantitative",
            "axis": {"title": None, "gridColor": "#e7e9df"},
        },
    }
    if split_by:
        encoding["color"] = {
            "field": split_by,
            "type": "nominal",
            "scale": {"range": ["#176b52", "#ee7658"]},
            "legend": {"title": None},
        }
    st.vega_lite_chart(
        spec={
            "data": {"values": rows},
            "mark": {
                "type": "bar",
                "color": "#176b52",
                "cornerRadiusTopLeft": 5,
                "cornerRadiusTopRight": 5,
            },
            "encoding": encoding,
            "config": {
                "view": {"stroke": None},
                "axis": {"labelColor": "#66746d", "titleColor": "#66746d"},
            },
        },
        use_container_width=True,
    )


def main() -> None:
    st.set_page_config(page_title="HazeShield Admin", page_icon="🌿", layout="wide")
    render_styles(st)
    with st.container(key="brand_logo"):
        st.image(str(APP_DIRECTORY / "HazeShield Logo.png"), width=360)
    token = st.session_state.get("admin_access_token")
    account = None
    if token:
        try:
            account = request_api("/auth/me", token=token)
        except RuntimeError:
            st.session_state.pop("admin_access_token", None)
            token = None
    if account is None:
        st.markdown(
            f"<div class='hero'><div class='eyebrow'>ADMIN · {date.today():%d %b %Y}</div>"
            "<h1>Operations sign in</h1><p>Administrative access is separate from customer accounts.</p></div>",
            unsafe_allow_html=True,
        )
        with st.form("admin_signin"):
            email = st.text_input("Admin Gmail address")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            try:
                login = request_api("/auth/login", "POST", {"email": email, "password": password})
                if login["account"]["role"] != "admin":
                    st.error("This account does not have admin access.")
                    st.stop()
                st.session_state["admin_access_token"] = login["access_token"]
                st.rerun()
            except RuntimeError as error:
                st.error(str(error))
        st.caption("Administrative access is restricted to authorized operators.")
        st.stop()
    if account["role"] != "admin":
        st.error("Admin access required.")
        st.session_state.pop("admin_access_token", None)
        st.stop()
    try:
        config = request_api("/config")
        zones = request_api("/zones")
    except RuntimeError as error:
        st.error(f"Backend API is unavailable. Start it with `python -m uvicorn backend.main:api`. {error}")
        st.stop()
    with st.sidebar:
        st.markdown("### HazeShield Admin")
        st.caption(f"Signed in as {account['email']}")
        page = st.radio("Management", ["Overview", "Accounts and policies", "Trigger tools", "Audit log"])
        if st.button("Sign out"):
            st.session_state.pop("admin_access_token", None)
            st.rerun()
        st.caption("Operations console")

    st.markdown(
        f"<div class='hero'><div class='eyebrow'>ADMIN CONSOLE · {date.today():%d %b %Y}</div>"
        "<h1>HazeShield operations</h1><p>Review accounts, policies, zone readings, and system activity.</p></div>",
        unsafe_allow_html=True,
    )
    notice = st.session_state.pop("admin_notice", None)
    if notice:
        st.success(notice)

    if page == "Overview":
        overview = request_api("/admin/overview", token=token)
        first, second, third, fourth = st.columns(4)
        first.metric("Active policies", overview["active_policies"])
        second.metric("Premium records", money(overview["paid_premiums"]))
        third.metric("Payout records", money(overview["paid_payouts"]))
        fourth.metric("Trigger events", overview["trigger_events"])
        st.caption("Premium and payout amounts shown here are records; no funds are transferred.")

        profiles = []
        for role in ("customer", "employer"):
            profiles.extend(request_api(f"/users?role={role}", token=token))
        account_zone_counts: Counter[str] = Counter()
        account_type_counts: Counter[str] = Counter()
        policy_by_id: dict[int, dict[str, str]] = {}
        for profile in profiles:
            account_type_counts[profile["role"].title()] += 1
            zone_name = next(
                (zone["name"] for zone in zones if zone["id"] == profile["zone_id"]),
                "Unknown",
            )
            if profile["role"] == "customer":
                account_zone_counts[zone_name] += 1
            dashboard = request_api(f"/users/{profile['id']}/dashboard", token=token)
            for policy in dashboard["policies"]:
                policy_by_id[policy["id"]] = {
                    "Plan": policy["plan_name"],
                    "Status": policy["status"].title(),
                }

        charts = st.columns(2)
        with charts[0]:
            st.markdown("### Individual accounts by zone")
            render_bar_chart(
                [{"Zone": zone, "Customers": count} for zone, count in account_zone_counts.items()],
                "Zone",
                "Customers",
            )
        with charts[1]:
            st.markdown("### Account mix")
            render_bar_chart(
                [{"Account type": role, "Accounts": count} for role, count in account_type_counts.items()],
                "Account type",
                "Accounts",
            )
        policy_counts: Counter[tuple[str, str]] = Counter(
            (policy["Plan"], policy["Status"]) for policy in policy_by_id.values()
        )
        if policy_counts:
            st.markdown("### Policy records by plan and status")
            render_bar_chart(
                [
                    {"Plan": plan, "Status": status, "Policies": count}
                    for (plan, status), count in policy_counts.items()
                ],
                "Plan",
                "Policies",
                split_by="Status",
            )

        st.markdown("### Zone status")
        rows = []
        for zone in zones:
            latest = request_api(f"/zones/{zone['id']}/dashboard")["latest"]
            source = latest["source"] if latest else "No reading"
            if source in {"SIMULATED", "MANUAL"}:
                source = "HazeShield local data"
            rows.append({
                "Zone": zone["name"], "State": zone["state"],
                "Index": latest["api_value"] if latest else None,
                "Reading date": latest["reading_date"] if latest else "—",
                "Source": source,
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)
        feed = config["feed"]
        st.info(f"Reading source: {feed['source']} · external feed configured: {feed['configured']}")
        if feed["last_error"]:
            st.warning(f"Latest feed error: {feed['last_error']}")
        st.caption("Imported feed readings are for display only until their source and index scale are verified.")

    elif page == "Accounts and policies":
        st.markdown("### Account directory")
        profiles = []
        for role in ("customer", "employer"):
            profiles.extend(request_api(f"/users?role={role}", token=token))
        rows = []
        dashboards = {}
        for profile in profiles:
            dashboard = request_api(f"/users/{profile['id']}/dashboard", token=token)
            dashboards[profile["id"]] = dashboard
            active_policies = [
                item for item in dashboard["policies"]
                if item["status"] == "active" and item["start_date"] <= date.today().isoformat() <= item["end_date"]
            ]
            rows.append({
                "Name": profile["name"], "Type": profile["role"].title(),
                "Zone": next((zone["name"] for zone in zones if zone["id"] == profile["zone_id"]), "—"),
                "Protection": dashboard["protection_status"],
                "Active policies": len(active_policies),
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)

        if profiles:
            selected_profile = st.selectbox(
                "Review account", profiles,
                format_func=lambda item: f"{item['name']} ({item['role']})",
            )
            policies = dashboards[selected_profile["id"]]["policies"]
            if policies:
                policy = st.selectbox(
                    "Policy", policies,
                    format_func=lambda item: f"#{item['id']} · {item['plan_name']} · {item['status']}",
                )
                target_status = st.selectbox(
                    "Set policy status", ["active", "cancelled"],
                    index=0 if policy["status"] == "active" else 1,
                )
                if st.button("Save policy status", type="primary"):
                    try:
                        request_api(f"/admin/policies/{policy['id']}", "PATCH", {
                            "status": target_status,
                        }, token=token)
                        st.success("Policy status updated and recorded in the audit log.")
                    except RuntimeError as error:
                        st.error(str(error))
            else:
                st.info("This account has no policy to manage.")

            st.divider()
            st.markdown("### Delete an account")
            st.caption(
                "Personal details and sign-in access will be removed. Any active policies will be cancelled; "
                "payment and payout history remains with identifying wallet details anonymized."
            )
            account_to_delete = st.selectbox(
                "Account to delete",
                profiles,
                format_func=lambda item: f"{item['name']} ({item['role']})",
                key="admin_delete_account_choice",
            )
            confirm_delete = st.checkbox(
                f"Confirm deletion of {account_to_delete['name']}",
                key=f"confirm_delete_account_{account_to_delete['id']}",
            )
            if st.button("Delete account", disabled=not confirm_delete, type="secondary"):
                try:
                    request_api(
                        f"/admin/users/{account_to_delete['id']}",
                        "DELETE",
                        token=token,
                    )
                    st.session_state["admin_notice"] = (
                        f"{account_to_delete['name']}'s personal details were removed. "
                        "Policy and payment/payout history was retained with policies cancelled."
                    )
                    st.rerun()
                except RuntimeError as error:
                    st.error(str(error))

    elif page == "Trigger tools":
        st.markdown("### Record a manual reading")
        st.info(
            "To test a simulated payout, choose Klang Valley and enter an API value above 150 for today. "
            "Submit again for tomorrow with a value above 150. The second reading should create payout "
            "records for eligible active customer policies in that zone."
        )
        st.warning("Manually entered readings are evaluated against trigger rules. Payout records do not transfer funds.")
        with st.form("admin_simulation"):
            zone = st.selectbox("Zone", zones, format_func=lambda item: item["name"])
            reading_day = st.date_input("Reading date", value=date.today())
            value = st.number_input("API value", min_value=0, max_value=1000, value=160, step=1)
            submitted = st.form_submit_button("Store reading and evaluate", type="primary")
        if submitted:
            try:
                result = request_api("/readings/simulate", "POST", {
                    "zone_id": zone["id"], "reading_date": reading_day.isoformat(),
                    "api_value": int(value),
                }, token=token)
                if result["missing"]:
                    st.warning("A neighboring day's reading is missing. No trigger was created.")
                elif result["triggered"]:
                    st.success(f"Trigger event #{result['event_id']} confirmed; {result['payouts']} payout record(s) created.")
                else:
                    st.info("Reading stored. The qualifying-day threshold has not been met yet.")
            except RuntimeError as error:
                st.error(str(error))

    else:
        st.markdown("### Audit log")
        logs = request_api("/admin/audit", token=token)
        if logs:
            st.dataframe(logs, hide_index=True, use_container_width=True)
        else:
            st.info("No admin actions have been recorded.")
        st.divider()
        st.markdown("#### Reset database")
        confirmed = st.checkbox("I understand that this clears activity and restores the initial data.")
        if st.button("Reset data", disabled=not confirmed, type="secondary"):
            try:
                request_api("/admin/reset", "POST", token=token)
                st.success("Data reset. Refresh the page to reload the initial state.")
            except RuntimeError as error:
                st.error(str(error))


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import date

import streamlit as st

from app import money, render_styles, request_api


def main() -> None:
    st.set_page_config(page_title="HazeShield Admin", page_icon="🌿", layout="wide")
    render_styles(st)
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
        st.caption("Prototype console. Sign-in does not make this demo suitable for public deployment.")
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
        page = st.radio("Management", ["Overview", "Accounts and policies", "Trigger simulation", "Audit log"])
        if st.button("Sign out"):
            st.session_state.pop("admin_access_token", None)
            st.rerun()
        st.caption("Demo management console")

    st.markdown(
        f"<div class='hero'><div class='eyebrow'>ADMIN CONSOLE · {date.today():%d %b %Y}</div>"
        "<h1>HazeShield operations</h1><p>Review demo accounts, policies, zone readings, and system activity.</p></div>",
        unsafe_allow_html=True,
    )

    if page == "Overview":
        overview = request_api("/admin/overview", token=token)
        first, second, third, fourth = st.columns(4)
        first.metric("Active policies", overview["active_policies"])
        second.metric("Demo premiums", money(overview["paid_premiums"]))
        third.metric("Simulated payouts", money(overview["paid_payouts"]))
        fourth.metric("Trigger events", overview["trigger_events"])
        st.markdown("### Zone status")
        rows = []
        for zone in zones:
            latest = request_api(f"/zones/{zone['id']}/dashboard")["latest"]
            rows.append({
                "Zone": zone["name"], "State": zone["state"],
                "Index": latest["api_value"] if latest else None,
                "Reading date": latest["reading_date"] if latest else "—",
                "Source": latest["source"] if latest else "No reading",
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)
        feed = config["feed"]
        st.info(f"Feed: {feed['source']} · configured: {feed['configured']} · mode: {config['data_mode']}")
        if feed["last_error"]:
            st.warning(f"Latest feed error: {feed['last_error']}")
        st.caption("Imported live-feed readings remain display-only until their source and index scale are approved.")

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

    elif page == "Trigger simulation":
        st.markdown("### Inject a simulated reading")
        st.warning("This writes demo data and can create simulated trigger events and payouts.")
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
                    st.success(f"Trigger event #{result['event_id']} confirmed; {result['payouts']} new demo payout(s).")
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
        st.markdown("#### Reset demo database")
        confirmed = st.checkbox("I understand that this clears demo activity and reseeds the database.")
        if st.button("Reset demo data", disabled=not confirmed, type="secondary"):
            try:
                request_api("/admin/reset", "POST", token=token)
                st.success("Demo data reset. Refresh the page to reload the seeded state.")
            except RuntimeError as error:
                st.error(str(error))


if __name__ == "__main__":
    main()

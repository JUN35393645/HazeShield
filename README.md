# HazeShield

A prototype for parametric haze cover for Malaysian outdoor workers. The public Customer site and separate Admin console communicate with a FastAPI backend. Individual and Employer accounts use Gmail-format addresses and passwords; employers can roster only existing individual accounts.

## Run locally

Open three PowerShell terminals in the project folder.

In terminal 1, start the backend:

```powershell
python -m pip install -r backend/requirements.txt
$env:HAZESHIELD_DATABASE_PATH = (Join-Path (Get-Location) "hazeshield.db")
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$env:HAZESHIELD_SESSION_SECRET = [Convert]::ToBase64String($bytes)
python -m uvicorn backend.main:api --reload
```

In terminal 2, start the public site:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run customer_app.py --server.address 127.0.0.1 --server.port 8502
```

In terminal 3, start the Admin console:

```powershell
python -m streamlit run admin_app.py --server.address 127.0.0.1 --server.port 8503
```

The public site is at `http://127.0.0.1:8502`; Admin is at `http://127.0.0.1:8503`; the backend API docs are at `http://127.0.0.1:8000/docs`. Keep all services on localhost.

## Demo accounts

The local demo database is migrated in place and seeded with existing accounts. Example sign-ins:

| Account | Gmail | Password |
| --- | --- | --- |
| Individual | `amina.demo@gmail.com` | `HazeDemo123!` |
| Individual, starts Not Protected | `new.customer.demo@gmail.com` | `HazeDemo123!` |
| Employer | `employer.demo@gmail.com` | `HazeDemo123!` |
| Admin | `admin.demo@gmail.com` | `AdminDemo123!` |

Change these before sharing the demo. Passwords are stored as salted PBKDF2 hashes. Signup requires a Gmail-format address, but does not verify ownership of the address or send email.

## Account flows

Visitors can browse plan prices and simulated zone charts before signing up. Individual signup collects name, Gmail, password, primary zone, and a gig-work occupation (or “Other”). New accounts begin **Not Protected**; activating an individual plan records a simulated payment and displays **Protected** while the policy is active.

Employer signup collects a business name. An employer adds a team member using the Gmail address on an existing individual account; unknown addresses are rejected. The demo group plan supports up to 20 people. When purchased, it creates member-level sponsored policies; removing a member cancels that employer-sponsored cover. A member’s own individual policy remains separate.

The Admin console reviews accounts and policies, changes policy status with an audit entry, simulates readings, and resets the demo database. Demo passwords are re-seeded after reset.

To demonstrate a simulated trigger, use Admin → Trigger simulation. Inject API 160 for a date with a reading the previous day, then API 165 the following day. Eligible policies receive simulated RM30 payouts, subject to the seasonal cap.

Run tests from the project folder with `python -m unittest discover -s . -v`.

## Deploy a demo on Render

1. Push this project to a GitHub repository. Confirm that `render.yaml` is in the repository root and that `.gitignore` excludes your local database and secrets.
2. In Render, create a **Blueprint** and connect the GitHub repository. Render will read `render.yaml` and configure the API, Customer site, and Admin console.
3. Review the plans before confirming. All three services use the Free plan. The API database is stored on temporary disk, so accounts created during a demo can disappear when Render restarts or replaces the API instance. Seeded demo accounts are recreated automatically.
4. Wait for all three services to finish deploying. Open the Customer and Admin service URLs from the Render dashboard. The API URL is also available there; its health check is `/api/v1/health` and its API docs are `/docs`.
5. Sign in with the demo accounts below. Change demo passwords before sharing the site.

After changing code, commit and push it to GitHub. Render can automatically redeploy the changed services from that commit. Check each service's deploy/runtime logs if a build or startup fails. Keep the API and Admin URLs private while this prototype uses demo authentication. Render Free services may sleep while idle and take a short time to wake.

## Live readings

The backend can poll a normalized JSON feed. Set `HAZESHIELD_FEED_URL`, optional `HAZESHIELD_FEED_TOKEN`, `HAZESHIELD_FEED_SOURCE`, and optional `HAZESHIELD_FEED_POLL_SECONDS` in the backend terminal before startup. The feed response must be a JSON array or an object with a `readings` array. Each record uses an exact HazeShield zone name:

```json
{"zone":"Klang Valley","reading_date":"2026-10-03","api_value":163}
```

This is an adapter contract, not a direct DOE APIMS integration. A stable public APIMS endpoint and response schema could not be verified. Imported feed readings remain display-only and never trigger payouts until the source and index scale are verified.

## Prototype limitations

- This is demo authentication, not a production identity system: Gmail ownership is not verified, and there is no email recovery, MFA, or rate limiting.
- Payments, underwriting, identity checks, notifications, and transfers are simulated. Do not enter real personal or payment data.
- Keep the API on localhost; the Admin console and session system are not security-reviewed for public deployment.
- This prototype is not an insurance offer, and demo readings are not official health guidance.
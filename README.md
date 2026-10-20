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

The Admin console reviews accounts and policies, changes policy status with an audit entry, simulates readings, and resets the demo database. Deleting a customer or employer account removes its personal details and sign-in access, cancels its policies, and retains payment/payout history with wallet details anonymized. Demo passwords are re-seeded after reset.

To test a simulated payout, use Admin → Trigger tools and choose **Klang Valley** (it has an active customer policy). Record API 160 for today, then record API 165 for tomorrow. The second reading should create payout records for eligible policies, subject to the seasonal cap. No money is transferred.

Run tests from the project folder with `python -m unittest discover -s . -v`.

## Deploy a demo on Render

> **Legacy deployment:** This section deploys the existing Streamlit/FastAPI prototype. It is separate from the Next.js + Supabase web app setup below.

1. Push this project to a GitHub repository. Confirm that `render.yaml` is in the repository root and that `.gitignore` excludes your local database and secrets.
2. In Render, create a **Blueprint** and connect the GitHub repository. Render will read `render.yaml` and configure the API, Customer site, and Admin console. The frontends use the API service's public hostname over HTTPS; this is required because Free web services cannot receive private-network requests.
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

## Web app: beginner setup for Vercel + Supabase

This section walks through the **new web app**, which lives in `web\`. It is separate from the original Python/Streamlit prototype: this web version uses Next.js for the website and Supabase for sign-in and its PostgreSQL database. The original Python files are left in place.

In simple terms:

- **GitHub** stores the project code and gives Vercel something to deploy.
- **Vercel** builds and hosts the website.
- **Supabase** stores app data, manages user sign-in, and enforces database access rules.
- A **PWA** (Progressive Web App) lets someone add the website to their phone's home screen. They still visit a website; this does not publish a native app to an app store.

You will need accounts for GitHub, Vercel, and Supabase, plus **Node.js 20.9 or later** installed on your computer. You do not need to install PostgreSQL separately. Free-plan details and limits can change; check the providers' current plan pages before depending on them.

### Part A — Create and prepare the Supabase project

1. Go to [supabase.com](https://supabase.com/), sign in, and choose **New project**. Create or choose an organization, give the project a name such as `hazeshield-demo`, choose a strong database password, and select a region close to your expected users (for example, Singapore if available). Save the database password somewhere private. Wait for the project to finish provisioning.
2. Open the project's **SQL Editor** from the left-hand menu, choose **New query**, and give the query a name such as `HazeShield web schema`.
3. On your computer, open this repository's file `supabase\migrations\202610130001_hazeshield_web.sql` in a text editor. Select and copy the **entire** file. Paste it into the Supabase SQL Editor, then choose **Run**. Wait for it to finish. If the editor shows an error, stop here and read the first error; do not repeatedly run parts of the script at random.
4. Check the result in Supabase **Table Editor**. You should see tables including `zones`, `plans`, `profiles`, `policies`, and `readings`. The migration creates these tables, example zones/plans, synthetic readings, security policies, and database functions. It does not import the old SQLite database.
5. Apply the manual trigger simulator update: open **SQL Editor → New query**, copy the entire contents of `supabase\migrations\202610200001_manual_trigger_payouts_year_round.sql` into the editor, and choose **Run**. This allows admin-entered simulator readings to create test payouts at any time of year. For an existing Supabase project, run this update migration without rerunning the initial schema migration.
6. Open **Project Settings → API** (the exact menu label may change). Copy:
   - **Project URL** — looks like `https://abcdefgh.supabase.co`.
   - **Publishable key** or legacy **anon/public key** — the web app uses this as `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
   - **Secret key** or legacy **service_role key** — the web app uses this as `SUPABASE_SERVICE_ROLE_KEY`. This key has powerful administrative access. Treat it like a password: use it only in the server-side environment variable below, never put it in page code, a screenshot, GitHub, or a variable starting `NEXT_PUBLIC_`.

   The public/anon key is designed to be used by a browser when Row Level Security (RLS) is configured; the private service-role key is not. If Supabase shows a newer "publishable/secret" pair, use the publishable key for the anon variable and the secret key for the service-role variable.
7. Open **Authentication → Providers → Email** (or the equivalent Email settings), leave email/password sign-in enabled, and find **Confirm email**. Turn it **off** for this classroom demo, then save. With confirmation off, users can sign in immediately after signup and you do not need to configure email delivery or callback URLs. This also means the app does not verify that a person owns the Gmail address they enter. Do not use this setting for a real service or real customer data.

### Part B — Start it on your own computer

1. Install Node.js **20.9 or later** from [nodejs.org](https://nodejs.org/) if it is not already installed. Close and reopen PowerShell after installing. Check that the commands are available:

   ```powershell
   node --version
   npm.cmd --version
   ```

   If the first command says `v20.9.0` or a later version, that is suitable. On Windows, use `npm.cmd` if PowerShell blocks the `npm` script.

2. In PowerShell, move to the project folder. Replace the example path with the actual folder if yours is different:

   ```powershell
   Set-Location 'C:\Users\hp\OneDrive\Desktop\HazeShield-App'
   Copy-Item web\.env.example web\.env.local
   notepad web\.env.local
   ```

   If Notepad asks whether to create the file, choose **Yes**. The file contains three lines. Replace the example values with the values you copied from Supabase:

   ```text
   NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your-publishable-or-anon-key
   SUPABASE_SERVICE_ROLE_KEY=your-secret-or-service-role-key
   ```

   Do not add quotation marks around the values. Save the file and close Notepad. The project ignores `web\.env.local` so these local secrets should not be committed to Git. There is no Site URL or callback URL to configure for this simplified demo.

3. Install the web app's packages and start the development website:

   ```powershell
   Set-Location 'C:\Users\hp\OneDrive\Desktop\HazeShield-App\web'
   npm.cmd install
   npm.cmd run dev
   ```

   Keep this PowerShell window open while using the site. Open `http://localhost:3000` in your browser. To stop it later, return to PowerShell and press **Ctrl+C**.

4. Try creating an individual account with a Gmail-format address and a password. With **Confirm email** turned off, signup should sign you in and open the dashboard immediately. To try the employer flow, also create a separate individual account first; the employer can then add that existing account by its Gmail address.
5. For a basic code check, open a **second** PowerShell window and run:

   ```powershell
   Set-Location 'C:\Users\hp\OneDrive\Desktop\HazeShield-App\web'
   npm.cmd run typecheck
   npm.cmd run build
   ```

   Both commands should finish without errors. If the local site says Supabase settings are missing, double-check the spelling of the three `.env.local` names and restart `npm.cmd run dev`.

### Part C — Give one trusted account admin access

The app deliberately does not let public visitors choose the admin role during signup. First create a normal account using the admin's own email address and sign in once so Supabase creates its profile row. Then:

1. In Supabase, open **SQL Editor → New query**.
2. Run the following, replacing the example address with the exact email used for that account:

   ```sql
   update public.profiles
   set role = 'admin'
   where email = 'trusted.operator@gmail.com'
     and role <> 'admin';
   ```

3. Sign out of the website and sign back in (or refresh the session). Open `/admin` on the local website. A non-admin account should not be able to access the admin console.

Only do this for the account you will use as the demo operator. Never share SQL editor access, your database password, or the Supabase service-role key with ordinary app users.

### Part D — Put the code on GitHub and deploy with Vercel

1. Make sure the project is in a GitHub repository that you control. In PowerShell, from the repository root, inspect what will be uploaded:

   ```powershell
   Set-Location 'C:\Users\hp\OneDrive\Desktop\HazeShield-App'
   git status --short
   git remote -v
   ```

   The file list should **not** contain `web\.env.local`, `web\node_modules`, `web\.next`, or the local `hazeshield.db`. If `.env.local` ever appears as a tracked file, stop and remove it from Git before pushing; do not post its contents. `git remote -v` should show a GitHub repository address. If it shows nothing, create an **empty** repository on GitHub (do not initialize it with a README), then connect it from PowerShell using the repository URL GitHub displays:

   ```powershell
   git remote add origin https://github.com/YOUR-GITHUB-NAME/YOUR-REPOSITORY.git
   ```

   Replace both example parts; do not type the angle brackets. To upload the web app and guide, stage the intended files, review them, commit, and push:

   ```powershell
   git add README.md .gitignore supabase web
   git status --short
   git commit -m "Add HazeShield web app"
   git push -u origin HEAD
   ```

   If Git says there is nothing to commit, it may already be committed. If pushing asks you to authenticate, complete GitHub's sign-in flow. If you already have other changes you want to keep separate, do not use `git add .`; stage only the files for this work as shown above. Never upload passwords, `.env.local`, or database files.

2. Sign in at [vercel.com](https://vercel.com/) using GitHub. Choose **Add New → Project**, find this repository, and select **Import**.
3. On the project setup screen:
   - Set **Root Directory** to `web` (use **Edit** if it initially shows the repository root).
   - Let Vercel detect **Next.js** and keep the normal build settings.
   - Add the environment variables below in **Environment Variables**. If it is easier, you can add them after importing from **Project → Settings → Environment Variables**.

   | Name | Value |
   | --- | --- |
   | `NEXT_PUBLIC_SUPABASE_URL` | The Supabase Project URL |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | The Supabase publishable/anon key |
   | `SUPABASE_SERVICE_ROLE_KEY` | Supabase's secret/service-role key; server-side only |

   Apply the variables to **Production**, and also to **Preview** if you want preview deployments to connect to the demo database.
4. Choose **Deploy** and wait for Vercel to report that the deployment is ready. If it fails, open the failed deployment and read the **Build Logs**. A missing environment variable or an incorrect Root Directory is a common cause.
5. Open the production address and test the flows below. When you push future changes to the connected GitHub branch, Vercel normally creates a new deployment automatically. Environment-variable changes also require a new deployment to take effect.

### Part E — Test the main flows before sharing

Use separate accounts and a private/incognito browser window where helpful:

1. **Visitor:** home page loads, plans appear, zone selector changes the reading.
2. **Individual:** sign up, check that the initial status is **Not Protected**, select a plan, and check policy/payment history.
3. **Employer:** sign up, add the existing individual using their Gmail address, select group cover, and check the roster. Try removing a member and verify the sponsored cover is cancelled.
4. **Admin:** promote a trusted account as in Part C. Change a policy status, record manual readings on two consecutive dates in the same zone, review the audit log, and only use reset after reading the warning. Both values must be above API 150. The manual simulator works year-round; the customer's policy must cover the reading dates, and the rule caps records at five payout days per policy per year.
5. **Access checks:** while signed in as a customer, try `/admin`; it should send you away. Verify customers cannot see each other's private account records. Review the Supabase RLS policies in the migration before using any real data.

For errors after deployment, inspect **Vercel → Project → Deployments → latest deployment → Build Logs** for build-time problems. For runtime/server action errors, inspect the Vercel project's **Logs**. In Supabase, check **Logs → Auth/Postgres** (menu names can vary) for sign-in or database problems. Do not paste secret keys into support requests or screenshots.

### Part F — Install the website on a phone

Use the deployed **HTTPS** address on the phone (not `localhost`, which means the phone itself):

- **Android:** open the link in Chrome. Use the browser prompt if offered, or open Chrome's menu and choose **Install app** or **Add to Home screen**.
- **iPhone:** open the link in **Safari**, tap **Share**, then **Add to Home Screen**, and confirm.

The web app has a manifest, icon, service worker, and standalone display mode. Browsers decide when to show an install prompt, and the user must confirm. This creates an app-like home-screen shortcut; it is not a native App Store or Google Play app.

### Common beginner problems

- **“Supabase environment variables are missing”:** check `web\.env.local`, confirm all three variable names, save it, and restart the local Next.js command. On Vercel, check **Settings → Environment Variables**, then redeploy.
- **Signup says the email is invalid:** this prototype accepts Gmail-format addresses only. Confirm the email address is entered correctly.
- **Signup still asks for email confirmation:** in Supabase, open **Authentication → Providers → Email**, turn off **Confirm email**, save, and try signing up with a new email. If an account was already created, try signing in with it.
- **“relation/table does not exist” or empty reference data:** the SQL migration may not have run successfully. Re-open Supabase Table Editor and SQL Editor, inspect the failed query's first error, and resolve that before continuing.
- **An individual cannot be added to an employer roster:** they need an existing individual account and must not already be on that employer's active roster. The group roster limit is 20.
- **Vercel build fails:** verify the Root Directory is `web`, Node is at least 20.9, and the deployment logs show no TypeScript/build errors.
- **The web app and original demo show different data:** they use separate databases. The web app uses Supabase; the older app uses the local SQLite database unless separately configured.

### Limitations and safety before public use

- The web app is a prototype: plan payments and payouts are simulated, and the sample readings are synthetic. No insurance cover is issued and no money is transferred. Do not enter real customer or payment information.
- The migration does not copy old SQLite accounts, passwords, policies, readings, or payment history. Existing local demo usernames/passwords do not work in the new web app.
- The original Python feed poller has not been migrated. The web app displays seeded and manually entered readings only; do not use these example readings for decisions about health, insurance, or payments.
- The prototype does not provide a production process for identity verification, actual payment processing, password recovery, MFA, operations monitoring, or comprehensive backups. Verify current Vercel/Supabase free-plan quotas and data-retention terms before relying on the services.
- RLS and server-side role checks are implemented as a starting point, not a guarantee of production readiness. Have the database rules and data-handling requirements reviewed before allowing real people or sensitive data.

# Al Shefa — Patient Antibiotic Safety Record

A web app where every patient keeps their own antibiotic history (allergies,
pregnancy status, medical conditions) on their phone. Each time a physician
or pharmacist prescribes an antibiotic, the patient adds it to their record
and the app immediately checks it against:

1. **Recorded allergies** (direct match + known cross-reactive drug classes)
2. **Pregnancy status** (if the antibiotic is contraindicated in pregnancy)
3. **Recent exposure** to the same antibiotic (configurable lookback window)
4. **Recorded medical conditions** that are listed as a contraindication

Three roles: a **Clinical Pharmacist / Controller** account (full database
access — you), a limited **Staff** account (other pharmacists/physicians who
need to look up a patient and add an antibiotic, but not edit the clinical
record), and a **Patient** account (their own record only, found by a
private patient ID). See section 3.5 below for the full permissions split.

> **This is a clinical decision-support tool, not a diagnostic one.** Every
> alert must be verified by a licensed physician or pharmacist. The seeded
> antibiotic reference data (pregnancy notes, contraindications) is a
> pharmacology starting point — review and correct it from the Owner
> Dashboard before relying on it for real patients.

## Why so few dependencies?

The app runs on **Flask + Python's built-in `sqlite3`** only — no ORM, no
Flask-Login, no Flask-WTF. Sessions use Flask's own signed cookies, and CSRF
protection is a small hand-rolled check (`app/csrf.py`). Fewer moving parts
means every query and every security check is plainly visible in the code,
which matters for a tool that will eventually hold real patient data.

## 1. Setup

```bash
cd alshefa_app
python3 -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set a real SECRET_KEY and an OWNER_PASSWORD you'll remember.
# Generate a SECRET_KEY with:
python3 -c "import secrets; print(secrets.token_hex(32))"

python3 seed.py     # creates the database, your owner account, and the
                     # starting antibiotic reference list
```

## 2. Run it

```bash
python3 run.py
```

Open `http://127.0.0.1:5000`. Log in as owner with the username/password
from your `.env` (default `admin` / whatever you set as `OWNER_PASSWORD`),
or register a new patient.

**Change the owner password immediately after first login** by adding a new
full-access account with a strong password from Controller Dashboard → Site
Settings, then treat the original `admin` account as disposable (or reset
its password directly in the database).

## 2.5 Getting a public link (deploy to Render)

Running it locally (above) only opens the app on your own computer — for a
link other people (competition judges, other staff) can open themselves,
it needs to run on a server somewhere. This repo is set up to deploy with
one path in mind: **[Render](https://render.com)**, using Docker (so the
Arabic PDF export's `wkhtmltopdf` dependency comes along automatically —
see section 3 for why that matters) and its free tier. It doesn't need a
credit card for the free plan itself, though Render's signup flow may ask
you to verify a card with a small refundable charge — that's a Render
policy, not something this app requires.

**Important limitation of the free tier, read this before you rely on it**:
free Render web services spin down after 15 minutes with no traffic, and
**local files are wiped on every restart** — including this app's SQLite
database. That means any patient record, staff account, or antibiotic
entry added while the demo is live will disappear the next time it spins
down and restarts. The app re-creates the database structure, the
antibiotic reference list, and your one seeded admin account automatically
every time it boots (so it's never just broken/empty), but it can't bring
back data nobody told it to keep. **This is fine for a competition demo or
letting people click around** — it's not fine for real patient data. When
you're ready for that, see section 5's "before real patients" checklist —
the short version is Render's paid Starter plan (~$7/month) plus a small
persistent disk (~$0.25/GB/month), which keeps the database file across
restarts. Section 5 has the exact settings.

### Step 1: push this code to GitHub

This folder is already a git repository with one commit ready to go. On
your own computer (with [git](https://git-scm.com/downloads) installed):

1. On [github.com](https://github.com), create a new **empty** repository
   (no README/license/gitignore — just the bare repo) — e.g. named
   `alshefa-app`.
2. In a terminal, inside this `alshefa_app` folder:
   ```bash
   git remote add origin https://github.com/<your-username>/alshefa-app.git
   git push -u origin main
   ```

### Step 2: deploy it on Render

1. Sign up / log in at [render.com](https://render.com) (signing up with
   your GitHub account is the quickest — it also makes the next step
   easier since Render can then see your repos).
2. Click **New +** → **Blueprint**.
3. Connect the `alshefa-app` GitHub repo you just pushed. Render will find
   the `render.yaml` file in it and pre-fill almost everything — service
   type, Docker build, plan (Free), and the app's configuration settings.
4. The one field you must fill in yourself is **`OWNER_PASSWORD`** (it's
   deliberately left blank for you to set, rather than shipping a default
   password in the repo) — pick a real password for the first controller
   account. Everything else can be left as Render pre-filled it.
5. Click **Apply** / **Create**. The first build takes a few minutes
   (installing `wkhtmltopdf` and the Python dependencies) — you can watch
   it happen in the Logs tab.
6. Once it says **Live**, Render shows your public URL — something like
   `https://alshefa-app-xxxx.onrender.com`. That's the link.
7. Open it, log in as `admin` with the `OWNER_PASSWORD` you set, and — same
   as the local setup — add a new controller account with a strong
   password from Site Settings and treat `admin` as disposable afterward.

If a deploy fails, check the **Logs** tab on Render first — this app is
written to refuse to start (with a clear message in the log) rather than
silently run with an insecure default if `SECRET_KEY` or `OWNER_PASSWORD`
weren't set, which is the most likely first-deploy issue.

## 3. How a patient record works

A patient record can start in either of two places:

- **The patient registers themselves** via "New patient — create a record"
  on their own phone.
- **The owner/hospital desk creates it for them** via Owner Dashboard →
  "+ New patient" — useful when a patient is being onboarded in person and
  you're filling in their gender, date of birth, and (for a woman) pregnancy
  status right there at the desk.

Either way, the app generates a random, unguessable **Patient ID** (e.g.
`ASH-7K3F9Q`) — not a national ID, not sequential — and the record can
optionally have a password.

### QR codes

Every patient has a **QR Code / ID card** screen (Owner Dashboard → a
patient's page → "View / print QR code & ID", or the patient's own
dashboard → "View QR code"). It shows:

- A QR code that, when scanned on the patient's phone, opens
  `/auth/go/<patient ID>`:
  - If the record has **no password**, this logs the patient straight into
    their dashboard — convenient, but it means the QR code (and the ID
    printed under it) is itself the whole credential. Treat it like a key.
  - If the record **has a password**, scanning only pre-fills the ID on the
    login screen — the password is still required. Set a password on any
    record where that matters.
- The Patient ID in large text, for manual entry as a fallback.
- A "Print ID card" button (uses the browser's print dialog — good for a
  small card or sticker to hand to the patient, or a printed QR to stick on
  a physical ID card).

QR rendering happens in the browser via the `qrcodejs` library (loaded from
a public CDN) — no extra Python dependency needed for it.

### PDF export for a doctor's visit

Both the owner (for any patient) and the patient themselves (for their own
record) can export a one-page (or more, if the history is long) summary:
demographics, allergies, conditions, and the full antibiotic history —
including the safety alerts that fired *at the time* each antibiotic was
added, so a doctor can see not just what was given but what the app
flagged about it. **Two buttons are offered, "Export PDF (English)" and
"Export PDF (Arabic)"** — same content, same layout, same brand colors and
logo, just the language of the labels and structure (right-to-left) that
differs, so either copy can be handed to a doctor.

- **English PDF** uses the `reportlab` Python library (pure Python, no
  system dependency beyond the bundled DejaVu Sans font in `app/fonts/`).
- **Arabic PDF** is built differently, on purpose: `reportlab` cannot
  correctly shape (join letters) or right-to-left-order Arabic script
  without extra libraries (`arabic-reshaper`, `python-bidi`) that could not
  be installed in the environment this app was built in. Instead, the
  Arabic PDF renders an HTML template (`app/templates/pdf/arabic_summary.html`)
  through **`wkhtmltopdf`** (a WebKit-based HTML-to-PDF program) via the
  `pdfkit` Python wrapper — WebKit's own text engine shapes and
  right-to-left-orders Arabic correctly with no extra Python libraries.

  **`wkhtmltopdf` is a system binary, not a pip package.** `pip install -r
  requirements.txt` installs `pdfkit` (the wrapper) but you must also
  install the program itself on the deployment machine:
  - Debian/Ubuntu: `sudo apt install wkhtmltopdf`
  - macOS (Homebrew): `brew install --cask wkhtmltopdf`
  - Windows / other: download an installer from the wkhtmltopdf project's
    official site.

  If it's missing, the Arabic export route returns a clear error message
  instead of a broken PDF or a silent crash — the English export is
  unaffected either way, since it doesn't use `wkhtmltopdf` at all.

Free-text fields typed in Arabic (an allergen name, a note) render
correctly on both PDFs; the Arabic PDF is simply the one with fully
Arabic labels and right-to-left layout throughout.

**A note on how the Arabic PDF was hardened.** This wkhtmltopdf build has
two real, verified rendering quirks with Arabic text that were tracked down
and fixed (see the comments in `arabic_summary.html` for the technical
detail): a line of Arabic text ending directly in a bare "." gets shifted
off the printable area and silently disappears (fixed by always putting a
space before a trailing period in Arabic template text), and three or more
stacked lines of Arabic text in one block corrupt from the third line
onward (fixed by never stacking more than two). Every fixed template
string was verified with `pdftotext -bbox` against the actual page
geometry, not just eyeballed. The one residual risk: a **very long**
Arabic free-text entry (several sentences in one allergy reaction or
condition note) could still hit the "3+ lines" limit if it has to wrap
inside a table cell — keep free-text entries to a sentence or two, or spot-
check the Arabic PDF after adding an unusually long one.

The **clinical pharmacist / controller** can look up any patient by ID and
has full read/write access — including resetting a lost password — from the
Controller Dashboard. A **staff** account can also look up any patient and
export their PDF, but has read-only access to everything except adding a
new antibiotic entry — see the next section.

### 3.5 Roles: Clinical Pharmacist / Controller vs. Staff

The single "owner" account type from the first build now has two roles,
distinguished by a `role` column on `owner_users` (`'owner'` or `'staff'`).
Both log in from the same "Hospital Staff Login" screen — the app routes
each session to the right dashboard and permissions based on their role, so
there's nothing for a user to choose at login time.

- **Clinical Pharmacist / Controller** (`role='owner'`) — this is **your**
  account (Ahmed's). Full database access, unchanged from the original
  single-role build: create patient records, edit any patient's allergies,
  conditions and pregnancy status, reset a patient's password, manage the
  antibiotic reference database, view the audit log, and create other
  accounts (staff or additional controller accounts) from Site Settings.
  Logging in as this role opens the **Controller Dashboard**, redesigned
  around what a pharmacist needs to see first rather than being a plain
  patient list: a **Recent Safety Alerts** feed (the most recent antibiotic
  entries, across every patient, that triggered a danger or warning alert —
  so a new allergy/pregnancy/condition conflict anywhere in the hospital is
  visible without opening each patient individually), a **Recent Antibiotic
  Entries** feed (the latest additions hospital-wide, whoever added them),
  then the same searchable patient list and admin buttons as before.

- **Staff** (`role='staff'`) — for other pharmacists, physicians, or desk
  staff who need the core safety-check workflow but shouldn't be able to
  edit a patient's clinical record. A staff account can:
  - Look up any patient by ID and view their full record (demographics,
    allergies, conditions, antibiotic history — all read-only).
  - Add a new antibiotic entry, which runs the same safety-check engine and
    shows the same alert result page as the controller sees.
  - View/print a patient's QR/ID card and export their PDF summary (English
    or Arabic).

  A staff account **cannot**: create a new patient record, edit a patient's
  allergies or conditions, change pregnancy status, reset a patient's
  password, manage the antibiotic reference database, view the audit log,
  or create other accounts. Server-side route decorators enforce this (not
  just hidden UI) — a staff session hitting any of these routes directly
  gets a 403, and the patient-detail page shows a short note in place of
  the hidden forms so it's clear who to ask for that change. Staff see a
  simpler **Staff Dashboard**: just the patient search/list, no admin
  buttons and no hospital-wide alert feed.

  Every antibiotic entry still records who actually added it (`owner` or
  `staff`, alongside the logged-in username in the audit log), so the
  "added by" trail stays accurate regardless of which role added it.

**Only the controller can create new accounts.** From Controller Dashboard
→ Site Settings, choose a role (Staff, or another full Clinical
Pharmacist / Controller account) when adding a username/password — staff
cannot reach this page at all.

Existing installs upgrade automatically: the first time the app starts
against a database created before roles existed, a small migration adds
the `role` column and every existing account keeps full ("owner") access —
no data is touched or lost, and no manual migration step is needed.

### 3.6 Login rate limiting

Every login surface — the owner/staff login form, the patient login form,
and the QR magic link — is rate-limited (`app/rate_limit.py`), backed by a
new `login_attempts` table rather than an in-memory counter or an extra
dependency (Flask-Limiter/Redis), so the limit survives a server restart
and would work correctly even if the app were ever run with multiple
worker processes.

Two limits are checked together, and only **failed** attempts count toward
either one (a correct login never causes a lockout):

- **Per identifier** (a username, or a patient's public ID) — 5 failures
  within 15 minutes by default (`LOGIN_ATTEMPT_LIMIT` /
  `LOGIN_ATTEMPT_WINDOW_MINUTES` in `.env`) blocks further attempts against
  that specific account or patient ID, no matter which IP they come from.
- **Per source IP** — 20 failures within the same window by default
  (`LOGIN_IP_ATTEMPT_LIMIT`), deliberately looser than the per-identifier
  limit since a shared hospital front-desk/kiosk IP will legitimately see
  many different patients and staff logging in. This is what stops someone
  from spraying guesses across many different accounts/patient IDs from one
  machine — including guessing patient IDs via the QR magic link, which
  shares its rate-limit bucket with the patient login form (guessing right
  there logs the patient straight in for a passwordless record, so it's
  rate-limited as a login attempt too).

A blocked attempt shows a "Too many login attempts, please wait about N
minutes" message (translated, both languages) without even checking the
submitted password, and is recorded in the audit log
(`login_rate_limited`) so the controller can see when and from which IP a
lockout was triggered. The table prunes its own attempts older than a day
on every write, so it doesn't grow unbounded on a long-running install.

**Caveat if you ever put this behind a reverse proxy**: the per-IP limit
only sees `request.remote_addr`. Behind a proxy, that will be the proxy's
own address unless you configure trusted `X-Forwarded-For` handling (e.g.
werkzeug's `ProxyFix`) — otherwise every visitor appears to share one IP,
which would make the per-IP limit either useless or (worse) lock out the
whole hospital together. The per-identifier limit is unaffected either way.

## 4. Extending the antibiotic reference database

Controller Dashboard → Antibiotic Reference Database (controller-only) lets
you add, edit, or remove entries: generic name, drug class, whether it's
contraindicated in pregnancy, and a comma-separated list of contraindicated
conditions (these must match the condition names patients/staff type in
exactly — keep a consistent house vocabulary, e.g. always "Renal
impairment / kidney disease").

## 5. Before using this with real patients

This build is a solid, tested prototype. Moving from "competition demo" to
"real hospital use" needs a few more steps that are genuinely worth doing
properly rather than rushing:

- **HTTPS everywhere.** Done automatically if deployed via section 2.5
  (Render terminates TLS and serves every app over HTTPS by default,
  and `render.yaml` already sets `SESSION_COOKIE_SECURE=1`). Only relevant
  if you deploy somewhere else instead: set `SESSION_COOKIE_SECURE=1` in
  `.env` and put the app behind a real TLS certificate (e.g. a reverse
  proxy like Caddy or nginx, or a host that provides HTTPS automatically).
- **A real WSGI server**, not `python run.py`'s development server. Done —
  the Dockerfile/`docker-entrypoint.sh` from section 2.5 already run
  `gunicorn -w 2 -b 0.0.0.0:$PORT run:app` instead.
- **Persistent storage for the database**, not the free tier's
  wipe-on-restart local disk (see the warning in section 2.5). On Render:
  upgrade the web service from the Free plan to **Starter** (~$7/month),
  add a **Disk** to it (Render dashboard → your service → Disks → Add
  Disk; ~$0.25/GB/month, 1 GB is plenty for a very long time), mount it at
  e.g. `/var/data`, and set the `DATABASE_PATH` environment variable to
  `/var/data/alshefa.db`. From then on the database survives restarts —
  the same `docker-entrypoint.sh` re-seed step still runs on every boot,
  but now finds existing data and skips reseeding rather than starting
  fresh (see its own comments). Take this step before adding any real
  patient's data, not after.
- **Clinical review of the antibiotic reference data** by a licensed
  pharmacist or physician — sign off on every pregnancy/contraindication
  entry before trusting it for real prescribing decisions.
- **Ideally, encryption at rest** for the SQLite file, or a move to a
  managed Postgres instance, once real patient data is stored — genuine
  hardening beyond what the disk above gives you.
- **A privacy/legal review** appropriate to your country's health-data
  regulations before go-live — this is outside what a coding assistant can
  certify.

The audit log (Controller Dashboard → Audit Log) already records every
login, record view, record change, and rate-limit lockout, which is a
useful foundation for that review. (Rate limiting on the login endpoints —
previously on this list — is now done; see section 3.6.)

## 6. Project layout

```
alshefa_app/
  app/
    db.py            sqlite3 connection + schema
    models.py         all database queries, as plain functions
    csrf.py            CSRF token generation/validation
    rate_limit.py        login rate limiting (per-identifier + per-IP, sqlite-backed)
    utils.py           session-based login helpers & access-control decorators
    pdf_export.py       builds the English "Export PDF" summary (reportlab)
    pdf_export_ar.py     builds the Arabic "Export PDF" summary (wkhtmltopdf/pdfkit)
    fonts/               bundled DejaVu Sans font used by the English PDF export
    engine/
      safety_check.py  the alert engine (allergy/pregnancy/exposure/condition)
    records.py          shared "add allergy/condition/antibiotic" logic
    auth/                owner & patient login, patient self-registration,
                          /auth/go/<id> QR magic link
    owner/                controller + staff dashboard, manual patient creation
                           (controller-only), patient management, reference DB,
                           audit log, QR/PDF views (all routes here serve both
                           roles, gated per-route by owner_required vs
                           full_owner_required in utils.py)
    patient/               patient's own dashboard, antibiotic entry, QR/PDF views
    templates/, static/     bilingual (Arabic/English, RTL-aware) UI
  seed.py              first-run setup: creates tables, owner account, reference data
  run.py               entry point (local dev server)
  requirements.txt
  .env.example
  Dockerfile            production image: Ubuntu 24.04 + wkhtmltopdf + fonts-dejavu + gunicorn
  docker-entrypoint.sh   refuses to boot with placeholder secrets; re-seeds on every
                          start (needed since free hosting tiers wipe local files); then
                          starts gunicorn
  render.yaml            Render "Blueprint" config -- see section 2.5, "Getting a public link"
  .dockerignore
```

## 7. Tested scenarios

All of the following were exercised end-to-end against a running instance
before delivery: owner login, patient self-registration (with and without a
password), owner manually creating a patient record (including setting
pregnancy status at creation), wrong-password rejection, owner
viewing/editing any patient's full record, owner resetting a patient's
password, adding allergies and conditions, and each of the six
safety-check outcomes — allergy match, pregnancy contraindication,
condition contraindication, recent-exposure warning, unknown-antibiotic
notice, and the clean "no known issues" result — plus role-based access
control (a patient session cannot reach owner pages and vice versa) and
CSRF rejection of a form submitted without a token.

Also tested for the controller/staff role split: the additive `role`-column
migration against a database created before roles existed (existing account
keeps full access, no data loss); controller creating a staff account from
Site Settings; a flagged (danger-level, allergy-match) antibiotic entry
correctly appearing in the Controller Dashboard's "Recent Safety Alerts"
feed, and a clean entry appearing in "Recent Antibiotic Entries"; staff
login landing on the simpler Staff Dashboard (no admin buttons, no alert
feed); staff successfully viewing a patient's full record and adding a new
antibiotic entry (with `added_by` correctly recorded as `staff`); staff
getting a 403 on every controller-only route both by URL (create patient,
antibiotic reference, audit log, settings) and by direct POST (reset
password, add allergy, add condition, update pregnancy status), with the
patient-detail page showing a view-only note instead of those forms; staff
still able to export both PDF languages; and the existing controller
account's own access confirmed unchanged after the change (still sees every
form, still reaches settings and the audit log). A pre-existing bug was
also found and fixed during this testing: logging in or out was silently
resetting the visitor's chosen language back to the default (Arabic)
because the session-clearing helper cleared the language key along with the
login state — session language now survives login/logout.

Also tested: the QR magic link both for a password-less record (auto-login)
and a password-protected one (ID pre-filled, password still required);
English **and Arabic** PDF export for both a mostly-empty record and a full
one (allergy + two antibiotics that triggered a pregnancy-contraindication
alert, a contraindicated-condition alert, and an allergy-match alert,
confirmed present in both exported PDFs' text) and a record with a
non-alerting antibiotic (the "no known issues" path); owner-side and
patient-side export routes for both languages; and access control / 404s
on all four PDF export routes (owner+patient × en+ar). Every Arabic PDF
generated during testing was additionally checked with `pdftotext -bbox`
against the true printable-area boundary to confirm no line silently
overflows off the page (see the note under "PDF export" above).

Also tested for login rate limiting: the owner/staff login form locking out
a specific username after 5 failed passwords in the default 15-minute
window (confirmed the *next* attempt is blocked even with the *correct*
password, and that the lockout is recorded in the audit log with the
source IP); the patient login form locking out a specific patient ID the
same way; the QR magic link sharing that same per-ID lockout bucket
(repeated wrong-ID guesses through the QR route eventually blocked further
QR attempts against that ID); a different, never-tried username/ID from
the very same source IP remaining unaffected (proving the per-identifier
limit doesn't leak across accounts); and a brand-new account successfully
logging in even after the shared IP had racked up numerous failures
elsewhere, confirming the (much looser) per-IP limit hadn't also tripped.
Also verified the `login_attempts` table appears automatically (via
`CREATE TABLE IF NOT EXISTS`, no manual migration needed) when starting the
app against a database created before this feature existed.

## 8. Next steps to build together

Good candidates for the next session: letting the controller bulk-print
QR/ID cards, a per-staff-member activity view (who added what, beyond the
hospital-wide audit log), and revisiting whether staff should be allowed to
create new patient records at the desk (currently controller-only, per the
permissions split in section 3.5). (Rate limiting on the login endpoints —
previously on this list — is now done; see section 3.6.)

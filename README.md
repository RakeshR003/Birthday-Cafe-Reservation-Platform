# Birthday Cafe — Reservation Platform

![CI](https://github.com/RakeshR003/Birthday-Cafe-Reservation-Platform/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

🔗 **Live Demo:** https://birthday-cafe-reservation-platform.onrender.com

A Flask web app for booking themed birthday decorations at partner cafes.
Three user roles, one shared codebase:

- **Customers** — browse decoration setups, check availability, book a slot
- **Decorators** — register, submit cafes and decoration packages for approval
- **Admins** — approve/reject submissions, manage bookings, block time slots, configure site settings


## Features

- Three-role auth (customer / decorator / admin) with session-scoped access control
- Photo + video uploads for decoration listings, with size/type validation and image thumbnailing
- Real-time availability checking before a booking is confirmed
- Admin dashboard: approve/reject cafes & decorations, manage bookings, block calendar slots, edit site-wide settings
- Booking confirmation flow with pending/approved/rejected states and email notifications
- Self-healing database seeding — a broken admin account repairs itself on startup instead of requiring a manual reset
- Automated test suite (pytest) covering booking, auth, and API endpoints, run on every push via GitHub Actions

## Tech stack

- Flask + Flask-SQLAlchemy (SQLite by default)
- Flask-WTF / WTForms (CSRF-protected forms)
- Flask-Mail (booking notification emails)
- Bootstrap 5 + vanilla JS/Swiper on the frontend
- pytest + GitHub Actions for automated testing

## Getting started

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then edit .env with your own values
python app.py                    # first run auto-creates + seeds the database
```

Visit `http://localhost:5000`.

The app seeds itself automatically on startup — it checks for (and repairs)
the admin account every time it starts, so a broken login self-heals; you
don't need to delete the database file if something looks wrong.

**Demo logins (created automatically):**
| Role | Email | Password |
|---|---|---|
| Admin | `admin@birthdaycafe.com` | `Admin@123!` |
| Decorator | `decorator@example.com` | `Decorator@123!` |

Change both before deploying anywhere public. In debug mode, both login
pages also show these credentials on-screen as a reminder — that hint
disables itself automatically once `FLASK_ENV` is set to `production`.

## Testing

```bash
pytest tests/ -v
```

Covers homepage/detail rendering, the full booking flow (submission →
confirmation page), admin/decorator login (including rejecting bad
credentials), and the admin cafe/decorator detail API endpoints. CI runs
this automatically on every push via `.github/workflows/ci.yml`.

## Environment variables (`.env`)

See `.env.example` for the full list. The important ones:

- `SECRET_KEY` — generate a real one for anything beyond local dev (`python -c "import secrets; print(secrets.token_hex(32))"`)
- `MAIL_USERNAME` / `MAIL_PASSWORD` — use a Gmail **App Password**, not your real account password
- `ADMIN_WHATSAPP` — used only to build a `wa.me/...` link; this project does not use the paid WhatsApp Business API

## Project structure

```
app.py                  # routes (customer, decorator, admin) + self-healing db seeding
models.py               # SQLAlchemy models
forms.py                # WTForms definitions
config.py               # env-driven configuration
templates/              # customer-facing pages (extend layout.html)
templates/admin/        # admin panel (extends admin/admin_layout.html)
templates/decorator/    # decorator portal (extends decorator/decorator_layout.html)
static/css/main.css     # shared design system (colors, typography, components)
static/css/admin.css    # admin-only overrides
static/css/decorator.css # decorator-only overrides
static/js/main.js       # site-wide JS (back-to-top, form UX, confetti on booking confirm)
static/js/admin.js      # admin-only JS
tests/test_app.py       # pytest suite (booking, auth, admin API)
.github/workflows/ci.yml # GitHub Actions: runs tests on every push
```

## Known limitations / next steps

- `app.py` is currently a single large file rather than Flask blueprints — fine at this size, worth splitting if it grows further
- WhatsApp integration is `wa.me` links only, not the paid Business API
- File uploads are stored on local disk (`static/uploads/`) — fine for a demo, would need object storage (S3, etc.) for a real multi-server deployment

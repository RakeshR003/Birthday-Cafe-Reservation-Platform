"""
Basic test suite for the Birthday Cafe reservation platform.

Run with:
    pytest

Uses an in-memory SQLite database and disables CSRF so tests don't need
to scrape tokens out of rendered HTML — this file only *tests* the app,
it doesn't change any app behavior.
"""
import datetime
import io

import pytest

from app import app as flask_app, db, create_tables, seed_data


@pytest.fixture
def app():
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
        SERVER_NAME="localhost",
    )
    with flask_app.app_context():
        create_tables()
        seed_data()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------

def test_homepage_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_decoration_detail_loads(client):
    resp = client.get("/decoration/1")
    assert resp.status_code == 200


def test_decoration_detail_missing_returns_404(client):
    resp = client.get("/decoration/9999")
    assert resp.status_code == 404


def test_quick_view_api_returns_json(client):
    resp = client.get("/api/decorations/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "decoration" in data
    assert data["decoration"]["id"] == 1


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


# ---------------------------------------------------------------------
# Booking flow
# ---------------------------------------------------------------------

def test_booking_form_loads(client):
    resp = client.get("/book/1")
    assert resp.status_code == 200


def test_booking_submission_creates_booking_and_redirects(client):
    future_date = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    resp = client.post(
        "/book/1",
        data={
            "name": "Test Customer",
            "email": "test@example.com",
            "phone": "9876543210",
            "date": future_date,
            "time": "12:00",
            "guests": "4",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/booking-confirm/" in resp.headers["Location"]

    # Following the redirect should show the pending/confirmation page
    confirm = client.get(resp.headers["Location"])
    assert confirm.status_code == 200
    assert b"Submitted" in confirm.data or b"Confirmed" in confirm.data


def test_booking_requires_valid_decoration(client):
    resp = client.get("/book/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------
# Admin auth + self-healing seed
# ---------------------------------------------------------------------

def test_admin_login_with_seeded_credentials(client):
    resp = client.post(
        "/admin/login",
        data={"email": "admin@birthdaycafe.com", "password": "Admin@123!"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/dashboard")


def test_admin_login_rejects_wrong_password(client):
    resp = client.post(
        "/admin/login",
        data={"email": "admin@birthdaycafe.com", "password": "wrong-password"},
    )
    assert resp.status_code == 200  # redisplays login form, no redirect


def test_admin_dashboard_requires_login(client):
    resp = client.get("/admin/dashboard", follow_redirects=False)
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_admin_can_view_cafe_details(client, app):
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_id"] = 1
        sess["admin_email"] = "admin@birthdaycafe.com"
        sess["login_time"] = datetime.datetime.utcnow().timestamp()

    resp = client.get("/api/admin/cafes/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "name" in data["cafe"]


# ---------------------------------------------------------------------
# Decorator flow
# ---------------------------------------------------------------------

def test_decorator_login_with_seeded_credentials(client):
    resp = client.post(
        "/decorator/login",
        data={"email": "decorator@example.com", "password": "Decorator@123!"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/decorator/dashboard")


def test_decorator_dashboard_shows_stats(client):
    with client.session_transaction() as sess:
        sess["decorator_logged_in"] = True
        sess["decorator_id"] = 2
        sess["decorator_name"] = "Floral Designs Co."

    resp = client.get("/decorator/dashboard")
    assert resp.status_code == 200
    # This used to render blank because the route never passed these
    # counters to the template at all.
    assert b"Total" in resp.data or b"Decorations" in resp.data


def test_decorator_dashboard_requires_login(client):
    resp = client.get("/decorator/dashboard", follow_redirects=False)
    assert resp.status_code == 302


def test_submit_decoration_requires_at_least_one_photo(client):
    with client.session_transaction() as sess:
        sess["decorator_logged_in"] = True
        sess["decorator_id"] = 2
        sess["decorator_name"] = "Floral Designs Co."

    resp = client.post(
        "/submit_decoration",
        data={
            "title": "Missing Photo Theme",
            "price": "1000",
            "description": "A theme with no photo attached.",
            "includes": "Balloons",
            "cafe_id": "1",
        },
        content_type="multipart/form-data",
    )
    # No photo attached -> redisplays the form with an error, not a redirect
    assert resp.status_code == 200


def test_submit_decoration_with_photo_succeeds(client):
    with client.session_transaction() as sess:
        sess["decorator_logged_in"] = True
        sess["decorator_id"] = 2
        sess["decorator_name"] = "Floral Designs Co."

    photo = (io.BytesIO(b"\xff\xd8\xff\xe0fakejpegbytes"), "test.jpg")
    resp = client.post(
        "/submit_decoration",
        data={
            "title": "A Brand New Theme",
            "price": "1800",
            "description": "Freshly submitted decoration theme for testing.",
            "includes": "Balloons\nBanner",
            "cafe_id": "1",
            "photos": photo,
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/decorator/dashboard")

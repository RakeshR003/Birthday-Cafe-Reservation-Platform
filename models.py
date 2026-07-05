from datetime import datetime, date
import json

from sqlalchemy import UniqueConstraint
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# =====================================================
#  USER MODEL
# =====================================================

class User(db.Model):
    """
    Represents any user in the system:
    - customer (future use)
    - decorator
    - admin
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    # 'customer', 'decorator', 'admin'
    role = db.Column(db.String(20), default='customer')

    phone = db.Column(db.String(20))
    company_name = db.Column(db.String(100))

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relationships
    decorations_created = db.relationship(
        'Decoration', backref='created_by_user', lazy=True
    )
    cafes_created = db.relationship(
        'Cafe', backref='created_by_user', lazy=True
    )

    # ---------- Password helpers ----------

    def set_password(self, password: str) -> None:
        """Hash and store the password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check a plain password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email} ({self.role})>"


# =====================================================
#  CAFE MODEL
# =====================================================

class Cafe(db.Model):
    """
    Cafe / location where decorations can be set up.
    Created by a decorator (created_by -> User.id).
    """
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    area = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)

    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))

    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    # 'pending', 'approved', 'rejected'
    status = db.Column(db.String(20), default='pending')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One cafe -> many decorations
    decorations = db.relationship('Decoration', backref='cafe', lazy=True)

    def get_status_badge(self) -> str:
        """
        Return a Bootstrap color name used in templates.
        Example: 'success', 'warning', 'danger'
        """
        status_colors = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger'
        }
        return status_colors.get(self.status, 'secondary')

    def __repr__(self) -> str:
        return f"<Cafe {self.id} {self.name} ({self.area})>"


# =====================================================
#  DECORATION MODEL
# =====================================================

class Decoration(db.Model):
    """
    Decoration / setup theme that can be booked.

    Key points:
    - Linked to a Cafe (cafe_id)
    - Linked to a creator User (created_by)
    - Stores media (images + videos) as JSON in 'images'
    - 'includes' is a JSON list of bullet points
    """
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)

    # Optional: used in filters & tags on home page
    themes = db.Column(db.String(200))  # e.g. "Warm, Minimal, Neon"

    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float)  # For discount calculations
    discount_percent = db.Column(db.Integer, default=0)  # 0-100%

    description = db.Column(db.Text, nullable=False)

    # Stores either:
    # - OLD FORMAT: ["path1", "path2"]
    # - NEW FORMAT: [{"path": "...", "type": "image"}, {"path": "...", "type": "video"}]
    images = db.Column(db.Text)

    # JSON list of strings (what is included)
    includes = db.Column(db.Text)

    cafe_id = db.Column(db.Integer, db.ForeignKey('cafe.id'), nullable=False)

    # 'pending', 'approved', 'rejected'
    status = db.Column(db.String(20), default='pending')

    # Used on home page to highlight certain setups
    featured = db.Column(db.Boolean, default=False)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One decoration -> many bookings
    bookings = db.relationship('Booking', backref='decoration', lazy=True)

    # ---------- Media helpers ----------

    def get_media_files(self):
        """
        Get all media files (images + videos) with type information.
        Returns a list like:
        [
            {"path": "static/uploads/file1.jpg", "type": "image"},
            {"path": "static/uploads/video.mp4", "type": "video"}
        ]
        """
        if not self.images:
            return []

        try:
            media_data = json.loads(self.images)

            # New format: list of dicts
            if isinstance(media_data, list) and media_data:
                if isinstance(media_data[0], dict):
                    return media_data
                # Old format: list of strings -> convert to dict type "image"
                elif isinstance(media_data[0], str):
                    return [{'path': path, 'type': 'image'} for path in media_data]
        except Exception as e:
            print(f"[Decoration.get_media_files] JSON parse error: {e}")
            return []

        return []

    def get_images(self):
        """Return only image media entries."""
        return [m for m in self.get_media_files() if m.get('type') == 'image']

    def get_videos(self):
        """Return only video media entries."""
        return [m for m in self.get_media_files() if m.get('type') == 'video']

    def get_first_image(self):
        """Return path of first image for thumbnails."""
        images = self.get_images()
        return images[0]['path'] if images else None

    def get_first_video(self):
        """Return path of first video for preview."""
        videos = self.get_videos()
        return videos[0]['path'] if videos else None

    def get_includes(self):
        """Return includes as list of strings."""
        if not self.includes:
            return []
        try:
            return json.loads(self.includes)
        except Exception:
            return []

    def get_status_badge(self) -> str:
        """Return Bootstrap badge color name based on status."""
        status_colors = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger'
        }
        return status_colors.get(self.status, 'secondary')

    def get_current_price(self) -> float:
        """Return price after applying discount, if any."""
        if self.discount_percent and self.discount_percent > 0:
            return self.price * (1 - self.discount_percent / 100)
        return self.price

    def __repr__(self) -> str:
        return f"<Decoration {self.id} {self.title} ({self.status})>"


# =====================================================
#  BOOKING MODEL
# =====================================================

class Booking(db.Model):
    """
    A booking for a specific decoration on a specific date & time.
    """
    id = db.Column(db.Integer, primary_key=True)

    decoration_id = db.Column(
        db.Integer, db.ForeignKey('decoration.id'), nullable=False
    )

    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)

    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(10), nullable=False)

    guests = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)

    # 'pending', 'approved', 'completed', 'cancelled', 'rejected' (can extend later)
    status = db.Column(db.String(20), nullable=False, default='pending')  # values: pending, approved, rejected

    total_amount = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    whatsapp_sent = db.Column(db.Boolean, default=False)

    def __repr__(self) -> str:
        return f"<Booking {self.id} {self.customer_name} {self.date} {self.time}>"


# =====================================================
#  NOTIFICATION MODEL
# =====================================================

class Notification(db.Model):
    """
    System notifications:
    - security events (logins, invalid sessions)
    - booking alerts
    - other system messages
    """
    id = db.Column(db.Integer, primary_key=True)

    type = db.Column(db.String(50), nullable=False)  # 'security', 'booking', etc.
    title = db.Column(db.String(200))
    message = db.Column(db.Text)

    # Free-form JSON payload (extra data)
    payload = db.Column(db.Text)

    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_payload(self):
        """Return payload as dict."""
        if not self.payload:
            return {}
        try:
            return json.loads(self.payload)
        except Exception:
            return {}

    def __repr__(self) -> str:
        return f"<Notification {self.id} {self.type} read={self.read}>"


# =====================================================
#  ADMIN SETTINGS MODEL
# =====================================================

class AdminSettings(db.Model):
    """
    Simple key/value settings table.

    Examples:
    - site_name
    - admin_email
    - booking_advance_days
    - max_guests_per_booking
    - announcement_message
    """
    id = db.Column(db.Integer, primary_key=True)

    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<AdminSettings {self.key}={self.value}>"


# =====================================================
#  PROMOTION MODEL
# =====================================================

class Promotion(db.Model):
    """
    Optional promotions / offers.

    Not heavily used right now, but ready to power:
    - banners
    - extra discounts
    """
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    discount_percent = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)

    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_currently_active(self) -> bool:
        """Check if promotion is active based on dates + is_active flag."""
        if not self.is_active:
            return False

        today = date.today()

        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False

        return True

    def __repr__(self) -> str:
        return f"<Promotion {self.id} {self.title} active={self.is_active}>"


# --- ADDED: BlockedSlot and MessageTemplate models ---


class BlockedSlot(db.Model):
    __tablename__ = 'blocked_slot'
    id = db.Column(db.Integer, primary_key=True)
    cafe_id = db.Column(db.Integer, db.ForeignKey('cafe.id'), nullable=True)
    decoration_id = db.Column(db.Integer, db.ForeignKey('decoration.id'), nullable=True)
    # use db.Date to align with Booking.date
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, nullable=True)  # optional admin user id
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('decoration_id', 'date', 'time', name='uix_block_decoration_datetime'),
        UniqueConstraint('cafe_id', 'date', 'time', name='uix_block_cafe_datetime'),
    )

class MessageTemplate(db.Model):
    __tablename__ = 'message_template'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

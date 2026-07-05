# FULL app.py - Replace your current app.py with this file.
# I kept structure and code you provided, merged duplicates, added
# blocked slots, templates, availability checks, admin protections,
# and small robustness fixes. Do migrations after replacing.

import os
import json
import uuid
import time
import secrets
from datetime import datetime, date, timedelta

from urllib.parse import quote_plus
from werkzeug.utils import secure_filename

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, flash, current_app
)
from flask_mail import Mail, Message
from flask_cors import CORS
from PIL import Image

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from config import Config
from models import (
    db, User, Cafe, Decoration, Booking,
    Notification, AdminSettings,
    BlockedSlot, MessageTemplate
)
from forms import (
    BookingForm, DecorationSubmissionForm, AdminLoginForm,
    DecoratorRegistrationForm, DecoratorLoginForm, CafeSubmissionForm,
    AdminSettingsForm, DiscountForm
)

# =====================================================
#  APP & EXTENSIONS SETUP
# =====================================================

app = Flask(__name__)
app.config.from_object(Config)

if app.config.get('DEBUG', True):
    app.config['SESSION_COOKIE_SECURE'] = False

db.init_app(app)
mail = Mail(app)
CORS(app)


# =====================================================
#  HELPERS: filenames, media saving
# =====================================================

def allowed_extension(filename: str, allowed: set):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed

def make_unique_filename(filename: str):
    name = secure_filename(filename)
    uid = uuid.uuid4().hex[:10]
    ts = int(time.time())
    base, ext = os.path.splitext(name)
    return f"{base}_{ts}_{uid}{ext}"

def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def save_media_files(file_list, media_type: str):
    cfg = current_app.config
    UPLOAD_BASE = cfg.get('UPLOAD_FOLDER', os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'uploads'))
    MAX_PHOTO_SIZE = cfg.get('MAX_PHOTO_SIZE', 12 * 1024 * 1024)
    MAX_VIDEO_SIZE = cfg.get('MAX_VIDEO_SIZE', 80 * 1024 * 1024)
    MAX_PHOTOS = cfg.get('MAX_PHOTOS', 6)
    MAX_VIDEOS = cfg.get('MAX_VIDEOS', 3)
    IMAGE_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    VIDEO_EXTS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'ogg'}

    if media_type == 'image':
        allowed = IMAGE_EXTS
        max_size = MAX_PHOTO_SIZE
        subfolder = 'photos'
        max_count = MAX_PHOTOS
    elif media_type == 'video':
        allowed = VIDEO_EXTS
        max_size = MAX_VIDEO_SIZE
        subfolder = 'videos'
        max_count = MAX_VIDEOS
    else:
        raise ValueError("media_type must be 'image' or 'video'")

    files = [f for f in (file_list or []) if getattr(f, 'filename', '')]
    if len(files) > max_count:
        raise ValueError(f"Max {max_count} {media_type}s allowed, you submitted {len(files)}")

    saved = []
    folder = os.path.join(UPLOAD_BASE, subfolder)
    ensure_folder(folder)

    for f in files:
        filename = f.filename
        if not filename:
            continue
        if not allowed_extension(filename, allowed):
            raise ValueError(f"File {filename} has unsupported extension for {media_type}. Allowed: {', '.join(sorted(allowed))}")

        size = None
        try:
            f.stream.seek(0, os.SEEK_END)
            size = f.stream.tell()
            f.stream.seek(0)
        except Exception:
            size = None

        if size and size > max_size:
            raise ValueError(f"File {filename} is too large ({round(size/1024/1024,2)} MB). Max {round(max_size/1024/1024,2)} MB.")

        unique_name = make_unique_filename(filename)
        save_path = os.path.join(folder, unique_name)

        ext_l = os.path.splitext(filename)[1].lower().lstrip('.')
        is_image = ext_l in IMAGE_EXTS

        try:
            if is_image:
                try:
                    img = Image.open(f)
                    img.thumbnail((1200, 900))
                    img.save(save_path)
                except Exception:
                    f.save(save_path)
            else:
                f.save(save_path)
        except Exception as e:
            raise ValueError(f"Failed saving file {filename}: {e}")

        rel_path = os.path.join('static', 'uploads', subfolder, unique_name).replace('\\', '/')
        saved.append({'path': rel_path, 'type': 'image' if is_image else 'video', 'filename': unique_name, 'size': size or 0})

    return saved

def save_uploaded_media(files):
    result = []
    images = []
    videos = []
    for file in files:
        if not getattr(file, 'filename', ''):
            continue
        ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
        if ext in {'jpg','jpeg','png','gif','webp'}:
            images.append(file)
        elif ext in {'mp4','mov','avi','mkv','webm','ogg'}:
            videos.append(file)
        else:
            continue
    if images:
        result.extend(save_media_files(images, 'image'))
    if videos:
        result.extend(save_media_files(videos, 'video'))
    return result

# =====================================================
#  AUTH HELPERS / DECORATORS
# =====================================================

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not all([
            session.get('admin_logged_in'),
            session.get('admin_email'),
            session.get('admin_id'),
            session.get('login_time')
        ]):
            flash('Admin authentication required', 'error')
            return redirect(url_for('admin_login'))

        admin_user = User.query.filter_by(
            id=session.get('admin_id'),
            email=session.get('admin_email'),
            role='admin',
            is_active=True
        ).first()

        if not admin_user:
            notification = Notification(
                type='security',
                title='Invalid Admin Session',
                message=f'Invalid admin session attempt from {request.remote_addr}',
                payload=json.dumps({
                    'ip': request.remote_addr,
                    'session_email': session.get('admin_email'),
                    'session_id': session.get('admin_id')
                })
            )
            db.session.add(notification)
            db.session.commit()
            session.clear()
            flash('Security session expired', 'error')
            return redirect(url_for('admin_login'))

        session_timeout = 1 * 60 * 60
        current_time = datetime.utcnow().timestamp()
        login_time = session.get('login_time', 0)

        if current_time - login_time > session_timeout:
            notification = Notification(
                type='security',
                title='Admin Session Expired',
                message=f'Admin session expired for {admin_user.email} from {request.remote_addr}',
                payload=json.dumps({
                    'ip': request.remote_addr,
                    'admin_id': admin_user.id,
                    'session_duration': current_time - login_time
                })
            )
            db.session.add(notification)
            db.session.commit()
            session.clear()
            flash('Session expired. Please login again.', 'error')
            return redirect(url_for('admin_login'))

        return f(*args, **kwargs)
    return decorated_function

def decorator_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('decorator_logged_in'):
            flash('Please login as decorator to access this page', 'error')
            return redirect(url_for('decorator_login'))

        decorator_user = User.query.filter_by(
            id=session.get('decorator_id'),
            role='decorator',
            is_active=True
        ).first()

        if not decorator_user:
            notification = Notification(
                type='security',
                title='Invalid Decorator Session',
                message=f'Invalid decorator session attempt from {request.remote_addr}',
                payload=json.dumps({
                    'ip': request.remote_addr,
                    'session_id': session.get('decorator_id')
                })
            )
            db.session.add(notification)
            db.session.commit()
            session.pop('decorator_logged_in', None)
            session.pop('decorator_id', None)
            session.pop('decorator_name', None)
            flash('Security session expired', 'error')
            return redirect(url_for('decorator_login'))

        return f(*args, **kwargs)
    return decorated_function

# =====================================================
#  CONTEXT PROCESSORS
# =====================================================

@app.context_processor
def inject_global_vars():
    return {}

@app.context_processor
def inject_admin_vars():
    if request.endpoint and 'admin' in request.endpoint and session.get('admin_logged_in'):
        notifications_count = Notification.query.filter_by(read=False).count()
        return {
            'notifications': notifications_count,
            'admin_name': session.get('admin_name')
        }
    return {}

# =====================================================
#  DATABASE & SEEDING
# =====================================================

def create_tables():
    db.create_all()
    print("✅ Database tables created successfully!")

def seed_data():
    print("🔄 Seeding initial data...")
    admin = User.query.filter_by(email='admin@birthdaycafe.com').first()
    if not admin:
        admin = User(
            name='Super Admin',
            email='admin@birthdaycafe.com',
            role='admin',
            phone='+919876543210',
            is_active=True
        )
        admin.set_password('Admin@123!')
        db.session.add(admin)
        print("✅ Admin user created: admin@birthdaycafe.com / Admin@123!")
    else:
        print(f"✅ Admin user already exists: {admin.email}")
        healed = False
        if not admin.check_password('Admin@123!'):
            admin.set_password('Admin@123!')
            healed = True
            print("🔄 Admin password reset to: Admin@123!")
        if not admin.is_active:
            admin.is_active = True
            healed = True
        if admin.role != 'admin':
            admin.role = 'admin'
            healed = True
        if healed:
            db.session.commit()
            print("🔄 Admin account repaired (was_active/role corrected)")

    if AdminSettings.query.count() == 0:
        settings = [
            AdminSettings(key='site_name', value='Birthday Cafe', description='Website name'),
            AdminSettings(key='admin_email', value='admin@birthdaycafe.com', description='Admin contact email'),
            AdminSettings(key='booking_advance_days', value='60', description='Maximum days in advance for booking'),
            AdminSettings(key='max_guests_per_booking', value='50', description='Maximum guests per booking'),
            AdminSettings(key='global_discount', value='0', description='Global discount percentage'),
            AdminSettings(key='announcement_message', value='', description='Site-wide announcement message'),
        ]
        db.session.add_all(settings)
        print("✅ Default settings created")

    decorator = User.query.filter_by(email='decorator@example.com').first()
    if not decorator:
        decorator = User(
            name='Floral Designs Co.',
            email='decorator@example.com',
            role='decorator',
            phone='+919876543211',
            company_name='Floral Designs Co.',
            is_active=True
        )
        decorator.set_password('Decorator@123!')
        db.session.add(decorator)
        print("✅ Sample decorator created: decorator@example.com / Decorator@123!")
    else:
        print(f"✅ Decorator user already exists: {decorator.email}")

    if Cafe.query.count() == 0:
        cafes = [
            Cafe(
                name='Koramangala Social',
                area='Koramangala',
                address='123, 5th Block, Koramangala, Bangalore - 560034\nLandmark: Near Forum Mall',
                phone='+918012345678',
                email='koramangala@social.com',
                status='approved'
            ),
            Cafe(
                name='Third Wave Coffee',
                area='New BEL Road',
                address='456, New BEL Road, Bangalore - 560094\nLandmark: Opposite RBI Layout',
                phone='+918012345679',
                email='newbelroad@thirdwave.com',
                status='approved'
            )
        ]
        db.session.add_all(cafes)
        db.session.commit()

        decorator_user = User.query.filter_by(role='decorator').first()

        decorations = [
            Decoration(
                title='Elegant Floral Theme',
                price=2500,
                original_price=2500,
                description='Beautiful floral arrangements with pastel colors perfect for intimate birthday celebrations.',
                images=json.dumps([
                    'https://images.unsplash.com/photo-1511795409834-ef04bbd61622?w=600',
                    'https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?w=600'
                ]),
                includes=json.dumps(['Fresh Flowers', 'Balloon Arch', 'Custom Banner', 'Table Decor']),
                cafe_id=1,
                status='approved',
                created_by=decorator_user.id if decorator_user else 1
            ),
            Decoration(
                title='Vintage Rustic Theme',
                price=3200,
                original_price=3200,
                discount_percent=15,
                description='Rustic charm with wooden elements and vintage decor.',
                images=json.dumps([
                    'https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?w=600',
                    'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600'
                ]),
                includes=json.dumps(['Wooden Decor', 'Fairy Lights', 'Vintage Centerpieces']),
                cafe_id=1,
                status='approved',
                featured=True,
                created_by=decorator_user.id if decorator_user else 1
            ),
        ]
        db.session.add_all(decorations)
        print("✅ Sample data created")

    db.session.commit()
    print("🎉 Seed data completed successfully!")

    verify_admin = User.query.filter_by(email='admin@birthdaycafe.com').first()
    if verify_admin and verify_admin.check_password('Admin@123!'):
        print("🔐 Admin login verified: admin@birthdaycafe.com / Admin@123!")
    else:
        print("❌ Admin login verification FAILED!")

# =====================================================
#  UTILITY: WHATSAPP + OTHER HELPERS
# =====================================================

def normalize_phone_for_wa(phone, default_country_code='91'):
    if not phone:
        return ''
    digits = ''.join(ch for ch in phone if ch.isdigit())
    if len(digits) == 10:
        return default_country_code + digits
    return digits

def build_whatsapp_link(raw_phone: str, message: str):
    if not raw_phone:
        return None
    digits = normalize_phone_for_wa(raw_phone)
    if not digits:
        return None
    encoded_text = quote_plus(message)
    return f"https://wa.me/{digits}?text={encoded_text}"

def send_admin_email(subject: str, body: str) -> bool:
    try:
        msg = Message(
            subject=subject,
            recipients=[app.config.get('ADMIN_EMAIL')],
            body=body,
            html=body.replace('\n', '<br>')
        )
        mail.send(msg)
        print(f"✅ Email sent to admin: {subject}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

def get_admin_settings() -> dict:
    settings = AdminSettings.query.all()
    return {setting.key: setting.value for setting in settings}

def get_booking_calendar():
    today = date.today()
    thirty_days_later = today + timedelta(days=30)

    bookings = Booking.query.filter(
        Booking.date >= today,
        Booking.date <= thirty_days_later
    ).all()

    calendar_data = []
    for booking in bookings:
        calendar_data.append({
            'id': booking.id,
            'title': f"{booking.decoration.title} - {booking.customer_name}",
            'start': booking.date.isoformat(),
            'time': booking.time,
            'guests': booking.guests,
            'cafe': booking.decoration.cafe.name,
            'className': 'booking-event'
        })

    return calendar_data

# =====================================================
#  SERIALIZERS / DECORATION JSON
def normalize_media_path(p):
    """Resolve a stored media path (which may be a full URL or a path
    relative to the static/ folder) into a URL the browser can load."""
    if not p:
        return None
    p = str(p).strip()
    if p.startswith('http://') or p.startswith('https://'):
        return p
    if p.startswith('static/'):
        p = p[len('static/'):]
    if p.startswith('/'):
        p = p[1:]
    try:
        return url_for('static', filename=p)
    except Exception:
        return p


app.jinja_env.globals['media_url'] = normalize_media_path


# =====================================================

def decoration_to_dict(decoration):
    candidates = []
    try:
        raw_images = getattr(decoration, 'images', None)
        if raw_images:
            parsed = None
            try:
                parsed = json.loads(raw_images)
            except Exception:
                parsed = raw_images
            if isinstance(parsed, list):
                candidates.extend(parsed)
            else:
                candidates.append(parsed)
    except Exception:
        pass

    try:
        raw_videos = getattr(decoration, 'videos', None)
        if raw_videos:
            parsed_v = None
            try:
                parsed_v = json.loads(raw_videos)
            except Exception:
                parsed_v = raw_videos
            if isinstance(parsed_v, list):
                candidates.extend(parsed_v)
            else:
                candidates.append(parsed_v)
    except Exception:
        pass

    image_candidate = None
    video_candidate = None

    for c in candidates:
        if isinstance(c, dict):
            c_type = (c.get('type') or '').lower()
            c_path = c.get('path') or c.get('filename') or None
            if not c_path:
                continue
            if c_type == 'video' and not video_candidate:
                video_candidate = c_path
            elif c_type == 'image' and not image_candidate:
                image_candidate = c_path
            else:
                ext = os.path.splitext(str(c_path))[1].lower().lstrip('.')
                if ext in ['mp4', 'mov', 'mkv', 'avi'] and not video_candidate:
                    video_candidate = c_path
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] and not image_candidate:
                    image_candidate = c_path
        else:
            try:
                path_str = str(c)
                ext = os.path.splitext(path_str)[1].lower().lstrip('.')
                if ext in ['mp4', 'mov', 'mkv', 'avi'] and not video_candidate:
                    video_candidate = path_str
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] and not image_candidate:
                    image_candidate = path_str
                if (not image_candidate) and (not video_candidate) and path_str:
                    image_candidate = path_str
            except Exception:
                continue

    image_url = normalize_media_path(image_candidate)
    video_url = normalize_media_path(video_candidate)

    price = float(getattr(decoration, 'price', 0) or 0)
    discount = int(getattr(decoration, 'discount_percent', 0) or 0)
    if hasattr(decoration, 'get_current_price'):
        try:
            current_price = float(decoration.get_current_price())
        except Exception:
            current_price = price * (100 - discount) / 100.0
    else:
        current_price = price * (100 - discount) / 100.0

    cafe_area = ''
    cafe_name = ''
    try:
        if getattr(decoration, 'cafe', None):
            cafe_area = getattr(decoration.cafe, 'area', '') or ''
            cafe_name = getattr(decoration.cafe, 'name', '') or ''
    except Exception:
        cafe_area = ''
        cafe_name = ''

    return {
        'id': decoration.id,
        'title': decoration.title,
        'description': decoration.description,
        'price': price,
        'discount_percent': discount,
        'current_price': round(current_price, 2),
        'themes': getattr(decoration, 'themes', '') or '',
        'cafe_area': cafe_area,
        'cafe_name': cafe_name,
        'image': image_url,
        'video': video_url
    }

# =====================================================
#  API: PUBLIC DECORATION LOOKUP (used by Quick View modal)
# =====================================================

@app.route('/api/decorations/<int:id>')
def api_decoration_detail(id):
    decoration = Decoration.query.get_or_404(id)
    if decoration.status != 'approved':
        return jsonify({'error': 'Not available'}), 404
    return jsonify({'decoration': decoration_to_dict(decoration)})

# =====================================================
#  API: AVAILABILITY + ADMIN HELPERS
# =====================================================

@app.route('/api/check_availability', methods=['GET'])
def api_check_availability():
    decoration_id_raw = request.args.get('decoration_id')
    date_raw = request.args.get('date')
    time_raw = request.args.get('time')

    if not decoration_id_raw or not date_raw or not time_raw:
        return jsonify({'available': False, 'reason': 'invalid', 'message': 'Missing parameters'}), 400

    try:
        decoration_id = int(decoration_id_raw)
    except Exception:
        return jsonify({'available': False, 'reason': 'invalid', 'message': 'Invalid decoration id'}), 400

    try:
        date_obj = datetime.strptime(date_raw, '%Y-%m-%d').date()
    except Exception:
        return jsonify({'available': False, 'reason': 'invalid', 'message': 'Invalid date format, use YYYY-MM-DD'}), 400

    dec = Decoration.query.get(decoration_id)
    if not dec:
        return jsonify({'available': False, 'reason': 'invalid', 'message': 'Decoration not found'}), 404

    blocked = BlockedSlot.query.filter_by(decoration_id=decoration_id, date=date_obj, time=time_raw).first()
    if blocked:
        return jsonify({'available': False, 'reason': 'blocked', 'message': 'This decoration is blocked for the selected date/time.'})

    cafe_id = getattr(dec, 'cafe_id', None)
    if cafe_id:
        blocked_cafe = BlockedSlot.query.filter_by(cafe_id=cafe_id, date=date_obj, time=time_raw).first()
        if blocked_cafe:
            return jsonify({'available': False, 'reason': 'blocked', 'message': 'The cafe is blocked for the selected date/time.'})

    existing = Booking.query.filter_by(decoration_id=decoration_id, date=date_obj, time=time_raw).first()
    if existing:
        return jsonify({'available': False, 'reason': 'booked', 'message': 'This decoration is already booked for the selected slot.'})

    return jsonify({'available': True, 'reason': 'ok', 'message': 'Available'})

@app.route('/admin/booking/get_message/<int:booking_id>/<int:template_id>')
@admin_required
def admin_get_message(booking_id, template_id):
    b = Booking.query.get_or_404(booking_id)
    t = MessageTemplate.query.get_or_404(template_id)

    mapping = {
        'name': getattr(b, 'customer_name', ''),
        'date': getattr(b, 'date', ''),
        'time': getattr(b, 'time', ''),
        'decoration': getattr(getattr(b, 'decoration', None), 'title', ''),
        'staff_number': '7624940567'
    }

    msg = t.body
    for k, v in mapping.items():
        msg = msg.replace('{' + k + '}', str(v))

    phone_raw = getattr(b, 'customer_phone', '') or ''
    phone_digits = ''.join(ch for ch in phone_raw if ch.isdigit())
    if len(phone_digits) == 10:
        phone_digits = '91' + phone_digits
    wa_link = f"https://wa.me/{phone_digits}?text={quote_plus(msg)}"
    return jsonify({'message': msg, 'wa_link': wa_link})

@app.route('/admin/blocked_slots')
@admin_required
def admin_blocked_slots_list():
    slots = BlockedSlot.query.order_by(BlockedSlot.date.desc(), BlockedSlot.time.desc()).all()
    return render_template('admin/blocked_slots_list.html', slots=slots)

@app.route('/admin/blocked_slots/new', methods=['GET','POST'])
@admin_required
def admin_blocked_slots_new():
    if request.method == 'POST':
        cafe_id = request.form.get('cafe_id') or None
        decoration_id = request.form.get('decoration_id') or None
        date_raw = request.form.get('date')
        time_raw = request.form.get('time')
        reason = request.form.get('reason')
        try:
            date_obj = datetime.strptime(date_raw, '%Y-%m-%d').date()
        except Exception:
            flash('Invalid date format', 'danger')
            return redirect(url_for('admin_blocked_slots_list'))
        slot = BlockedSlot(cafe_id=cafe_id, decoration_id=decoration_id, date=date_obj, time=time_raw, reason=reason)
        try:
            db.session.add(slot)
            db.session.commit()
            flash('Blocked slot created','success')
        except IntegrityError:
            db.session.rollback()
            flash('A block for this slot already exists','danger')
        return redirect(url_for('admin_blocked_slots_list'))
    cafes = Cafe.query.all()
    decs = Decoration.query.all()
    return render_template('admin/blocked_slots_form.html', cafes=cafes, decs=decs)

@app.route('/admin/blocked_slots/delete/<int:slot_id>', methods=['POST'])
@admin_required
def admin_blocked_slots_delete(slot_id):
    slot = BlockedSlot.query.get_or_404(slot_id)
    db.session.delete(slot)
    db.session.commit()
    flash('Blocked slot removed','info')
    return redirect(url_for('admin_blocked_slots_list'))

# =====================================================
#  PUBLIC ROUTES (home, decoration, booking)
# =====================================================

@app.route('/')
def home():
    settings = get_admin_settings()
    announcements = settings.get('announcement_message', '')

    featured_decorations = Decoration.query.filter_by(
        status='approved',
        featured=True
    ).all()

    all_decorations = Decoration.query.filter_by(status='approved').all()
    cafes = Cafe.query.filter_by(status='approved').all()

    has_contact = 'contact' in current_app.view_functions
    has_book_now = 'book_now' in current_app.view_functions

    return render_template(
        'home.html',
        decorations=all_decorations,
        featured_decorations=featured_decorations,
        cafes=cafes,
        announcements=announcements,
        has_contact=has_contact,
        has_book_now=has_book_now
    )

@app.route('/decoration/<int:id>')
def decoration_detail(id):
    decoration = Decoration.query.get_or_404(id)
    if decoration.status != 'approved':
        flash('Decoration not available', 'error')
        return redirect(url_for('home'))
    return render_template('decoration_detail.html', decoration=decoration)

@app.route('/book/<int:decoration_id>', methods=['GET', 'POST'])
def book_decoration(decoration_id):
    decoration = Decoration.query.get_or_404(decoration_id)
    if decoration.status != 'approved':
        flash('This decoration is not available for booking', 'error')
        return redirect(url_for('home'))

    form = BookingForm()
    if form.validate_on_submit():
        date_obj = form.date.data
        time_raw = form.time.data

        # Server side checks: blocked slot / existing booking
        if BlockedSlot.query.filter_by(decoration_id=decoration_id, date=date_obj, time=time_raw).first():
            flash('This time slot is blocked. Please choose another time.', 'error')
            return render_template('book.html', decoration=decoration, form=form)

        cafe_id = getattr(decoration, 'cafe_id', None)
        if cafe_id and BlockedSlot.query.filter_by(cafe_id=cafe_id, date=date_obj, time=time_raw).first():
            flash('The cafe is blocked for the selected slot. Choose another time.', 'error')
            return render_template('book.html', decoration=decoration, form=form)

        existing_booking = Booking.query.filter_by(decoration_id=decoration_id, date=date_obj, time=time_raw).first()
        if existing_booking:
            flash('This time slot is already booked. Please choose another time.', 'error')
            return render_template('book.html', decoration=decoration, form=form)

        booking = Booking(
            decoration_id=decoration_id,
            customer_name=form.name.data,
            customer_email=form.email.data,
            customer_phone=form.phone.data,
            date=date_obj,
            time=time_raw,
            guests=form.guests.data,
            notes=form.notes.data,
            total_amount=decoration.get_current_price(),
            status='pending'
        )
        try:
            db.session.add(booking)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('The slot was taken by another request just now. Please choose another time.', 'danger')
            return render_template('book.html', decoration=decoration, form=form)

        notification = Notification(
            type='booking',
            title='New Booking',
            message=f'New booking for {decoration.title} by {booking.customer_name}',
            payload=json.dumps({
                'booking_id': booking.id,
                'decoration_title': decoration.title,
                'customer_name': booking.customer_name
            })
        )
        db.session.add(notification)
        db.session.commit()

        send_admin_email('🎂 New Birthday Booking', f"""
            New Booking Received!
            Booking ID: {booking.id}
            Customer: {booking.customer_name}
            Decoration: {decoration.title}
            Date: {booking.date} at {booking.time}
        """)

        return redirect(url_for('booking_confirm', booking_id=booking.id))

    return render_template('book.html', decoration=decoration, form=form)

@app.route('/booking-confirm/<int:booking_id>')
def booking_confirm(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    cafe_phone = None
    if booking.decoration and booking.decoration.cafe:
        cafe_phone = booking.decoration.cafe.phone

    whatsapp_link = None
    if cafe_phone:
        message = (
            f"Hi, I just booked the decoration '{booking.decoration.title}' "
            f"on {booking.date.strftime('%d-%m-%Y')} at {booking.time} "
            f"for {booking.guests} guests via Birthday Cafe.\n"
            f"My name is {booking.customer_name}."
        )
        whatsapp_link = build_whatsapp_link(cafe_phone, message)

    return render_template(
        'booking_confirm.html',
        booking=booking,
        whatsapp_link=whatsapp_link
    )

# =====================================================
#  DECORATOR ROUTES
# =====================================================

@app.route('/decorator')
def decorator_portal():
    return render_template('decorator/decorator_portal.html')

@app.route('/decorator/register', methods=['GET', 'POST'])
def decorator_register():
    form = DecoratorRegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered', 'error')
            return render_template('decorator/decorator_register.html', form=form)

        decorator = User(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            company_name=form.company_name.data,
            role='decorator'
        )
        decorator.set_password(form.password.data)
        db.session.add(decorator)
        db.session.commit()

        flash('Registration submitted for admin approval', 'success')
        return redirect(url_for('decorator_login'))

    return render_template('decorator/decorator_register.html', form=form)

@app.route('/decorator/login', methods=['GET', 'POST'])
def decorator_login():
    form = DecoratorLoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(
            email=form.email.data,
            role='decorator',
            is_active=True
        ).first()
        if user and user.check_password(form.password.data):
            session['decorator_logged_in'] = True
            session['decorator_id'] = user.id
            session['decorator_name'] = user.name
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('decorator_dashboard'))
        else:
            flash('Invalid credentials or account not approved', 'error')

    return render_template('decorator/decorator_login.html', form=form)

@app.route('/decorator/dashboard')
@decorator_required
def decorator_dashboard():
    decorator_id = session.get('decorator_id')
    my_decorations = Decoration.query.filter_by(created_by=decorator_id).all()
    my_cafes = Cafe.query.filter_by(created_by=decorator_id).all()

    total_decorations = len(my_decorations)
    approved_decorations = sum(1 for d in my_decorations if d.status == 'approved')
    pending_decorations = sum(1 for d in my_decorations if d.status == 'pending')

    return render_template(
        'decorator/decorator_dashboard.html',
        decorations=my_decorations,
        cafes=my_cafes,
        total_decorations=total_decorations,
        approved_decorations=approved_decorations,
        pending_decorations=pending_decorations
    )

@app.route('/decorator/submit-cafe', methods=['GET', 'POST'])
@decorator_required
def submit_cafe():
    form = CafeSubmissionForm()
    if form.validate_on_submit():
        cafe = Cafe(
            name=form.name.data,
            area=form.area.data,
            address=form.address.data,
            phone=form.phone.data,
            email=form.email.data,
            created_by=session.get('decorator_id'),
            status='pending'
        )
        db.session.add(cafe)
        db.session.commit()
        flash('Cafe submitted for approval', 'success')
        return redirect(url_for('decorator_dashboard'))

    return render_template('decorator/submit_cafe.html', form=form)

@app.route('/submit_decoration', methods=['GET', 'POST'])
@decorator_required
def submit_decoration():
    form = DecorationSubmissionForm()

    try:
        decorator_id = session.get('decorator_id')
        if decorator_id:
            cafes_q = Cafe.query.filter_by(created_by=decorator_id).all()
        else:
            cafes_q = []

        if not cafes_q:
            cafes_q = Cafe.query.filter_by(status='approved').all()

        choices = [(c.id, f"{c.name} — {c.area}") for c in cafes_q]
        form.cafe_id.choices = choices

        if not choices:
            flash('Please add a cafe first before submitting a decoration.', 'error')
            return redirect(url_for('submit_cafe'))
    except Exception:
        form.cafe_id.choices = []

    if form.validate_on_submit():
        try:
            title = (form.title.data or '').strip()
            description = (form.description.data or '').strip()
            try:
                price = float(form.price.data or 0)
            except Exception:
                price = 0.0
            cafe_id = int(form.cafe_id.data) if form.cafe_id.data else None
            includes_raw = form.includes.data or ''
            includes = [ln.strip() for ln in includes_raw.splitlines() if ln.strip()]

            uploaded_files = []
            try:
                mf = request.files.getlist('media_files') or []
                uploaded_files.extend([f for f in mf if getattr(f, 'filename', '')])
            except Exception:
                pass

            try:
                uploaded_files.extend([f for f in request.files.getlist('photos') if getattr(f, 'filename', '')])
                uploaded_files.extend([f for f in request.files.getlist('videos') if getattr(f, 'filename', '')])
            except Exception:
                pass

            media_list = []
            if uploaded_files:
                try:
                    media_list = save_uploaded_media(uploaded_files)
                except Exception:
                    images_files = []
                    videos_files = []
                    for f in uploaded_files:
                        if not getattr(f, 'filename', ''):
                            continue
                        ext = os.path.splitext(f.filename)[1].lower().lstrip('.')
                        if ext in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
                            images_files.append(f)
                        elif ext in {'mp4', 'mov', 'avi', 'mkv', 'webm', 'ogg'}:
                            videos_files.append(f)
                    if images_files:
                        media_list.extend(save_media_files(images_files, 'image'))
                    if videos_files:
                        media_list.extend(save_media_files(videos_files, 'video'))

            if not any(m.get('type') == 'image' for m in media_list):
                flash('Please upload at least one photo of the decoration.', 'error')
                return render_template('decorator/submit_decoration.html', form=form)

            decoration = Decoration(
                title=title,
                description=description,
                price=price,
                original_price=price,
                discount_percent=0,
                themes='',
                includes=json.dumps(includes),
                images=json.dumps(media_list),
                cafe_id=cafe_id,
                status='pending',
                featured=False,
                created_by=session.get('decorator_id'),
                created_at=datetime.utcnow()
            )
            db.session.add(decoration)
            db.session.commit()

            flash('Decoration submitted successfully — pending approval.', 'success')
            return redirect(url_for('decorator_dashboard'))

        except ValueError as ve:
            flash(str(ve), 'error')
        except Exception:
            current_app.logger.exception("Error in submit_decoration")
            flash('Something went wrong while submitting. Please try again or contact admin.', 'error')

    return render_template('decorator/submit_decoration.html', form=form)

@app.route('/decorator/logout')
def decorator_logout():
    if session.get('decorator_name'):
        notification = Notification(
            type='security',
            title='Decorator Logout',
            message=f'Decorator {session.get("decorator_name")} logged out',
            payload=json.dumps({'ip': request.remote_addr})
        )
        db.session.add(notification)
        db.session.commit()

    session.pop('decorator_logged_in', None)
    session.pop('decorator_id', None)
    session.pop('decorator_name', None)

    flash('Logged out successfully', 'success')
    return redirect(url_for('decorator_portal'))

# =====================================================
#  ADMIN AUTH & DASHBOARD
# =====================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'GET':
        session.clear()
    form = AdminLoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(
            email=form.email.data,
            role='admin',
            is_active=True
        ).first()

        if user and user.check_password(form.password.data):
            session.clear()
            session['admin_logged_in'] = True
            session['admin_email'] = user.email
            session['admin_name'] = user.name
            session['admin_id'] = user.id
            session['login_time'] = datetime.utcnow().timestamp()
            session['session_id'] = secrets.token_hex(16)

            user.last_login = datetime.utcnow()
            db.session.commit()

            flash('Admin login successful', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'error')

    return render_template('admin/admin_login.html', form=form)

@app.route('/admin/logout')
def admin_logout():
    if session.get('admin_name'):
        notification = Notification(
            type='security',
            title='Admin Logout',
            message=f'Admin {session.get("admin_name")} logged out',
            payload=json.dumps({'ip': request.remote_addr})
        )
        db.session.add(notification)
        db.session.commit()

    session.clear()
    flash('Admin logged out successfully', 'success')
    return redirect(url_for('home'))

@app.route('/admin')
def admin_redirect():
    session.clear()
    session['session_reset'] = secrets.token_hex(16)
    flash('Please login to access admin panel', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_bookings = Booking.query.count()
    total_decorations = Decoration.query.count()
    total_cafes = Cafe.query.count()
    total_decorators = User.query.filter_by(role='decorator', is_active=True).count()

    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()

    pending_decorations = Decoration.query.filter_by(status='pending').count()
    pending_cafes = Cafe.query.filter_by(status='pending').count()

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_revenue = db.session.query(func.sum(Booking.total_amount)).filter(
        Booking.created_at >= thirty_days_ago
    ).scalar() or 0

    calendar_data = get_booking_calendar()

    return render_template(
        'admin/admin_dashboard.html',
        total_bookings=total_bookings,
        total_decorations=total_decorations,
        total_cafes=total_cafes,
        total_decorators=total_decorators,
        recent_bookings=recent_bookings,
        pending_decorations=pending_decorations,
        pending_cafes=pending_cafes,
        recent_revenue=recent_revenue,
        calendar_data=json.dumps(calendar_data)
    )

# =====================================================
#  ADMIN PAGES
# =====================================================

@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    templates = MessageTemplate.query.order_by(MessageTemplate.id.asc()).all()
    return render_template('admin/admin_bookings.html', bookings=bookings, templates=templates)

@app.route('/admin/decorations')
@admin_required
def admin_decorations():
    decorations = Decoration.query.all()
    return render_template('admin/admin_decorations.html', decorations=decorations)

@app.route('/admin/cafes')
@admin_required
def admin_cafes():
    cafes = Cafe.query.all()
    return render_template('admin/admin_cafes.html', cafes=cafes)

@app.route('/admin/decorators')
@admin_required
def admin_decorators():
    decorators = User.query.filter_by(role='decorator').all()
    return render_template('admin/admin_decorators.html', decorators=decorators)

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    form = AdminSettingsForm()
    settings = get_admin_settings()

    if form.validate_on_submit():
        settings_to_update = {
            'site_name': form.site_name.data,
            'admin_email': form.admin_email.data,
            'booking_advance_days': str(form.booking_advance_days.data),
            'max_guests_per_booking': str(form.max_guests_per_booking.data)
        }

        for key, value in settings_to_update.items():
            setting = AdminSettings.query.filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                setting = AdminSettings(key=key, value=value)
                db.session.add(setting)

        db.session.commit()
        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin_settings'))

    if request.method == 'GET':
        form.site_name.data = settings.get('site_name', 'Birthday Cafe')
        form.admin_email.data = settings.get('admin_email', '')
        form.booking_advance_days.data = int(settings.get('booking_advance_days', 60))
        form.max_guests_per_booking.data = int(settings.get('max_guests_per_booking', 50))

    return render_template('admin/admin_settings.html', form=form, settings=settings)

# =====================================================
#  ADMIN API (AJAX / JSON)
# =====================================================

@app.route('/api/admin/decorations/<int:id>/approve', methods=['POST'])
@admin_required
def approve_decoration(id):
    decoration = Decoration.query.get_or_404(id)
    decoration.status = 'approved'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Decoration approved'})

@app.route('/api/admin/decorations/<int:id>/reject', methods=['POST'])
@admin_required
def reject_decoration(id):
    decoration = Decoration.query.get_or_404(id)
    decoration.status = 'rejected'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Decoration rejected'})

@app.route('/api/admin/decorations/<int:id>/discount', methods=['POST'])
@admin_required
def set_decoration_discount(id):
    decoration = Decoration.query.get_or_404(id)
    form = DiscountForm()

    if form.validate():
        decoration.discount_percent = form.discount_percent.data
        decoration.featured = form.is_featured.data
        db.session.commit()
        return jsonify({'success': True, 'message': 'Discount applied'})

    return jsonify({'success': False, 'message': 'Invalid data'})

@app.route('/api/admin/cafes/<int:id>/approve', methods=['POST'])
@admin_required
def approve_cafe(id):
    cafe = Cafe.query.get_or_404(id)
    cafe.status = 'approved'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Cafe approved'})

@app.route('/api/admin/cafes/<int:id>/reject', methods=['POST'])
@admin_required
def reject_cafe(id):
    cafe = Cafe.query.get_or_404(id)
    cafe.status = 'rejected'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Cafe rejected'})

@app.route('/api/admin/announcement', methods=['POST'])
@admin_required
def update_announcement():
    message = request.json.get('message', '')
    setting = AdminSettings.query.filter_by(key='announcement_message').first()
    if setting:
        setting.value = message
    else:
        setting = AdminSettings(key='announcement_message', value=message)
        db.session.add(setting)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Announcement updated'})

@app.route('/api/admin/notifications/mark-read', methods=['POST'])
@admin_required
def mark_notifications_read():
    Notification.query.update({'read': True})
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/admin/calendar')
@admin_required
def get_calendar_data():
    calendar_data = get_booking_calendar()
    return jsonify(calendar_data)

@app.route('/api/admin/bookings/<int:id>')
@admin_required
def get_booking_details(id):
    booking = Booking.query.get_or_404(id)
    return jsonify({
        'success': True,
        'booking': {
            'customer_name': booking.customer_name,
            'customer_email': booking.customer_email,
            'customer_phone': booking.customer_phone,
            'date': booking.date.strftime('%Y-%m-%d'),
            'time': booking.time,
            'guests': booking.guests,
            'total_amount': booking.total_amount,
            'decoration_title': booking.decoration.title,
            'cafe_name': booking.decoration.cafe.name,
            'notes': booking.notes
        }
    })

@app.route('/api/admin/cafes/<int:id>')
@admin_required
def get_cafe_details(id):
    cafe = Cafe.query.get_or_404(id)
    decorations = Decoration.query.filter_by(cafe_id=cafe.id).all()
    return jsonify({
        'success': True,
        'cafe': {
            'id': cafe.id,
            'name': cafe.name,
            'area': cafe.area,
            'address': cafe.address,
            'phone': cafe.phone,
            'email': cafe.email,
            'status': cafe.status,
            'created_by': cafe.created_by_user.name if getattr(cafe, 'created_by_user', None) else 'System',
            'decoration_count': len(decorations),
            'decorations': [{'id': d.id, 'title': d.title, 'status': d.status} for d in decorations]
        }
    })

@app.route('/api/admin/decorators/<int:id>/details')
@admin_required
def get_decorator_details(id):
    decorator = User.query.filter_by(id=id, role='decorator').first_or_404()
    decorations = Decoration.query.filter_by(created_by=decorator.id).all()
    cafes = Cafe.query.filter_by(created_by=decorator.id).all()
    return jsonify({
        'success': True,
        'decorator': {
            'id': decorator.id,
            'name': decorator.name,
            'email': decorator.email,
            'phone': decorator.phone,
            'company_name': decorator.company_name,
            'is_active': decorator.is_active,
            'joined': decorator.created_at.strftime('%Y-%m-%d') if decorator.created_at else '',
            'last_login': decorator.last_login.strftime('%Y-%m-%d %H:%M') if decorator.last_login else 'Never',
            'total_cafes': len(cafes),
            'total_decorations': len(decorations),
            'approved_decorations': sum(1 for d in decorations if d.status == 'approved'),
            'pending_decorations': sum(1 for d in decorations if d.status == 'pending'),
        }
    })

@app.route('/api/admin/bookings/<int:id>/status', methods=['POST'])
@admin_required
def update_booking_status(id):
    booking = Booking.query.get_or_404(id)
    new_status = request.json.get('status')
    booking.status = new_status
    db.session.commit()
    return jsonify({'success': True, 'message': f'Booking status updated to {new_status}'})

@app.route('/api/admin/decorators/<int:id>/toggle', methods=['POST'])
@admin_required
def toggle_decorator(id):
    decorator = User.query.get_or_404(id)
    decorator.is_active = request.json.get('active', False)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Decorator status updated'})

@app.route('/api/admin/decorators/<int:id>', methods=['DELETE'])
@admin_required
def delete_decorator(id):
    decorator = User.query.get_or_404(id)
    db.session.delete(decorator)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Decorator deleted'})

@app.route('/api/admin/decorations/<int:id>/toggle-feature', methods=['POST'])
@admin_required
def toggle_decoration_feature(id):
    decoration = Decoration.query.get_or_404(id)
    decoration.featured = not decoration.featured
    db.session.commit()
    return jsonify({'success': True, 'message': 'Feature status updated'})

# =====================================================
#  DEBUG ROUTES
# =====================================================

@app.route('/test-session')
def test_session():
    session['test'] = 'hello'
    return f"Session set! Current session: {dict(session)}"

# =====================================================
#  APP ENTRY POINT
# =====================================================

@app.route('/health')
def health_check():
    """Lightweight endpoint for uptime monitors / deployment platforms."""
    try:
        db.session.execute(db.select(1))
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({
        'status': 'ok' if db_ok else 'degraded',
        'database': 'connected' if db_ok else 'unavailable',
        'time': datetime.utcnow().isoformat() + 'Z'
    }), (200 if db_ok else 503)


if __name__ == '__main__':
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    sqlite_path = None
    if db_uri.startswith('sqlite:///'):
        sqlite_path = db_uri.replace('sqlite:///', '', 1)
        is_new_db = not os.path.exists(sqlite_path)
    else:
        is_new_db = os.environ.get('FORCE_CREATE_AND_SEED', 'false').lower() == 'true'

    with app.app_context():
        # create_tables() is safe to call every time (create_all is a no-op
        # for tables that already exist). seed_data() is also idempotent —
        # it only creates the admin/demo rows that don't already exist,
        # and repairs the admin password if it can't be verified. Running
        # this on every startup (not just when the db file is brand new)
        # means a corrupted or unverifiable admin login self-heals instead
        # of requiring you to delete the database file by hand.
        print("Checking database..." if not is_new_db else "Database not found. Creating and seeding database...")
        create_tables()
        seed_data()


    print("\n🎉 Enhanced Birthday Cafe Platform Started!")
    print("📍 Main Site: http://localhost:5000")
    print("🎨 Decorator Portal: http://localhost:5000/decorator")
    print("⚙️  Admin Panel: http://localhost:5000/admin/login")
    print("\n🔑 Admin Login: admin@birthdaycafe.com / Admin@123!")

    app.run(debug=app.config.get('DEBUG', True))

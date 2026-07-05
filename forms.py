from datetime import date
import re

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms import (
    StringField, EmailField, TextAreaField, IntegerField,
    DateField, SelectField, FloatField, PasswordField,
    BooleanField, SubmitField, MultipleFileField
)
from wtforms.validators import (
    DataRequired, NumberRange, ValidationError,
    Optional, Length
)


# =====================================================
#  CUSTOM VALIDATORS
# =====================================================

def phone_validator(form, field):
    """
    Validate phone numbers in a simple international format.
    Allows:
    - Optional '+' at start
    - Optional '1' (country code style)
    - 9 to 15 digits total
    Example: +919876543210
    """
    if field.data:
        phone_pattern = re.compile(r'^\+?1?\d{9,15}$')
        if not phone_pattern.match(field.data):
            raise ValidationError('Invalid phone number format. Use something like +919876543210')


def future_date_validator(form, field):
    """
    Ensure date is today or in the future.
    Used for booking dates and promotions.
    """
    if field.data and field.data < date.today():
        raise ValidationError('Date cannot be in the past')


def discount_validator(form, field):
    """
    Ensure discount is between 0 and 100.
    Used in PromotionForm and DiscountForm.
    """
    if field.data is not None and (field.data < 0 or field.data > 100):
        raise ValidationError('Discount must be between 0 and 100 percent')


# =====================================================
#  USER FORMS (PUBLIC SIDE)
# =====================================================

class BookingForm(FlaskForm):
    """
    Booking form used on:
    - /book/<decoration_id>

    app.py expects:
    - name, email, phone, date, time, guests, notes, send_whatsapp
    """
    name = StringField(
        'Name',
        validators=[DataRequired(), Length(min=2, max=100)]
    )
    email = EmailField(
        'Email',
        validators=[DataRequired()]
    )
    phone = StringField(
        'Phone',
        validators=[DataRequired(), phone_validator]
    )
    date = DateField(
        'Date',
        validators=[DataRequired(), future_date_validator]
    )
    time = SelectField(
        'Time',
        choices=[
            ('10:00', '10:00 AM'), ('11:00', '11:00 AM'),
            ('12:00', '12:00 PM'), ('13:00', '1:00 PM'),
            ('14:00', '2:00 PM'), ('15:00', '3:00 PM'),
            ('16:00', '4:00 PM'), ('17:00', '5:00 PM'),
            ('18:00', '6:00 PM')
        ],
        validators=[DataRequired()]
    )
    guests = IntegerField(
        'Number of Guests',
        validators=[DataRequired(), NumberRange(min=1, max=50)]
    )
    notes = TextAreaField('Special Requests')
    send_whatsapp = BooleanField('Send WhatsApp confirmation')
    submit = SubmitField('Book Now')


# =====================================================
#  DECORATOR FORMS
# =====================================================

class CafeSubmissionForm(FlaskForm):
    """
    Used in:
    - /decorator/submit-cafe

    app.py expects:
    - name, area, address, phone, email
    """
    name = StringField(
        'Cafe Name',
        validators=[DataRequired(), Length(min=2, max=100)]
    )
    area = StringField(
        'Area/Locality',
        validators=[DataRequired()]
    )
    address = TextAreaField(
        'Full Address',
        validators=[DataRequired()]
    )
    phone = StringField(
        'Cafe Phone',
        validators=[Optional(), phone_validator]
    )
    email = EmailField(
        'Cafe Email',
        validators=[Optional()]
    )
    submit = SubmitField('Submit Cafe')


class DecorationSubmissionForm(FlaskForm):
    """
    Used in:
    - /decorator/submit-decoration

    app.py expects:
    - title, price, description, includes, cafe_id, media_files

    'media_files' supports images and videos.
    """
    title = StringField(
        'Decoration Theme Title',
        validators=[DataRequired(), Length(min=5, max=200)]
    )
    price = FloatField(
        'Price (₹)',
        validators=[DataRequired(), NumberRange(min=0)]
    )
    description = TextAreaField(
        'Description',
        validators=[DataRequired()]
    )
    includes = TextAreaField(
        'Included Items (one per line)',
        validators=[DataRequired()]
    )
    cafe_id = SelectField(
        'Cafe Location',
        coerce=int,
        validators=[DataRequired()]
    )

    # Media files for images and videos
    media_files = MultipleFileField(
        'Upload Media Files (Max 5 files - Images & Videos)',
        validators=[
            FileAllowed(
                ['jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'mov', 'avi', 'mkv'],
                'Only images (JPG, PNG, GIF, WebP) and videos (MP4, MOV, AVI, MKV) are allowed!'
            )
        ]
    )

    submit = SubmitField('Submit Decoration')


class DecoratorRegistrationForm(FlaskForm):
    """
    Used in:
    - /decorator/register
    """
    name = StringField(
        'Your Name',
        validators=[DataRequired(), Length(min=2, max=100)]
    )
    email = EmailField(
        'Email',
        validators=[DataRequired()]
    )
    phone = StringField(
        'Phone',
        validators=[DataRequired(), phone_validator]
    )
    password = PasswordField(
        'Password',
        validators=[DataRequired(), Length(min=6)]
    )
    company_name = StringField('Company Name (Optional)')
    submit = SubmitField('Register')


class DecoratorLoginForm(FlaskForm):
    """
    Used in:
    - /decorator/login
    """
    email = EmailField(
        'Email',
        validators=[DataRequired()]
    )
    password = PasswordField(
        'Password',
        validators=[DataRequired()]
    )
    submit = SubmitField('Login')


# =====================================================
#  ADMIN FORMS
# =====================================================

class AdminLoginForm(FlaskForm):
    """
    Used in:
    - /admin/login
    """
    email = EmailField(
        'Email',
        validators=[DataRequired()]
    )
    password = PasswordField(
        'Password',
        validators=[DataRequired()]
    )
    submit = SubmitField('Login')


class AdminSettingsForm(FlaskForm):
    """
    Used in:
    - /admin/settings

    Fields match the keys in AdminSettings:
    - site_name
    - admin_email
    - booking_advance_days
    - max_guests_per_booking
    """
    site_name = StringField(
        'Site Name',
        validators=[DataRequired()]
    )
    admin_email = EmailField(
        'Admin Email',
        validators=[DataRequired()]
    )
    booking_advance_days = IntegerField(
        'Booking Advance Days',
        validators=[DataRequired(), NumberRange(min=1, max=365)]
    )
    max_guests_per_booking = IntegerField(
        'Max Guests per Booking',
        validators=[DataRequired(), NumberRange(min=1, max=100)]
    )
    submit = SubmitField('Save Settings')


class PromotionForm(FlaskForm):
    """
    Not used in app.py right now,
    but ready if you add a promotions page in admin later.
    """
    title = StringField(
        'Promotion Title',
        validators=[DataRequired()]
    )
    description = TextAreaField('Description')
    discount_percent = IntegerField(
        'Discount Percentage',
        validators=[Optional(), NumberRange(min=0, max=100), discount_validator]
    )
    is_active = BooleanField('Active', default=True)
    start_date = DateField(
        'Start Date',
        validators=[Optional(), future_date_validator]
    )
    end_date = DateField(
        'End Date',
        validators=[Optional()]
    )
    submit = SubmitField('Create Promotion')


class DiscountForm(FlaskForm):
    """
    Used with AJAX endpoints to set discount & feature flag:
    - /api/admin/decorations/<id>/discount
    - /api/admin/decorations/<id>/toggle-feature
    """
    discount_percent = IntegerField(
        'Discount Percentage',
        validators=[Optional(), NumberRange(min=0, max=100), discount_validator]
    )
    is_featured = BooleanField('Feature this decoration', default=False)
    submit = SubmitField('Apply Discount')

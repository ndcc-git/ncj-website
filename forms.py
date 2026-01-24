from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, RadioField, TextAreaField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Regexp, Optional, EqualTo, URL
from flask_wtf.file import FileField, FileAllowed
from wtforms.widgets import TextArea

class RegistrationForm(FlaskForm):
    """Registration form for participants"""
    full_name = StringField('Full Name', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ])
    
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=100)
    ])
    
    institution = StringField('Institution', validators=[
        DataRequired(),
        Length(min=2, max=200)
    ])
    
    segment = SelectField('Segment', choices=[], validators=[DataRequired()])
    
    category = RadioField('Category', choices=[
        ('P', 'Primary (P)'),
        ('S', 'School (S)'),
        ('HS', 'High School (HS)'),
        ('A', 'Adult (A)')
    ], validators=[Optional()])

    submission_link = StringField('Submission Link', validators=[
    Optional(),
    URL(message="Enter a valid URL")
    ])


    ca_ref = StringField('CA Reference', validators=[
        Length(min=2),
        Optional()
    ])
    
    bkash_number = StringField('Bkash Number', validators=[
        DataRequired(),
        Regexp(r'^01[3-9]\d{8}$', message='Enter a valid Bangladesh mobile number')
    ])
    
    transaction_id = StringField('Transaction ID', validators=[
        DataRequired(),
        Length(min=5, max=50)
    ])
    submit = SubmitField('Register')
    # Hidden fields for bot prevention
    honeypot = StringField('Honeypot', validators=[Optional()])
    timestamp = HiddenField()

class CARegistrationForm(FlaskForm):
    """CA Registration Form"""
    full_name = StringField('Full Name', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ])
    
    institution = StringField('Institution/University', validators=[
        DataRequired(),
        Length(min=2, max=200)
    ])
    
    class_info = StringField('Class/Year', validators=[
        DataRequired(),
        Length(min=1, max=50)
    ])
    
    phone = StringField('Phone Number', validators=[
        DataRequired(),
        Regexp(r'^01[3-9]\d{8}$', message='Enter a valid Bangladesh mobile number')
    ])
    
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=100)
    ])
    
    why_ca = TextAreaField('Why do you want to be a CA?', validators=[
        DataRequired(),
        Length(min=20, max=1000)
    ], widget=TextArea(), render_kw={"rows": 6})
    
    profile_picture = FileField('Profile Picture (Optional)', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only! (jpg, jpeg, png)')
    ])
    
    submit = SubmitField('Apply as CA')


class AdminLoginForm(FlaskForm):
    """Admin login form"""
    email = StringField('Email', validators=[
        DataRequired(),
        Email()
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired()
    ])
    submit = SubmitField('Login')


class ContactForm(FlaskForm):
    """Contact form for inquiries"""
    name = StringField('Your Name', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ])
    
    institution = StringField('Institution/Organization', validators=[
        DataRequired(),
        Length(min=2, max=200)
    ])
    
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=100)
    ])
    
    message = TextAreaField('Message', validators=[
        DataRequired(),
        Length(min=10, max=2000)
    ], widget=TextArea(), render_kw={"rows": 6})
    
    submit = SubmitField('Send Message')

class AdminUserForm(FlaskForm):
    """Form for adding admin users"""
    name = StringField('Full Name', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ])
    
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=100)
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters')
    ])
    
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    
    submit = SubmitField('Add Admin User')
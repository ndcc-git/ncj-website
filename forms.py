from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, RadioField, BooleanField, TextAreaField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Regexp, Optional
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
    ], validators=[DataRequired()])

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

class EmailForm(FlaskForm):
    """Email form for admin"""
    subject = StringField('Subject', validators=[
        DataRequired(),
        Length(min=2, max=200)
    ])
    
    message = TextAreaField('Message', validators=[
        DataRequired(),
        Length(min=10, max=5000)
    ], widget=TextArea(), render_kw={"rows": 10})
    
    segment = SelectField('Segment (Optional)', choices=[], validators=[Optional()])
    category = SelectField('Category (Optional)', choices=[
        ('', 'All Categories'),
        ('P', 'Primary'),
        ('S', 'School'),
        ('HS', 'High School'),
        ('A', 'Adult')
    ], validators=[Optional()])
    
    verified_only = BooleanField('Send to verified registrations only')
    
    submit = SubmitField('Send Email')
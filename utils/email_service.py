import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from threading import Thread

def send_email(to_email, subject, body, is_html=False):
    """Send an email using SMTP"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = to_email
        
        if is_html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))
        
        # with smtplib.SMTP(current_app.config['MAIL_SERVER'],
        #                  current_app.config['MAIL_PORT']) as server:
        #     server.starttls()
        #     server.login(current_app.config['MAIL_USERNAME'],
        #                 current_app.config['MAIL_PASSWORD'])
        #     server.send_message(msg)

        with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login("api", current_app.config['MAIL_API'])
            server.send_message(msg)

        
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_verification_email(registration):
    """Send verification email to a participant"""
    subject = "Successful Registration at 10th NCJ"
    body = f"""
    Dear {registration['full_name']},

    This is your confirmation regarding your registration in {registration['segment_name']} at 9th National Cultural Jubilation.
    Please show this email upon entering Notre Dame College, Dhaka campus on the event day.
    Your confirmation code for the event is below:
    {registration['_id']}
    
    Kindly visit our facebook page for the schedule and ensure timely attendance at the fest.
    Also read rules and regulation for every event from our website.


    Best Regards,
    Notre Dame Cultural Club
    """
    return send_email(registration['email'], subject, body, is_html=False)

def send_bulk_emails(recipients, subject=None):
    """Send emails to multiple recipients in bulk"""
    if not recipients:
        return False
    
    success_count = 0
    
    for recipient in recipients:
        email_subject = "Successful Registration at 10th NCJ"
        email_body = f"""
        Dear {recipient.get('full_name', 'Participant')},
        
        This is your confirmation regarding your registration in {recipient['segment_name']} at 9th National Cultural Jubilation.
        Please show this email upon entering Notre Dame College, Dhaka campus on the event day.
        Your confirmation code for the event is below:
        {recipient['_id']}
        
        Kindly visit our facebook page for the schedule and ensure timely attendance at the fest.
        Also read rules and regulation for every event from our website.


        Best Regards,
        Notre Dame Cultural Club
        """
        
        if send_email(recipient['email'], email_subject, email_body):
            success_count += 1
    
    return success_count > 0

def send_email_async(app, to_email, subject, body):
    """Send email asynchronously"""
    with app.app_context():
        send_email(to_email, subject, body)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from threading import Thread
import qrcode
from io import BytesIO
from email.mime.image import MIMEImage

def send_email(to_email, subject, body, is_html, buffer=None):
    """Send an email using SMTP"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = to_email
        
        with open("logo-bangla.png", "rb") as f:
            logo = MIMEImage(f.read())
            logo.add_header('Content-ID', '<logo>')
            msg.attach(logo)
        if buffer:
            image = MIMEImage(buffer.read())
            image.add_header('Content-ID', '<qr_code>')
            msg.attach(image)
            
        if is_html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(current_app.config['MAIL_SERVER'],
                         current_app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(current_app.config['MAIL_USERNAME'],
                        current_app.config['MAIL_PASSWORD'])
            server.send_message(msg)
            
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_reg_verification_email(registration):
    """Send verification email to a participant"""
    qr = qrcode.make(registration['_id'])
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)
    
    subject = "১০ম  ন্যাশনাল কালচারাল জুবিলেশন-এ রেজিস্ট্রেশনের জন্য ধন্যবাদ"
    body = f"""
    <!DOCTYPE html>
    <html lang="bn">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>১০ম  ন্যাশনাল কালচারাল জুবিলেশন-এ রেজিস্ট্রেশনের জন্য ধন্যবাদ!</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Baloo+Da+2:wght@400..800&display=swap" rel="stylesheet">

    </head>
    <body style="margin:0; padding:0; font-family: 'Baloo Da 2', sans-serif;">

    <div style="max-width:600px; margin:30px auto; background:#ffffff;">

        <!-- Logo -->
        <div style="text-align:center; padding:20px; background:#734610;">
            <img src="cid:logo" width="150">
        </div>

        <!-- Heading -->
        <div style="background:#D9A23D; padding:30px 20px; text-align:center;">
            <h1 style="margin:0; color:#261515; font-size:24px;">
                ৯ম ন্যাশনাল কালচারাল জুবিলেশন-এ রেজিস্ট্রেশনের জন্য ধন্যবাদ!
            </h1>
        </div>

        <!-- Event Strip -->
        <div style="background:#734610; padding:15px; text-align:center;">
            <span style="color:#ffffff; font-weight:bold; letter-spacing:1px;">
                {registration['segment_name']} ইভেন্ট
            </span>
        </div>

        <!-- Content -->
        <div style="padding:30px; color:#261515; font-size:15px; line-height:1.7;">

            <p>প্রিয় <strong>{registration['full_name']}</strong>,</p>

            <p>
                <strong>{registration['segment_name']}</strong> ইভেন্টে আপনার রেজিস্ট্রেশন সফল হয়েছে।
                অনুষ্ঠান দিনে নটর ডেম কলেজ, ঢাকা ক্যাম্পাসে প্রবেশের সময়
                এই ইমেইলটি প্রদর্শন করবেন।
                আপনার কোড নিচে দেওয়া হলো:
            </p>

            <!-- Code Box -->
            <div style="text-align:center; margin:25px 0;">
                <div style="display:inline-block; background:#D9C24E; padding:15px 30px; border-radius:8px;">
                    <span id="confirmCode" style="font-size:22px; font-weight:bold; color:#402B12;">
                        {registration['_id']}
                    </span>
                </div>
            </div>

            <!-- QR Code -->
            <div style="text-align:center; margin-bottom:25px;">
                <img src="cid:qr_code" width="150" style="display:block; margin:0 auto;">
                <p style="font-size:13px; color:#734610; margin-top:10px;">
                    প্রবেশের সময় এই QR কোড স্ক্যান করা হবে
                </p>
            </div>


            <p>
                সময়সূচি জানতে আমাদের 
                <a target="_blank" href="https://www.facebook.com/NDCCDhaka" style="color:#734610;">ফেসবুক পেজ</a> ভিজিট করুন।
            </p>

            <p>
                প্রতিটি ইভেন্টের নিয়মাবলি জানতে আমাদের
                <a target="_blank" href="ncj.ndcc.net" style="color:#734610;">ওয়েবসাইট</a> দেখুন।
            </p>

            <p style="margin-top:30px;">
                শুভেচ্ছান্তে,<br>
                <strong style="font-size:18px;">নটর ডেম কালচারাল ক্লাব</strong>
            </p>

        </div>

        <!-- Footer -->
        <div style="background:#261515; color:#ffffff; text-align:center; padding:20px; font-size:13px;">
            © ২০২৬ NDCC, সর্বস্বত্ব সংরক্ষিত<br>
            যোগাযোগ: {current_app.config['MAIL_DEFAULT_SENDER']}
        </div>

    </div>

    </body>
    </html>
    
    """
    
    return send_email(registration['email'], subject, body, is_html=True, buffer=buffer)

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


def send_ca_approval_email(ca_registration):
    """Send approval email to CA"""
    subject = "১০ম ন্যাশনাল কালচারাল জুবিলেশন-এ সিএ রেজিস্ট্রেশনের জন্য ধন্যবাদ!"
    body = f"""
    <!DOCTYPE html>
    <html lang="bn">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>১০ম ন্যাশনাল কালচারাল জুবিলেশন-এ সিএ রেজিস্ট্রেশনের জন্য ধন্যবাদ!</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Baloo+Da+2:wght@400..800&display=swap" rel="stylesheet">

    </head>
    <body style="margin:0; padding:0; font-family: 'Baloo Da 2', sans-serif;">

    <div style="max-width:600px; margin:30px auto; background:#ffffff;">

        <!-- Logo -->
        <div style="text-align:center; padding:20px; background:#734610;">
            <img src="cid:logo" width="150">
        </div>

        <!-- Heading -->
        <div style="background:#D9A23D; padding:30px 20px; text-align:center;">
            <h1 style="margin:0; color:#261515; font-size:24px;">
                ১০ম ন্যাশনাল কালচারাল জুবিলেশন-এ সিএ রেজিস্ট্রেশনের জন্য ধন্যবাদ!
            </h1>
        </div>

        <!-- Content -->
        <div style="padding:30px; color:#261515; font-size:15px; line-height:1.7;">

            <p>প্রিয় <strong>{ca_registration['full_name']}</strong>,</p>

            <p>
                ১০ম ন্যাশনাল কালচারাল জুবিলেশন-এ ক্যামপাস অ্যাম্বাসেডর হিসেবে নিবন্ধনের জন্য আপনাকে আন্তরিক অভিনন্দন ও ধন্যবাদ।
                আপনার নিবন্ধন সফলভাবে সম্পন্ন হয়েছে। আপনার নির্ধারিত সিএ কোড নিচে প্রদান করা হলো:
            </p>

            <!-- Code Box -->
            <div style="text-align:center; margin:25px 0;">
                <div style="display:inline-block; background:#D9C24E; padding:15px 30px; border-radius:8px;">
                    <span id="confirmCode" style="font-size:22px; font-weight:bold; color:#402B12;">
                        {ca_registration['ca_code']}
                    </span>
                </div>
            </div>

            <p>
                অনুগ্রহ করে এই কোডটি সংরক্ষণ করুন।  রেজিস্ট্রেশনের সময় কোডটি ব্যবহার করতে উৎসাহিত করুন। আপনার সক্রিয় অংশগ্রহণ আমাদের আয়োজনকে আরও সফল করে তুলবে — এই প্রত্যাশায়।
            </p>

            <p>
                সময়সূচি জানতে আমাদের 
                <a target="_blank" href="https://www.facebook.com/NDCCDhaka" style="color:#734610;">ফেসবুক পেজ</a> ভিজিট করুন।
            </p>

            <p>
                প্রতিটি ইভেন্টের নিয়মাবলি জানতে আমাদের
                <a target="_blank" href="ncj.ndcc.net" style="color:#734610;">ওয়েবসাইট</a> দেখুন।
            </p>

            <p style="margin-top:30px;">
                শুভেচ্ছান্তে,<br>
                <strong style="font-size:18px;">নটর ডেম কালচারাল ক্লাব</strong>
            </p>

        </div>

        <!-- Footer -->
        <div style="background:#261515; color:#ffffff; text-align:center; padding:20px; font-size:13px;">
            © ২০২৬ NDCC, সর্বস্বত্ব সংরক্ষিত<br>
            যোগাযোগ: ndcc.it.dept@gmail.com
        </div>

    </div>

    </body>
    </html>

    """
    
    return send_email(ca_registration['email'], subject, body, is_html=True, buffer=None)
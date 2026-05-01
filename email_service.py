import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_reset_code(to_email: str, code: str) -> bool:
    user = os.environ.get('MAILTRAP_USER', '').strip()
    pwd  = os.environ.get('MAILTRAP_PASS', '').strip()

    if not user or not pwd:
        print("[EMAIL] ERROR: MAILTRAP_USER or MAILTRAP_PASS not set in .env")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'InterviewAI — Your Verification Code'
    msg['From']    = 'InterviewAI <noreply@interviewai.com>'
    msg['To']      = to_email

    html = f"""
    <div style="font-family:Arial,sans-serif;background:#f1f5f9;padding:40px 0;">
      <div style="max-width:480px;margin:auto;background:#0d1420;border-radius:16px;padding:40px;border:1px solid #1e3a5f;">
        <h2 style="color:#38bdf8;margin:0 0 8px;">Verification Code</h2>
        <p style="color:#94a3b8;margin:0 0 28px;">
          Use the code below for your <strong style="color:#e2e8f0;">InterviewAI</strong> account.
          Valid for <strong style="color:#38bdf8;">10 minutes</strong>.
        </p>
        <div style="background:#080c14;border:2px solid #38bdf8;border-radius:12px;padding:28px;text-align:center;">
          <span style="font-family:'Courier New',monospace;font-size:2.4rem;font-weight:700;color:#38bdf8;letter-spacing:12px;">{code}</span>
        </div>
        <p style="color:#475569;font-size:0.8rem;margin-top:24px;">If you didn't request this, ignore this email.</p>
      </div>
    </div>"""

    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP('sandbox.smtp.mailtrap.io', 2525) as smtp:
            smtp.starttls()
            smtp.login(user, pwd)
            smtp.sendmail(msg['From'], to_email, msg.as_string())
        print(f"[EMAIL] Sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL] Error: {e}")
        return False

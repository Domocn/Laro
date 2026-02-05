"""
Email Service - Handles all email notifications
Supports SMTP and Resend API
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Configuration
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() == "true"
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "noreply@laro.food")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
APP_NAME = "Laro"
APP_URL = os.environ.get("OAUTH_REDIRECT_BASE_URL", "http://localhost:3001")


def is_email_configured() -> bool:
    """Check if email is properly configured"""
    if not EMAIL_ENABLED:
        return False
    if RESEND_API_KEY:
        return True
    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
        return True
    return False


async def send_email(to: str, subject: str, html_body: str, text_body: str = None) -> bool:
    """Send an email using configured provider"""
    if not is_email_configured():
        logger.info(f"Email not configured - would send to {to}: {subject}")
        return False

    try:
        if RESEND_API_KEY:
            return await send_via_resend(to, subject, html_body)
        else:
            return await send_via_smtp(to, subject, html_body, text_body)
    except Exception as e:
        logger.error(f"Error sending email to {to}: {e}", exc_info=True)
        return False


async def send_via_resend(to: str, subject: str, html_body: str) -> bool:
    """Send email via Resend API"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": f"{APP_NAME} <{SMTP_FROM_EMAIL}>",
                "to": [to],
                "subject": subject,
                "html": html_body
            }
        )
        return response.status_code == 200


async def send_via_smtp(to: str, subject: str, html_body: str, text_body: str = None) -> bool:
    """Send email via SMTP"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{APP_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to
    
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL, to, msg.as_string())
    
    return True


# =============================================================================
# EMAIL TEMPLATES
# =============================================================================

def get_base_template(content: str) -> str:
    """Wrap content in base email template"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ text-align: center; padding: 20px 0; border-bottom: 1px solid #eee; }}
        .logo {{ font-size: 24px; font-weight: bold; color: #6B8E6B; }}
        .content {{ padding: 30px 0; }}
        .button {{ display: inline-block; padding: 12px 24px; background: #6B8E6B; color: white; text-decoration: none; border-radius: 25px; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 20px 0; border-top: 1px solid #eee; color: #666; font-size: 12px; }}
        .alert-box {{ background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .info-box {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        code {{ background: #f1f1f1; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🥑 {APP_NAME}</div>
        </div>
        <div class="content">
            {content}
        </div>
        <div class="footer">
            <p>This email was sent from {APP_NAME}</p>
            <p><a href="{APP_URL}">{APP_URL}</a></p>
        </div>
    </div>
</body>
</html>
"""


async def send_password_reset_email(to: str, token: str) -> bool:
    """Send password reset email"""
    reset_url = f"{APP_URL}/#/reset-password?token={token}"
    
    content = f"""
    <h2>Reset Your Password</h2>
    <p>We received a request to reset your password. Click the button below to create a new password:</p>
    <p style="text-align: center;">
        <a href="{reset_url}" class="button">Reset Password</a>
    </p>
    <p>Or copy this link:</p>
    <p><code>{reset_url}</code></p>
    <div class="alert-box">
        <strong>⏰ This link expires in 1 hour.</strong><br>
        If you didn't request this, you can safely ignore this email.
    </div>
    """
    
    return await send_email(
        to=to,
        subject=f"[{APP_NAME}] Reset Your Password",
        html_body=get_base_template(content)
    )


async def send_new_login_notification(
    to: str, 
    device: str, 
    ip_address: str, 
    location: str = "Unknown",
    timestamp: datetime = None
) -> bool:
    """Send notification about new device login"""
    timestamp = timestamp or datetime.now(timezone.utc)
    time_str = timestamp.strftime("%B %d, %Y at %I:%M %p UTC")
    
    content = f"""
    <h2>New Sign-In to Your Account</h2>
    <p>We noticed a new sign-in to your {APP_NAME} account:</p>
    <div class="info-box">
        <p><strong>Device:</strong> {device}</p>
        <p><strong>IP Address:</strong> {ip_address}</p>
        <p><strong>Location:</strong> {location}</p>
        <p><strong>Time:</strong> {time_str}</p>
    </div>
    <p>If this was you, no action is needed.</p>
    <div class="alert-box">
        <strong>⚠️ Wasn't you?</strong><br>
        If you didn't sign in, your account may be compromised. Please:
        <ol>
            <li>Change your password immediately</li>
            <li>Enable two-factor authentication</li>
            <li>Review your active sessions</li>
        </ol>
        <p style="text-align: center; margin-top: 15px;">
            <a href="{APP_URL}/#/settings/security" class="button">Secure My Account</a>
        </p>
    </div>
    """
    
    return await send_email(
        to=to,
        subject=f"[{APP_NAME}] New sign-in from {device}",
        html_body=get_base_template(content)
    )


async def send_password_changed_notification(to: str) -> bool:
    """Send notification that password was changed"""
    content = f"""
    <h2>Your Password Was Changed</h2>
    <p>Your {APP_NAME} account password was recently changed.</p>
    <div class="info-box">
        <p><strong>Time:</strong> {datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")}</p>
    </div>
    <div class="alert-box">
        <strong>⚠️ Didn't change your password?</strong><br>
        If you didn't make this change, your account may be compromised.
        <p style="text-align: center; margin-top: 15px;">
            <a href="{APP_URL}/#/forgot-password" class="button">Reset Password Now</a>
        </p>
    </div>
    """
    
    return await send_email(
        to=to,
        subject=f"[{APP_NAME}] Your password was changed",
        html_body=get_base_template(content)
    )


async def send_2fa_enabled_notification(to: str) -> bool:
    """Send notification that 2FA was enabled"""
    content = f"""
    <h2>Two-Factor Authentication Enabled</h2>
    <p>Two-factor authentication has been enabled on your {APP_NAME} account. 🎉</p>
    <div class="info-box">
        <p>Your account is now more secure. You'll need your authenticator app each time you sign in.</p>
    </div>
    <p><strong>Make sure to save your backup codes!</strong> You'll need them if you lose access to your authenticator app.</p>
    """
    
    return await send_email(
        to=to,
        subject=f"[{APP_NAME}] 2FA enabled on your account",
        html_body=get_base_template(content)
    )


async def send_2fa_disabled_notification(to: str) -> bool:
    """Send notification that 2FA was disabled"""
    content = f"""
    <h2>Two-Factor Authentication Disabled</h2>
    <p>Two-factor authentication has been disabled on your {APP_NAME} account.</p>
    <div class="alert-box">
        <strong>⚠️ Your account is less secure</strong><br>
        We recommend keeping 2FA enabled for maximum security.
        <p style="text-align: center; margin-top: 15px;">
            <a href="{APP_URL}/#/settings/security" class="button">Re-enable 2FA</a>
        </p>
    </div>
    <p>If you didn't make this change, please secure your account immediately.</p>
    """
    
    return await send_email(
        to=to,
        subject=f"[{APP_NAME}] 2FA disabled on your account",
        html_body=get_base_template(content)
    )


async def send_account_locked_notification(to: str, unlock_minutes: int) -> bool:
    """Send notification that account was locked"""
    content = f"""
    <h2>Account Temporarily Locked</h2>
    <p>Your {APP_NAME} account has been temporarily locked due to multiple failed login attempts.</p>
    <div class="alert-box">
        <strong>⏰ Your account will unlock in {unlock_minutes} minutes.</strong>
    </div>
    <p>If this was you, please wait and try again. If you've forgotten your password:</p>
    <p style="text-align: center;">
        <a href="{APP_URL}/#/forgot-password" class="button">Reset Password</a>
    </p>
    <p>If you didn't try to sign in, someone else may be trying to access your account. Consider:</p>
    <ul>
        <li>Changing your password after the lockout</li>
        <li>Enabling two-factor authentication</li>
    </ul>
    """

    return await send_email(
        to=to,
        subject=f"[{APP_NAME}] Account locked - suspicious activity",
        html_body=get_base_template(content)
    )


async def send_beta_invite_email(to: str, play_store_url: str) -> bool:
    """Send beta invite email with Google Play download link"""
    content = f"""
    <h2>You're Invited to the Laro Beta!</h2>
    <p>Great news! You've been accepted into the {APP_NAME} Android beta. 🎉</p>
    <div class="info-box">
        <p>As a beta tester, you'll get early access to new features and help shape the future of {APP_NAME}.</p>
    </div>
    <p style="text-align: center;">
        <a href="{play_store_url}" class="button">Download from Google Play</a>
    </p>
    <p><strong>How to get started:</strong></p>
    <ol>
        <li>Click the button above to open Google Play</li>
        <li>Accept the beta tester invitation</li>
        <li>Install the {APP_NAME} app</li>
        <li>Sign in with this email address</li>
    </ol>
    <div class="alert-box">
        <strong>🐛 Found a bug?</strong><br>
        We'd love your feedback! You can report issues directly through the app or reply to this email.
    </div>
    <p>Thanks for being an early supporter!</p>
    """

    return await send_email(
        to=to,
        subject=f"[{APP_NAME}] You're in! Download the beta app",
        html_body=get_base_template(content)
    )

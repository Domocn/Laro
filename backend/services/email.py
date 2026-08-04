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
# Logo URL for emails
LOGO_URL = os.environ.get("EMAIL_LOGO_URL", "https://www.laro.food/laro-banner.png")

# Featured free recipe for welcome emails
FREE_RECIPE_SOURCE = os.environ.get("FREE_RECIPE_SOURCE", "https://pinchofnom.com/recipes/hunters-chicken/")
FREE_RECIPE_NAME = os.environ.get("FREE_RECIPE_NAME", "Hunters Chicken")
# Import link that opens Laro with the recipe URL pre-filled
import urllib.parse
FREE_RECIPE_URL = f"{APP_URL}/#/recipes/import?url={urllib.parse.quote(FREE_RECIPE_SOURCE)}"

# Cooking pro tips - randomly selected for email footers
import random
COOKING_TIPS = [
    "Salt your pasta water until it tastes like the sea 🧂🌊",
    "Let meat rest after cooking — patience makes it juicier 🥩",
    "Mise en place: prep all ingredients before you start cooking 🥕🧄",
    "A sharp knife is safer than a dull one. Keep 'em sharp! 🔪",
    "Don't crowd the pan — give your food room to breathe 🍳",
    "Taste as you go. Your tongue is your best tool 👅",
    "Room temp eggs whip better for baking 🥚",
    "Add pasta water to your sauce — it's liquid gold ✨",
    "Fresh herbs at the end, dried herbs at the start 🌿",
    "Let your pan get hot before adding oil 🔥",
    "Acid brightens everything — a squeeze of lemon works wonders 🍋",
    "Toast your spices to unlock their full flavor 🌶️",
    "Rest your cookie dough overnight for better texture 🍪",
    "Garlic burns fast — add it last when sautéing 🧄",
    "Save your veggie scraps for homemade stock 🥬",
    "Bloom your spices in oil for deeper flavor 🫒",
    "Cold butter = flaky pastry. Keep it chilly! 🧈",
    "Season every layer, not just at the end 🧂",
    "A hot oven = crispy roasted veggies 🥦",
    "Deglazing the pan? That's where the flavor lives 🍷",
]

def get_random_tip() -> str:
    """Get a random cooking tip for email footers"""
    return random.choice(COOKING_TIPS)


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
# EMAIL TEMPLATES - Modern, Beautiful Design
# =============================================================================

def get_base_template(content: str, accent_color: str = "#5BB080") -> str:
    """Wrap content in beautiful base email template"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <!--[if mso]>
    <style type="text/css">
        table, td, div, h1, p {{font-family: Arial, sans-serif !important;}}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAF8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #F8FAF8;">
        <tr>
            <td align="center" style="padding: 48px 20px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 560px;">
                    <!-- Logo Header with Image -->
                    <tr>
                        <td align="center" style="padding-bottom: 32px;">
                            <a href="{APP_URL}" style="text-decoration: none;">
                                <img src="{LOGO_URL}" alt="{APP_NAME}" width="140" height="auto" style="display: block; max-width: 140px; height: auto;" />
                            </a>
                        </td>
                    </tr>

                    <!-- Main Content Card -->
                    <tr>
                        <td>
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: #ffffff; border-radius: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04), 0 8px 32px rgba(91, 176, 128, 0.08); border: 1px solid #E8F0E8;">
                                <tr>
                                    <td style="padding: 40px 36px;">
                                        {content}
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td align="center" style="padding: 32px 20px 16px;">
                            <table role="presentation" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td align="center">
                                        <p style="margin: 0 0 12px 0; font-size: 14px; color: #6B7B6B;">
                                            Made with care by the {APP_NAME} team
                                        </p>
                                        <p style="margin: 0; font-size: 13px;">
                                            <a href="{APP_URL}" style="color: {accent_color}; text-decoration: none; font-weight: 500;">laro.food</a>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def get_button(text: str, url: str, color: str = "#5BB080", full_width: bool = False) -> str:
    """Generate a beautiful button"""
    width_style = "width: 100%;" if full_width else ""
    # Determine shadow color based on button color
    shadow_color = "rgba(91, 176, 128, 0.35)" if color == "#5BB080" else "rgba(0,0,0,0.15)"
    return f"""
    <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 0 auto; {width_style}">
        <tr>
            <td align="center" style="background: {color}; border-radius: 12px; box-shadow: 0 4px 12px {shadow_color};">
                <a href="{url}" target="_blank" style="display: inline-block; padding: 14px 32px; font-size: 15px; font-weight: 600; color: #ffffff; text-decoration: none; letter-spacing: 0.2px;">{text}</a>
            </td>
        </tr>
    </table>
    """


def get_header(title: str, subtitle: str = "", emoji: str = "") -> str:
    """Generate a clean header with optional emoji"""
    subtitle_html = f'<p style="margin: 8px 0 0 0; font-size: 16px; color: #6B7B6B; font-weight: 400;">{subtitle}</p>' if subtitle else ""
    emoji_html = ""
    if emoji:
        emoji_html = f"""
        <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 0 auto 16px auto;">
            <tr>
                <td align="center" style="width: 64px; height: 64px; background-color: #f0f7f2; border-radius: 50%;">
                    <span style="font-size: 28px; line-height: 64px;">{emoji}</span>
                </td>
            </tr>
        </table>
        """
    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 28px;">
        <tr>
            <td align="center">
                {emoji_html}
                <h1 style="margin: 0; font-size: 26px; font-weight: 700; color: #1a1a1a; letter-spacing: -0.3px;">{title}</h1>
                {subtitle_html}
            </td>
        </tr>
    </table>
    """


def get_icon_header(emoji: str, title: str, subtitle: str = "", color: str = "#5BB080") -> str:
    """Generate header with emoji icon"""
    return get_header(title, subtitle, emoji)


def get_info_card(content: str, bg_color: str = "#F5F8F5") -> str:
    """Generate an info card"""
    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 20px 0;">
        <tr>
            <td style="background: {bg_color}; border-radius: 12px; padding: 20px;">
                {content}
            </td>
        </tr>
    </table>
    """


def get_alert_card(content: str, alert_type: str = "warning") -> str:
    """Generate an alert card"""
    colors = {
        "warning": {"bg": "#FFFBEB", "border": "#F59E0B", "text": "#92400E"},
        "error": {"bg": "#FEF2F2", "border": "#EF4444", "text": "#991B1B"},
        "success": {"bg": "#ECFDF5", "border": "#10B981", "text": "#065F46"},
        "info": {"bg": "#EFF6FF", "border": "#3B82F6", "text": "#1E40AF"},
    }
    c = colors.get(alert_type, colors["warning"])
    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 20px 0;">
        <tr>
            <td style="background: {c['bg']}; border-left: 4px solid {c['border']}; border-radius: 0 12px 12px 0; padding: 16px 20px;">
                <div style="color: {c['text']}; font-size: 14px; line-height: 1.6;">
                    {content}
                </div>
            </td>
        </tr>
    </table>
    """


def get_feature_item(title: str) -> str:
    """Generate a single feature item with checkmark"""
    return f"""
    <tr>
        <td style="padding: 10px 0; border-bottom: 1px solid #f0f0f0;">
            <table role="presentation" cellspacing="0" cellpadding="0">
                <tr>
                    <td style="width: 28px; vertical-align: top;">
                        <div style="width: 20px; height: 20px; background-color: #5BB080; border-radius: 50%; text-align: center; line-height: 20px;">
                            <span style="color: white; font-size: 12px; font-weight: bold;">&#10003;</span>
                        </div>
                    </td>
                    <td style="padding-left: 12px; font-size: 15px; color: #333;">{title}</td>
                </tr>
            </table>
        </td>
    </tr>
    """


def get_feature_list(features: list) -> str:
    """Generate a clean feature list"""
    rows = "".join([get_feature_item(f) for f in features])
    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 24px 0;">
        {rows}
    </table>
    """


def get_feature_row(emoji: str, title: str, description: str = "") -> str:
    """Legacy function - redirects to get_feature_item"""
    # Strip any HTML spans from title
    import re
    clean_title = re.sub(r'<[^>]+>', '', title)
    return get_feature_item(clean_title)


# =============================================================================
# EMAIL FUNCTIONS
# =============================================================================

async def send_verification_email(to: str, name: str, token: str) -> bool:
    """Send email verification link to new user"""
    verification_url = f"{APP_URL}/#/verify-email?token={token}"

    content = f"""
    <!-- Welcome Header -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 28px;">
        <tr>
            <td align="center">
                <p style="font-size: 40px; margin: 0 0 12px 0;">👋</p>
                <h1 style="margin: 0 0 8px 0; font-size: 26px; font-weight: 700; color: #1a1a1a;">Hey {name}!</h1>
                <p style="margin: 0; font-size: 16px; color: #666;">One quick step to get started</p>
            </td>
        </tr>
    </table>

    <p style="font-size: 16px; color: #444; line-height: 1.7; margin: 0 0 28px 0; text-align: center;">
        Thanks for signing up for Laro! Click below to verify your email and unlock your personal recipe organizer.
    </p>

    <!-- CTA Button -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 32px 0;">
        <tr>
            <td align="center">
                {get_button("Verify My Email →", verification_url)}
            </td>
        </tr>
    </table>

    <!-- What's waiting -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: #f8faf8; border-radius: 12px; margin: 28px 0;">
        <tr>
            <td style="padding: 20px;">
                <p style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; color: #1a1a1a;">What's waiting for you:</p>
                <p style="margin: 0; font-size: 14px; color: #555; line-height: 1.6;">
                    📚 Save recipes from any website<br>
                    🍽️ Plan your weekly meals<br>
                    🛒 Auto-generate shopping lists<br>
                    👨‍👩‍👧‍👦 Share with your household
                </p>
            </td>
        </tr>
    </table>

    <!-- Link expires note -->
    <p style="font-size: 13px; color: #888; text-align: center; margin: 24px 0 0 0;">
        This link expires in 24 hours. Didn't sign up? You can ignore this email.
    </p>

    <!-- Pro tip -->
    <p style="font-size: 13px; color: #999; text-align: center; margin: 20px 0 0 0; font-style: italic; border-top: 1px solid #eee; padding-top: 20px;">
        🍳 Pro tip: {get_random_tip()}
    </p>
    """

    return await send_email(
        to=to,
        subject=f"Verify your email — let's get cooking! 🍳",
        html_body=get_base_template(content)
    )


async def send_password_reset_email(to: str, token: str) -> bool:
    """Send password reset email"""
    reset_url = f"{APP_URL}/#/reset-password?token={token}"

    content = f"""
    {get_header("Reset Your Password", "", "🔐")}

    <p style="font-size: 16px; color: #4B5B4B; line-height: 1.7; margin: 0 0 28px 0; text-align: center;">
        We received a request to reset your password. Click the button below to create a new one.
    </p>

    <div style="text-align: center; margin: 32px 0;">
        {get_button("Reset Password", reset_url)}
    </div>

    {get_info_card(f'''
        <p style="margin: 0 0 8px 0; font-size: 13px; color: #6B7B6B;"><strong>Or copy this link:</strong></p>
        <p style="margin: 0; font-size: 12px; color: #8B9B8B; word-break: break-all; background: #fff; padding: 12px; border-radius: 8px; border: 1px solid #E0E8E0;">{reset_url}</p>
    ''')}

    {get_alert_card('''
        <strong>This link expires in 1 hour.</strong><br>
        If you didn't request this, you can safely ignore this email.
    ''', 'warning')}
    """

    return await send_email(
        to=to,
        subject=f"Reset your {APP_NAME} password",
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
    {get_header("New Sign-In Detected", "We noticed a login to your account", "🔔")}

    {get_info_card(f'''
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
            <tr><td style="padding: 8px 0; border-bottom: 1px solid #E8F0E8;"><span style="color: #6B7B6B;">Device</span></td><td style="padding: 8px 0; border-bottom: 1px solid #E8F0E8; text-align: right; font-weight: 600; color: #2D3B2D;">{device}</td></tr>
            <tr><td style="padding: 8px 0; border-bottom: 1px solid #E8F0E8;"><span style="color: #6B7B6B;">IP Address</span></td><td style="padding: 8px 0; border-bottom: 1px solid #E8F0E8; text-align: right; font-weight: 600; color: #2D3B2D;">{ip_address}</td></tr>
            <tr><td style="padding: 8px 0; border-bottom: 1px solid #E8F0E8;"><span style="color: #6B7B6B;">Location</span></td><td style="padding: 8px 0; border-bottom: 1px solid #E8F0E8; text-align: right; font-weight: 600; color: #2D3B2D;">{location}</td></tr>
            <tr><td style="padding: 8px 0;"><span style="color: #6B7B6B;">Time</span></td><td style="padding: 8px 0; text-align: right; font-weight: 600; color: #2D3B2D;">{time_str}</td></tr>
        </table>
    ''')}

    <p style="font-size: 15px; color: #4B5B4B; text-align: center; margin: 24px 0;">
        If this was you, no action is needed.
    </p>

    {get_alert_card(f'''
        <strong>Wasn't you?</strong><br>
        Your account may be compromised. Please secure it immediately.
        <div style="margin-top: 16px;">
            {get_button("Secure My Account", f"{APP_URL}/#/settings/security", "#EF4444")}
        </div>
    ''', 'error')}
    """

    return await send_email(
        to=to,
        subject=f"New sign-in to your {APP_NAME} account",
        html_body=get_base_template(content)
    )


async def send_password_changed_notification(to: str) -> bool:
    """Send notification that password was changed"""
    time_str = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")

    content = f"""
    {get_header("Password Changed", "", "🔒")}

    <p style="font-size: 16px; color: #4B5B4B; line-height: 1.7; margin: 0 0 24px 0; text-align: center;">
        Your {APP_NAME} password was successfully changed on {time_str}.
    </p>

    {get_alert_card(f'''
        <strong>Didn't make this change?</strong><br>
        Your account may be compromised. Reset your password immediately.
        <div style="margin-top: 16px;">
            {get_button("Reset Password Now", f"{APP_URL}/#/forgot-password", "#EF4444")}
        </div>
    ''', 'error')}
    """

    return await send_email(
        to=to,
        subject=f"Your {APP_NAME} password was changed",
        html_body=get_base_template(content)
    )


async def send_2fa_enabled_notification(to: str) -> bool:
    """Send notification that 2FA was enabled"""
    content = f"""
    {get_header("2FA Enabled", "Your account is now more secure!", "🛡️")}

    {get_alert_card('''
        <strong>You're all set!</strong><br>
        Two-factor authentication is now active. You'll need your authenticator app each time you sign in.
    ''', 'success')}

    {get_info_card('''
        <p style="margin: 0; font-size: 14px; color: #4B5B4B;">
            <strong>Don't forget to save your backup codes!</strong><br>
            You'll need them if you lose access to your authenticator app.
        </p>
    ''')}
    """

    return await send_email(
        to=to,
        subject=f"2FA enabled on your {APP_NAME} account",
        html_body=get_base_template(content)
    )


async def send_2fa_disabled_notification(to: str) -> bool:
    """Send notification that 2FA was disabled"""
    content = f"""
    {get_header("2FA Disabled", "", "⚠️")}

    {get_alert_card(f'''
        <strong>Your account is less secure</strong><br>
        Two-factor authentication has been disabled. We recommend keeping it enabled.
        <div style="margin-top: 16px;">
            {get_button("Re-enable 2FA", f"{APP_URL}/#/settings/security")}
        </div>
    ''', 'warning')}

    <p style="font-size: 14px; color: #6B7B6B; text-align: center; margin-top: 24px;">
        If you didn't make this change, please secure your account immediately.
    </p>
    """

    return await send_email(
        to=to,
        subject=f"2FA disabled on your {APP_NAME} account",
        html_body=get_base_template(content)
    )


async def send_account_locked_notification(to: str, unlock_minutes: int) -> bool:
    """Send notification that account was locked"""
    content = f"""
    {get_header("Account Temporarily Locked", "", "🔐")}

    <p style="font-size: 16px; color: #4B5B4B; line-height: 1.7; margin: 0 0 24px 0; text-align: center;">
        Your account has been temporarily locked due to multiple failed login attempts.
    </p>

    {get_alert_card(f'''
        <strong>Your account will unlock in {unlock_minutes} minutes.</strong><br>
        If this was you, please wait and try again.
    ''', 'warning')}

    <div style="text-align: center; margin: 28px 0;">
        {get_button("Reset Password", f"{APP_URL}/#/forgot-password")}
    </div>

    {get_info_card('''
        <p style="margin: 0; font-size: 14px; color: #4B5B4B;">
            <strong>Protect your account:</strong><br>
            Consider enabling two-factor authentication after the lockout.
        </p>
    ''')}
    """

    return await send_email(
        to=to,
        subject=f"Your {APP_NAME} account was locked",
        html_body=get_base_template(content)
    )


async def send_account_deletion_email(to: str, token: str) -> bool:
    """Send account deletion confirmation email (GDPR compliance)"""
    deletion_url = f"{APP_URL}/#/delete-account?token={token}"

    content = f"""
    {get_header("Confirm Account Deletion", "", "🗑️")}

    <p style="font-size: 16px; color: #4B5B4B; line-height: 1.7; margin: 0 0 24px 0; text-align: center;">
        We received a request to delete your {APP_NAME} account.
    </p>

    {get_alert_card('''
        <strong>Warning: This action is permanent</strong>
        <p style="margin: 12px 0 0 0;">The following will be permanently deleted:</p>
        <ul style="margin: 12px 0 0 0; padding-left: 20px;">
            <li>Your account and profile</li>
            <li>All your recipes</li>
            <li>Meal plans and shopping lists</li>
            <li>Cookbooks and pantry items</li>
        </ul>
    ''', 'error')}

    <div style="text-align: center; margin: 28px 0;">
        {get_button("Delete My Account", deletion_url, "#EF4444")}
    </div>

    {get_info_card(f'''
        <p style="margin: 0 0 8px 0; font-size: 13px; color: #6B7B6B;"><strong>Or copy this link:</strong></p>
        <p style="margin: 0; font-size: 12px; color: #8B9B8B; word-break: break-all; background: #fff; padding: 12px; border-radius: 8px; border: 1px solid #E0E8E0;">{deletion_url}</p>
    ''')}

    <p style="font-size: 13px; color: #8B9B8B; text-align: center; margin-top: 24px;">
        This link expires in 24 hours. If you didn't request this, ignore this email.
    </p>
    """

    return await send_email(
        to=to,
        subject=f"Confirm your {APP_NAME} account deletion",
        html_body=get_base_template(content, "#EF4444")
    )


async def send_account_deleted_notification(to: str) -> bool:
    """Send notification that account was successfully deleted"""
    content = f"""
    {get_header("Account Deleted", "", "👋")}

    <p style="font-size: 16px; color: #4B5B4B; line-height: 1.7; margin: 0 0 24px 0; text-align: center;">
        Your {APP_NAME} account and all data have been permanently deleted.
    </p>

    {get_info_card('''
        <p style="margin: 0; font-size: 14px; color: #4B5B4B; text-align: center;">
            We're sorry to see you go. If you ever want to come back, you're always welcome to create a new account.
        </p>
    ''')}

    <p style="font-size: 14px; color: #6B7B6B; text-align: center; margin-top: 24px;">
        Have feedback? We'd love to hear from you at<br>
        <a href="mailto:app@laro.food" style="color: #5BB080;">app@laro.food</a>
    </p>
    """

    return await send_email(
        to=to,
        subject=f"Your {APP_NAME} account has been deleted",
        html_body=get_base_template(content)
    )


# ==================== SUBSCRIPTION EMAILS ====================

async def send_subscription_welcome_email(to: str, name: str = "there") -> bool:
    """Send welcome email for new Pro subscribers"""
    content = f"""
    <!-- Celebration Header -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 32px;">
        <tr>
            <td align="center">
                <p style="font-size: 48px; margin: 0 0 16px 0;">🍳</p>
                <h1 style="margin: 0 0 8px 0; font-size: 28px; font-weight: 700; color: #1a1a1a;">Welcome to the kitchen, {name}!</h1>
                <p style="margin: 0; font-size: 18px; color: #5BB080; font-weight: 600;">You're now a Laro Pro chef</p>
            </td>
        </tr>
    </table>

    <!-- Personal Message -->
    <p style="font-size: 16px; color: #444; line-height: 1.8; margin: 0 0 28px 0;">
        Thank you for joining our community of home cooks! Your support helps us build better tools so you can spend less time planning and more time enjoying delicious meals with the people you love. 💚
    </p>

    <!-- Free Recipe Gift -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: linear-gradient(135deg, #fff9e6 0%, #fff3cc 100%); border-radius: 16px; margin: 0 0 28px 0; border: 1px solid #ffe066;">
        <tr>
            <td style="padding: 24px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                    <tr>
                        <td>
                            <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: 600; color: #b8860b; text-transform: uppercase; letter-spacing: 1px;">🎁 Your welcome gift</p>
                            <p style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; color: #1a1a1a;">{FREE_RECIPE_NAME}</p>
                            <p style="margin: 0 0 16px 0; font-size: 14px; color: #666;">A comforting classic — perfect for using up leftovers! One of our favorites.</p>
                            <a href="{FREE_RECIPE_URL}" style="display: inline-block; background: #5BB080; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">View Recipe →</a>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>

    <!-- What's Unlocked Section -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: #f8faf8; border-radius: 16px; margin: 0 0 28px 0;">
        <tr>
            <td style="padding: 24px;">
                <p style="margin: 0 0 16px 0; font-size: 13px; font-weight: 600; color: #5BB080; text-transform: uppercase; letter-spacing: 1px;">🔓 Your Pro toolkit</p>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                    <tr>
                        <td style="padding: 8px 0;"><span style="margin-right: 10px;">📚</span> <strong>Unlimited recipes</strong> — your personal cookbook, no limits</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><span style="margin-right: 10px;">🤖</span> <strong>AI meal planning</strong> — "What's for dinner?" solved forever</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><span style="margin-right: 10px;">🛒</span> <strong>Smart shopping lists</strong> — organized by aisle, never forget garlic again</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><span style="margin-right: 10px;">🥗</span> <strong>Nutrition tracking</strong> — know what's on your plate</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><span style="margin-right: 10px;">💬</span> <strong>Priority support</strong> — real humans who love food</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>

    <!-- Quick Start Tips -->
    <p style="margin: 0 0 16px 0; font-size: 15px; font-weight: 600; color: #1a1a1a;">🚀 Get cooking in 3 steps:</p>

    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 28px;">
        <tr>
            <td style="padding: 12px 0; border-bottom: 1px solid #eee;">
                <table role="presentation" cellspacing="0" cellpadding="0">
                    <tr>
                        <td style="width: 36px; vertical-align: top;">
                            <span style="display: inline-block; width: 28px; height: 28px; background: #5BB080; color: white; border-radius: 50%; text-align: center; line-height: 28px; font-size: 14px; font-weight: 600;">1</span>
                        </td>
                        <td style="padding-left: 12px;">
                            <strong style="color: #1a1a1a;">Save your favorite recipes</strong><br>
                            <span style="color: #666; font-size: 14px;">Paste any recipe URL — we'll grab the ingredients & steps</span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px 0; border-bottom: 1px solid #eee;">
                <table role="presentation" cellspacing="0" cellpadding="0">
                    <tr>
                        <td style="width: 36px; vertical-align: top;">
                            <span style="display: inline-block; width: 28px; height: 28px; background: #5BB080; color: white; border-radius: 50%; text-align: center; line-height: 28px; font-size: 14px; font-weight: 600;">2</span>
                        </td>
                        <td style="padding-left: 12px;">
                            <strong style="color: #1a1a1a;">Plan your week</strong><br>
                            <span style="color: #666; font-size: 14px;">Drag recipes to your meal plan or let AI surprise you</span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px 0;">
                <table role="presentation" cellspacing="0" cellpadding="0">
                    <tr>
                        <td style="width: 36px; vertical-align: top;">
                            <span style="display: inline-block; width: 28px; height: 28px; background: #5BB080; color: white; border-radius: 50%; text-align: center; line-height: 28px; font-size: 14px; font-weight: 600;">3</span>
                        </td>
                        <td style="padding-left: 12px;">
                            <strong style="color: #1a1a1a;">Shop & cook</strong><br>
                            <span style="color: #666; font-size: 14px;">One-tap shopping list, then enjoy your creation 🍽️</span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>

    <!-- CTA Button -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 32px 0;">
        <tr>
            <td align="center">
                {get_button("Let's Get Cooking 🍳", f"{APP_URL}/#/recipes")}
            </td>
        </tr>
    </table>

    <!-- Personal Sign-off -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-top: 1px solid #eee; padding-top: 24px; margin-top: 24px;">
        <tr>
            <td>
                <p style="font-size: 15px; color: #444; line-height: 1.7; margin: 0;">
                    Got a question? A recipe request? Just want to share what you're cooking tonight? Hit reply — we read every message and love hearing from our community.
                </p>
                <p style="font-size: 15px; color: #444; margin: 16px 0 0 0;">
                    Happy cooking!<br>
                    <strong>The Laro Team</strong> 👨‍🍳👩‍🍳
                </p>
                <p style="font-size: 13px; color: #999; margin: 16px 0 0 0; font-style: italic;">
                    P.S. Pro tip: {get_random_tip()}
                </p>
            </td>
        </tr>
    </table>
    """

    return await send_email(
        to=to,
        subject=f"Welcome to the kitchen, {name}! 🍳 Here's a free recipe",
        html_body=get_base_template(content)
    )


async def send_billing_issue_email(to: str, name: str = "there") -> bool:
    """Send notification about billing issues"""
    content = f"""
    {get_header("Payment Issue", f"Hey {name}, we need your help", "💳")}

    <p style="font-size: 16px; color: #4B5B4B; line-height: 1.7; margin: 0 0 24px 0; text-align: center;">
        We had trouble processing your payment. Don't worry - this happens sometimes!
    </p>

    {get_alert_card('''
        <strong>Action needed</strong><br>
        Please update your payment method to keep your Pro features.
    ''', 'warning')}

    {get_info_card(f'''
        <p style="margin: 0 0 16px 0; font-weight: 600; color: #2D3B2D;">How to fix this:</p>
        <div style="margin-left: 8px;">
            <p style="margin: 8px 0;"><span style="background: #5BB080; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px; margin-right: 12px;">1</span> Open {APP_NAME} on your phone</p>
            <p style="margin: 8px 0;"><span style="background: #5BB080; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px; margin-right: 12px;">2</span> Go to Settings  Subscription</p>
            <p style="margin: 8px 0;"><span style="background: #5BB080; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px; margin-right: 12px;">3</span> Tap Manage Subscription</p>
        </div>
    ''')}

    <p style="font-size: 14px; color: #6B7B6B; text-align: center; margin-top: 24px;">
        Need help? Just reply to this email!
    </p>
    """

    return await send_email(
        to=to,
        subject=f"Action needed: Update your payment",
        html_body=get_base_template(content, "#FFB800")
    )


async def send_subscription_expired_email(to: str, name: str = "there") -> bool:
    """Send win-back email when subscription expires"""
    content = f"""
    {get_header("We Miss You!", f"Hey {name}", "💚")}

    <p style="font-size: 16px; color: #4B5B4B; line-height: 1.7; margin: 0 0 24px 0; text-align: center;">
        Your {APP_NAME} Pro subscription has ended. We hope you enjoyed cooking with us!
    </p>

    {get_info_card('''
        <p style="margin: 0 0 16px 0; font-weight: 600; color: #2D3B2D;">You'll be missing:</p>
        <div style="color: #8B9B8B;">
            <p style="margin: 8px 0; text-decoration: line-through;"> AI-powered meal planning</p>
            <p style="margin: 8px 0; text-decoration: line-through;"> Smart shopping lists</p>
            <p style="margin: 8px 0; text-decoration: line-through;"> Nutrition tracking</p>
            <p style="margin: 8px 0; text-decoration: line-through;"> Unlimited recipes</p>
        </div>
    ''')}

    <div style="text-align: center; margin: 32px 0;">
        {get_button("Come Back to Pro", f"{APP_URL}")}
    </div>

    <p style="font-size: 13px; color: #8B9B8B; text-align: center;">
        We'd love to hear why you left - your feedback helps us improve!
    </p>
    """

    return await send_email(
        to=to,
        subject=f"We miss you at {APP_NAME}!",
        html_body=get_base_template(content)
    )


async def send_subscription_cancelled_email(to: str, name: str = "there", expires_at: str = None) -> bool:
    """Send confirmation when subscription is cancelled"""
    expiry_html = ""
    if expires_at:
        expiry_html = get_alert_card(f'''
            <strong>Good news!</strong><br>
            You still have Pro access until <strong>{expires_at}</strong>
        ''', 'success')

    content = f"""
    {get_header("Subscription Cancelled", "", "📋")}

    <p style="font-size: 16px; color: #4B5B4B; line-height: 1.7; margin: 0 0 24px 0; text-align: center;">
        We've cancelled your {APP_NAME} Pro subscription as requested.
    </p>

    {expiry_html}

    {get_info_card('''
        <p style="margin: 0; font-size: 14px; color: #4B5B4B; text-align: center;">
            <strong>Changed your mind?</strong><br>
            You can resubscribe anytime in the app.
        </p>
    ''')}

    <p style="font-size: 13px; color: #8B9B8B; text-align: center; margin-top: 24px;">
        Cancelled by mistake? Just reply to this email!
    </p>
    """

    return await send_email(
        to=to,
        subject=f"Your {APP_NAME} subscription was cancelled",
        html_body=get_base_template(content)
    )

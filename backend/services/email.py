import os
import resend
import logging

logger = logging.getLogger(__name__)

resend.api_key = os.getenv("RESEND_API_KEY")

UK_CRISIS_HELPLINES_HTML = """
<div style="background:#1a0505;border:2px solid #c0392b;border-radius:8px;padding:20px;margin:20px 0;">
  <p style="color:#e74c3c;font-weight:bold;font-size:16px;margin:0 0 12px;">
    If you are in crisis or having thoughts of suicide, please reach out right now:
  </p>
  <ul style="color:#f5b7b1;font-size:15px;line-height:2;margin:0;padding-left:20px;">
    <li><strong>Samaritans</strong> — call or text <strong>116 123</strong> (free, 24/7)</li>
    <li><strong>Shout crisis text line</strong> — text <strong>SHOUT to 85258</strong> (free, 24/7)</li>
    <li><strong>NHS urgent mental health</strong> — call <strong>111</strong>, select option 2</li>
    <li><strong>CALM</strong> (men's mental health) — <strong>0800 58 58 58</strong></li>
    <li><strong>Papyrus</strong> (under 35) — <strong>0800 068 4141</strong></li>
    <li><strong>Emergency</strong> — call <strong>999</strong> if you are in immediate danger</li>
  </ul>
  <p style="color:#f5b7b1;margin:12px 0 0;font-size:14px;">
    You are not alone. These teams are trained to listen and they want to hear from you.
  </p>
</div>
"""

def send_crisis_email(to_email: str, username: str) -> bool:
    if not resend.api_key:
        logger.warning("RESEND_API_KEY is missing. Crisis email skipped.")
        return False

    html_content = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#333;">
      <h2 style="color:#c0392b;">MoodMap — We're concerned about you</h2>
      <p>Hi {username},</p>
      <p>We noticed something in your recent journal entry that concerns us, and we want to make sure
         you have access to immediate support.</p>
      {UK_CRISIS_HELPLINES_HTML}
      <p>If you are safe right now and just needed to express yourself, that's okay too.
         We're glad you're using MoodMap to process your feelings.</p>
      <p style="color:#6B7280;font-size:12px;margin-top:40px;">- The MoodMap Team</p>
    </div>
    """

    try:
        resend.Emails.send({
            "from": "MoodMap <onboarding@resend.dev>",
            "to": to_email,
            "subject": "We're here for you — important support resources",
            "html": html_content,
        })
        logger.info(f"Crisis email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send crisis email: {e}")
        return False


def send_nudge_email(to_email: str, username: str, nudge_content: str):
    """
    Wraps the Claude nudge in a beautiful HTML template and sends it via Resend
    """

    if not resend.api_key:
        logger.warning("RESEND_API_KEY is missing. Email skipped.")
        return False
    
    # A clean, modern HTML email template
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
        <h2 style="color: #4F46E5;">MoodMap Check-in</h2>
        <p>Hi {username},</p>
        <p>We've noticed you've been having a tough time lately. We just wanted to reach out and offer a thought:</p>
        
        <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #4F46E5;">
            <p style="font-size: 16px; margin: 0; font-style: italic; color: #1F2937;">"{nudge_content}"</p>
        </div>
        
        <p>Take care of yourself today.</p>
        <p style="color: #6B7280; font-size: 12px; margin-top: 40px;">- The MoodMap Team</p>
    </div>
    """

    try:
        # Send the email
        r = resend.Emails.send({
            "from": "MoodMap <onboarding@resend.dev>", # Resend's default testing email
            "to": to_email,
            "subject": "Thinking of you 💙",
            "html": html_content
        })
        logger.info(f"✅ Nudge email sent successfully to {to_email}!")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email: {str(e)}")
        return False
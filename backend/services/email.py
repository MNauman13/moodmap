import os
import resend
import logging

logger = logging.getLogger(__name__)

resend.api_key = os.getenv("RESEND_API_KEY")

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
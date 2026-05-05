import html
import os
import resend
import logging

_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "MoodMap <onboarding@resend.dev>")
_REPLY_TO = os.getenv("RESEND_REPLY_TO", "support@mood-map.uk")
_FRONTEND_URL = os.getenv("FRONTEND_URL", "https://moodmap.app").rstrip("/")

logger = logging.getLogger(__name__)

resend.api_key = os.getenv("RESEND_API_KEY")

# ── Shared layout primitives ──────────────────────────────────────────────────

_GOOGLE_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;1,400'
    '&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&display=swap" rel="stylesheet">'
)

# Fonts: web fonts load in Apple Mail, iOS, Samsung Mail, Outlook on Mac.
# Gmail ignores <link> tags — the serif/sans-serif fallbacks carry it there.
_FONT_SERIF  = "'Lora', Georgia, 'Times New Roman', serif"
_FONT_SANS   = "'DM Sans', 'Helvetica Neue', Arial, system-ui, sans-serif"

# Palette — mirrors globals.css and the Tailwind token usage across pages
_BG          = "#0e0d0b"
_BG_CARD     = "#0c0b09"
_BG_INSET    = "#141210"
_BORDER      = "#1a1815"
_BORDER_MID  = "#2a2720"
_GOLD        = "#c8a96e"
_TEXT_HI     = "#f0ece2"
_TEXT_BODY   = "#c8bfb0"
_TEXT_MID    = "#8a8070"
_TEXT_LO     = "#6b6357"
_TEXT_FAINT  = "#4a4438"
_RED         = "#b85c4a"
_RED_BG      = "#1a0a09"
_RED_BORDER  = "#5a2a20"


def _email_shell(title: str, preheader: str, body_html: str) -> str:
    """
    Wraps content in a full, client-compatible HTML document.
    Uses table-based layout; inline styles only (no <style> blocks —
    Gmail strips them). bgcolor attributes provide Outlook fallbacks.
    """
    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <meta name="supported-color-schemes" content="dark">
  <title>{title}</title>
  {_GOOGLE_FONTS_LINK}
  <!--[if mso]>
  <noscript>
    <xml><o:OfficeDocumentSettings>
      <o:PixelsPerInch>96</o:PixelsPerInch>
    </o:OfficeDocumentSettings></xml>
  </noscript>
  <![endif]-->
</head>
<body style="margin:0;padding:0;background-color:{_BG};" bgcolor="{_BG}">

  <!-- Preheader text (shown in inbox preview, hidden in body) -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
    {preheader}&zwnj;&nbsp;&#8199;&nbsp;&#65279;&nbsp;&#847;
  </div>

  <!-- Outer wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{_BG}"
         style="background-color:{_BG};">
    <tr>
      <td align="center" style="padding:48px 16px 56px;">

        <!-- Content column -->
        <table width="560" cellpadding="0" cellspacing="0" border="0"
               style="max-width:560px;width:100%;">

          <!-- ── Wordmark ── -->
          <tr>
            <td style="padding-bottom:28px;">
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="border-bottom:1px solid {_BORDER};padding-bottom:20px;">
                    <span style="font-family:{_FONT_SERIF};font-size:20px;font-weight:400;
                                 color:{_TEXT_HI};letter-spacing:0.01em;">Mood<span
                      style="font-style:italic;color:{_GOLD};">Map</span></span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ── Body ── -->
          {body_html}

          <!-- ── Footer ── -->
          <tr>
            <td style="border-top:1px solid {_BORDER};padding-top:24px;">
              <p style="margin:0 0 6px;font-family:{_FONT_SANS};font-size:12px;
                        font-weight:300;color:{_TEXT_FAINT};line-height:1.6;">
                You received this because email notifications are enabled on your MoodMap account.
                To stop these, visit <strong style="font-weight:400;">Account</strong>
                and turn off notifications.
              </p>
              <p style="margin:0;font-family:{_FONT_SANS};font-size:11px;
                        font-weight:300;color:#3d3830;line-height:1.5;">
                MoodMap &mdash; your emotional companion.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


# ── Nudge email ───────────────────────────────────────────────────────────────

def send_nudge_email(to_email: str, nudge_content: str) -> bool:
    """
    Sends a Claude-generated wellness nudge wrapped in the MoodMap design language.
    nudge_content is already plaintext (caller decrypts before passing here).
    """
    # Escape before embedding in HTML to prevent XSS if nudge_content ever
    # contains angle brackets or ampersands (e.g. from an LLM producing HTML).
    nudge_content = html.escape(nudge_content)

    if not resend.api_key:
        logger.warning("RESEND_API_KEY is missing. Nudge email skipped.")
        return False

    body = f"""
          <!-- Gold accent rule -->
          <tr>
            <td style="padding-bottom:32px;">
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="32" height="1" bgcolor="{_GOLD}"
                      style="background-color:{_GOLD};font-size:0;line-height:0;">&nbsp;</td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Eyebrow + headline -->
          <tr>
            <td style="padding-bottom:28px;">
              <p style="margin:0 0 10px;font-family:{_FONT_SANS};font-size:10px;
                        letter-spacing:0.14em;text-transform:uppercase;
                        color:{_TEXT_LO};font-weight:400;">
                A note for you
              </p>
              <h1 style="margin:0;font-family:{_FONT_SERIF};font-size:26px;font-weight:400;
                         color:{_TEXT_HI};line-height:1.3;">
                Hey &mdash; we&rsquo;ve been thinking about you.
              </h1>
            </td>
          </tr>

          <!-- Intro copy -->
          <tr>
            <td style="padding-bottom:32px;">
              <p style="margin:0;font-family:{_FONT_SANS};font-size:14px;font-weight:300;
                        color:{_TEXT_MID};line-height:1.75;">
                Your recent journal entries have shown some patterns worth pausing on.
                Here is something to consider as you move through your day.
              </p>
            </td>
          </tr>

          <!-- Nudge quote card -->
          <tr>
            <td style="padding-bottom:32px;">
              <!--[if mso]>
              <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr><td bgcolor="{_BG_CARD}" style="padding:24px 28px;">
              <![endif]-->
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td bgcolor="{_BG_CARD}"
                      style="background-color:{_BG_CARD};border:1px solid {_BORDER};
                             border-left:3px solid {_GOLD};border-radius:8px;
                             padding:24px 28px;">
                    <p style="margin:0;font-family:{_FONT_SERIF};font-size:16px;font-style:italic;
                               font-weight:400;color:{_TEXT_BODY};line-height:1.85;">
                      {nudge_content}
                    </p>
                  </td>
                </tr>
              </table>
              <!--[if mso]></td></tr></table><![endif]-->
            </td>
          </tr>

          <!-- Closing copy -->
          <tr>
            <td style="padding-bottom:40px;">
              <p style="margin:0;font-family:{_FONT_SANS};font-size:14px;font-weight:300;
                        color:{_TEXT_MID};line-height:1.75;">
                Small steps count. Be gentle with yourself today.
              </p>
            </td>
          </tr>

          <!-- CTA button -->
          <tr>
            <td style="padding-bottom:48px;">
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td bgcolor="{_BG_INSET}"
                      style="background-color:{_BG_INSET};border:1px solid {_BORDER_MID};
                             border-radius:100px;">
                    <a href="{_FRONTEND_URL}/journal"
                       style="display:inline-block;padding:12px 28px;font-family:{_FONT_SANS};
                              font-size:13px;font-weight:400;color:{_TEXT_MID};
                              text-decoration:none;letter-spacing:0.02em;">
                      Open your journal &rarr;
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
    """

    email_html = _email_shell(
        title="A note for you — MoodMap",
        preheader="A gentle nudge from your emotional companion.",
        body_html=body,
    )

    try:
        resend.Emails.send({
            "from": _FROM_EMAIL,
            "reply_to": _REPLY_TO,
            "to": to_email,
            "subject": "A note from your MoodMap",
            "html": email_html,
        })
        logger.info("Nudge email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send nudge email: %s", e)
        return False


# ── Crisis email ──────────────────────────────────────────────────────────────

def send_crisis_email(to_email: str) -> bool:
    """
    Sends immediate crisis support resources.
    Tone: warm, human, non-clinical. Avoids sounding automated.
    """
    if not resend.api_key:
        logger.warning("RESEND_API_KEY is missing. Crisis email skipped.")
        return False

    # Build the helpline rows outside the outer f-string.
    # Python 3.11 (PEP 701 not yet available) rejects a triple-quoted f-string
    # nested inside another f-string expression — compute it up-front instead.
    _helpline_rows_html = "".join(
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
        f' style="margin-bottom:14px;"><tr>'
        f'<td style="font-family:{_FONT_SANS};font-size:14px;font-weight:400;'
        f'color:{_TEXT_BODY};line-height:1.5;">'
        f'<strong style="color:{_TEXT_HI};font-weight:500;">{name}</strong>'
        f" &mdash; {detail}"
        f"</td></tr></table>"
        for name, detail in [
            ("Samaritans", "call or text <strong style='color:#e8e4dc;'>116 123</strong> &mdash; free, 24/7, confidential"),
            ("Shout", "text <strong style='color:#e8e4dc;'>SHOUT to 85258</strong> &mdash; free crisis text line, 24/7"),
            ("NHS urgent mental health", "call <strong style='color:#e8e4dc;'>111</strong> and select option 2"),
            ("CALM", "call <strong style='color:#e8e4dc;'>0800 58 58 58</strong> &mdash; men's mental health"),
            ("Papyrus", "call <strong style='color:#e8e4dc;'>0800 068 4141</strong> &mdash; under 35"),
            ("Emergency", "call <strong style='color:#e8e4dc;'>999</strong> if you are in immediate danger"),
        ]
    )

    body = f"""
          <!-- Warm red accent rule -->
          <tr>
            <td style="padding-bottom:32px;">
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="32" height="1" bgcolor="{_RED}"
                      style="background-color:{_RED};font-size:0;line-height:0;">&nbsp;</td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Eyebrow + headline -->
          <tr>
            <td style="padding-bottom:28px;">
              <p style="margin:0 0 10px;font-family:{_FONT_SANS};font-size:10px;
                        letter-spacing:0.14em;text-transform:uppercase;
                        color:{_TEXT_LO};font-weight:400;">
                We&rsquo;re here for you
              </p>
              <h1 style="margin:0;font-family:{_FONT_SERIF};font-size:26px;font-weight:400;
                         color:{_TEXT_HI};line-height:1.3;">
                Hey &mdash; we noticed something in your words.
              </h1>
            </td>
          </tr>

          <!-- Intro copy -->
          <tr>
            <td style="padding-bottom:32px;">
              <p style="margin:0 0 16px;font-family:{_FONT_SANS};font-size:14px;font-weight:300;
                        color:{_TEXT_MID};line-height:1.75;">
                Something you wrote recently gave us pause, and we want to make sure
                you know that support is available right now &mdash; at any hour.
              </p>
              <p style="margin:0;font-family:{_FONT_SANS};font-size:14px;font-weight:300;
                        color:{_TEXT_MID};line-height:1.75;">
                If you are safe and just needed a space to express yourself, that is
                completely okay. But if any part of you is struggling, please reach out
                to one of the teams below.
              </p>
            </td>
          </tr>

          <!-- Crisis helplines card -->
          <tr>
            <td style="padding-bottom:32px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td bgcolor="{_RED_BG}"
                      style="background-color:{_RED_BG};border:1px solid {_RED_BORDER};
                             border-left:3px solid {_RED};border-radius:8px;
                             padding:24px 28px;">

                    <p style="margin:0 0 18px;font-family:{_FONT_SANS};font-size:11px;
                               letter-spacing:0.12em;text-transform:uppercase;
                               color:{_RED};font-weight:400;">
                      Free &amp; confidential support &mdash; UK
                    </p>

                    <!-- Helpline rows -->
                    {_helpline_rows_html}

                    <table width="100%" cellpadding="0" cellspacing="0" border="0"
                           style="border-top:1px solid {_RED_BORDER};margin-top:8px;padding-top:16px;">
                      <tr>
                        <td style="font-family:{_FONT_SERIF};font-size:14px;font-style:italic;
                                   font-weight:400;color:{_TEXT_MID};line-height:1.7;
                                   padding-top:16px;">
                          You are not alone. These teams are trained to listen,
                          and they want to hear from you.
                        </td>
                      </tr>
                    </table>

                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Closing copy -->
          <tr>
            <td style="padding-bottom:48px;">
              <p style="margin:0;font-family:{_FONT_SANS};font-size:14px;font-weight:300;
                        color:{_TEXT_MID};line-height:1.75;">
                We&rsquo;re glad you&rsquo;re using MoodMap to process how you feel.
                That takes courage.
              </p>
            </td>
          </tr>
    """

    email_html = _email_shell(
        title="We're here for you — MoodMap",
        preheader="Support resources are available right now, any time.",
        body_html=body,
    )

    try:
        resend.Emails.send({
            "from": _FROM_EMAIL,
            "reply_to": _REPLY_TO,
            "to": to_email,
            "subject": "We're here for you — support resources inside",
            "html": email_html,
        })
        logger.info("Crisis email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send crisis email: %s", e)
        return False

"""
Manual smoke test for the nudge-email and weekly-PDF-report flows.

Drives the helpers directly with sample data — no API server, no Celery,
no database, no LangGraph. Useful for confirming Resend + Claude + fpdf2
all work end-to-end on the local machine before wiring them up to live data.

Run from the project root:

    python scripts/test_nudge_and_report.py

Required env vars (read from backend/.env):
    ANTHROPIC_API_KEY   — to actually call Claude (otherwise that step is skipped)
    RESEND_API_KEY      — to actually send the email (otherwise that step is skipped)

Optional:
    EMAIL_FROM          — defaults to "MoodMap <onboarding@resend.dev>" (Resend free tier)
    TEST_EMAIL_TO       — defaults to mnaumansiddiqui06@gmail.com
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

# Look for .env in backend/.env (relative to project root)
_candidate_envs = [
    ROOT / "backend" / ".env",
]
for env_path in _candidate_envs:
    if env_path.is_file():
        # override=True so an empty/stale shell var doesn't mask the .env value
        load_dotenv(env_path, override=True)
        print(f"Loaded env from {env_path}")
        break
else:
    print("WARN: no backend/.env found — relying on shell environment only")

# Resend's free tier only sends from onboarding@resend.dev (or a verified domain)
# and only delivers to the address you signed up with. Override via env if you
# have a verified domain set up.
os.environ.setdefault("EMAIL_FROM", "MoodMap <onboarding@resend.dev>")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("smoke-test")


def test_nudge() -> bool:
    """Generate a Claude-written nudge and email it via Resend."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY not set — skipping nudge generation")
        return False
    if not os.getenv("RESEND_API_KEY"):
        logger.error("RESEND_API_KEY not set — skipping email send")
        return False

    # Drive the real distress_agent.generate_nudge node so we exercise the
    # exact prompt + max_tokens + truncation pipeline used in production.
    from unittest.mock import patch
    from backend.agents.distress_agent import generate_nudge
    from backend.services.email import send_nudge_email

    state = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "mood_history": [-0.6, -0.5, -0.4, -0.7, -0.6, -0.8, -0.7],
        "trajectory": {"slope": -0.10, "volatility": 0.13, "z_score": -1.2},
        "is_crisis": False,
    }

    logger.info("[1/3] Running distress_agent.generate_nudge with mocked DB")
    # Skip the SyncSessionLocal lookup for intervention weights — fall back to defaults.
    with patch("backend.agents.distress_agent.SyncSessionLocal") as mock_session:
        mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = None
        result = generate_nudge(state)

    nudge_content = result["nudge_content"]
    logger.info(
        "[2/3] Final nudge (%d chars, type=%s):\n    %s",
        len(nudge_content), result["nudge_type"], nudge_content,
    )
    if not nudge_content.rstrip().endswith((".", "!", "?")):
        logger.warning("Nudge does NOT end on sentence-final punctuation!")

    target = os.getenv("TEST_EMAIL_TO", "mnaumansiddiqui06@gmail.com")
    logger.info("[3/3] Sending nudge email to %s", target)
    ok = send_nudge_email(to_email=target, username="Test", nudge_content=nudge_content)
    if ok:
        logger.info("Nudge email sent successfully.")
    else:
        logger.error("Nudge email FAILED — check Resend dashboard / API key / EMAIL_FROM.")
    return ok


def test_report() -> bool:
    """Generate a sample weekly PDF report and write it to disk."""
    from backend.services.pdf_generator import generate_weekly_report

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    out_path = ROOT / "test_weekly_report.pdf"

    logger.info("Generating sample weekly PDF at %s", out_path)
    generate_weekly_report(
        file_path=str(out_path),
        start_date=start.strftime("%B %d, %Y"),
        end_date=end.strftime("%B %d, %Y"),
        headline="A reflective week",
        summary=(
            "You journaled 5 days this week. Saturday carried the lightest "
            "weight, while Tuesday felt the heaviest. Both the easy days and "
            "the harder ones are part of the same texture — noticing them is "
            "itself a kind of self-care."
        ),
        top_emotions=[
            ("Calm", 6),
            ("Joy", 4),
            ("Anxiety", 3),
            ("Sadness", 2),
        ],
        themes=[
            "Work, Stress, Deadline",
            "Sleep, Rest, Morning",
            "Friend, Coffee, Conversation",
        ],
        quote={
            "text": (
                "Today felt strange — I couldn't tell if I was tired or just "
                "quiet. I sat with my coffee for a long time and watched the "
                "light move across the kitchen. There was something settling "
                "about not having to do anything in particular."
            ),
            "attribution": "Tuesday morning",
        },
        reflection_prompts=[
            "What's one moment from this week you'd like to carry forward into the next?",
            "Where did you feel most yourself, and what made that possible?",
            "If next week could feel a degree lighter, what might help?",
        ],
        days_logged=5,
    )
    if out_path.exists():
        size_kb = out_path.stat().st_size / 1024
        logger.info("PDF written: %s (%.1f KB)", out_path, size_kb)
        return True
    logger.error("PDF generation produced no file at %s", out_path)
    return False


if __name__ == "__main__":
    print("=" * 60)
    print(" MoodMap smoke test — nudge email + weekly PDF report")
    print("=" * 60)

    print("\n--- TEST 1: nudge email ---")
    if os.getenv("SKIP_NUDGE") == "1":
        logger.info("SKIP_NUDGE=1 set — skipping nudge test")
        nudge_ok = True
    else:
        nudge_ok = test_nudge()

    print("\n--- TEST 2: weekly PDF report ---")
    report_ok = test_report()

    print("\n" + "=" * 60)
    print(f" Nudge email : {'PASS' if nudge_ok else 'FAIL/SKIP'}")
    print(f" PDF report  : {'PASS' if report_ok else 'FAIL'}")
    print("=" * 60)

    sys.exit(0 if (nudge_ok and report_ok) else 1)

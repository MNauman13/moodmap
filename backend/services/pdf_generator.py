"""
Weekly PDF report renderer.

Visual language mirrors the MoodMap web app: dark background, warm gold
accent, serif headlines, sans-serif metadata. Built on fpdf2 with the
built-in Helvetica + Times faces (no external font assets to ship).

Design principles:
  - User-centric content only. No z-scores, slopes, or raw fused scores.
  - Every section answers a question a person would actually ask:
    "How was my week?", "What did I feel?", "What was on my mind?"
  - Lots of whitespace. The web app trades on quiet — the PDF should too.
"""

from typing import Optional
from fpdf import FPDF


# --- Brand palette (mirrors the dark website theme) -------------------------
BG          = (14, 13, 11)      # #0e0d0b - page background
SURFACE     = (12, 11, 9)       # #0c0b09 - cards / pull-quote surface
BORDER      = (26, 24, 21)      # #1a1815 - hairline dividers
INK         = (232, 228, 220)   # #e8e4dc - body copy
INK_BRIGHT  = (240, 236, 226)   # #f0ece2 - headlines
MUTED       = (138, 128, 112)   # #8a8070 - secondary copy
FAINT       = (107, 99, 87)     # #6b6357 - labels & footer
GOLD        = (200, 169, 110)   # #c8a96e - primary accent
GOLD_DIM    = (160, 135, 88)    # softer gold for bars / dividers


# --- Encoding safety --------------------------------------------------------
# Built-in PDF fonts use WinAnsiEncoding (cp1252), which already supports
# em-dash, en-dash, smart quotes, ellipsis, and bullet directly. We round-trip
# through cp1252 so any unmappable codepoint (e.g. emoji) becomes "?" instead
# of crashing the generator on a user's journal entry.
_NBSP_REPLACEMENTS = {
    " ": " ",   # non-breaking space -> regular space
}


def _safe(text: str) -> str:
    if not text:
        return ""
    for k, v in _NBSP_REPLACEMENTS.items():
        text = text.replace(k, v)
    return text.encode("cp1252", errors="replace").decode("cp1252")


# --- PDF document -----------------------------------------------------------
class WeeklyReportPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        # fpdf2 normalizes every cell through this encoding before writing the
        # PDF stream. Default is "latin-1" which doesn't include em-dash,
        # smart quotes, ellipsis, or bullet — switching to cp1252 (WinAnsi)
        # makes all of those render natively with the built-in core fonts.
        self.core_fonts_encoding = "cp1252"
        self.set_margins(left=22, top=22, right=22)
        self.set_auto_page_break(auto=True, margin=24)

    def header(self):
        # Paint full-page dark background
        self.set_fill_color(*BG)
        self.rect(-1, -1, self.w + 2, self.h + 2, style="F")
        # Brand mark, top-right
        self.set_xy(self.w - self.r_margin - 30, 14)
        self.set_font("helvetica", "B", 8)
        self.set_text_color(*FAINT)
        self.cell(30, 4, _safe("M O O D M A P"), align="R")

    def footer(self):
        self.set_y(-16)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.15)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)
        self.set_font("helvetica", "I", 7)
        self.set_text_color(*FAINT)
        self.cell(
            0, 4,
            _safe("MoodMap is a reflection companion, not a clinical tool."),
            align="C", new_x="LMARGIN", new_y="NEXT",
        )

    # --- Layout helpers -----------------------------------------------------
    def ensure_room_for(self, mm: float) -> None:
        """Start a new page if less than `mm` of vertical space remains."""
        if self.get_y() + mm > self.h - self.b_margin:
            self.add_page()

    # --- Building blocks ----------------------------------------------------
    def section_heading(self, label: str) -> None:
        """Small uppercase label + short gold accent line underneath."""
        self.ln(6)
        self.set_font("helvetica", "B", 8)
        self.set_text_color(*FAINT)
        # Manual letter-spacing via space insertion
        spaced = "  ".join(label.upper())
        self.cell(0, 4, _safe(spaced), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        y = self.get_y()
        self.set_draw_color(*GOLD_DIM)
        self.set_line_width(0.4)
        self.line(self.l_margin, y, self.l_margin + 10, y)
        self.ln(5)

    def body_paragraph(self, text: str) -> None:
        self.set_font("times", "", 11.5)
        self.set_text_color(*INK)
        usable_w = self.w - self.l_margin - self.r_margin
        self.multi_cell(usable_w, 6.2, _safe(text), new_x="LMARGIN", new_y="NEXT")

    def emotion_bars(self, emotions: list, *, bar_max_w: float = 80.0) -> None:
        """Renders a clean horizontal bar list, e.g. Joy ████ 4 times."""
        if not emotions:
            return
        peak = max((c for _, c in emotions), default=1) or 1
        for name, count in emotions:
            row_y = self.get_y()
            self.set_font("times", "", 12)
            self.set_text_color(*INK_BRIGHT)
            self.set_xy(self.l_margin, row_y)
            self.cell(38, 7, _safe(name))

            bar_x = self.l_margin + 38
            bar_y = row_y + 3
            bar_h = 1.6
            self.set_fill_color(*BORDER)
            self.rect(bar_x, bar_y, bar_max_w, bar_h, style="F")
            fill_w = bar_max_w * (count / peak)
            self.set_fill_color(*GOLD_DIM)
            self.rect(bar_x, bar_y, fill_w, bar_h, style="F")

            self.set_xy(bar_x + bar_max_w + 5, row_y)
            self.set_font("helvetica", "", 9)
            self.set_text_color(*FAINT)
            label = f"{count} {'time' if count == 1 else 'times'}"
            self.cell(0, 7, _safe(label), new_x="LMARGIN", new_y="NEXT")
            self.ln(0.3)

    def theme_item(self, primary: str, secondary: Optional[str] = None) -> None:
        """Theme line: gold dot + primary phrase + optional secondary copy."""
        usable_w = self.w - self.l_margin - self.r_margin
        self.set_font("times", "B", 12)
        self.set_text_color(*GOLD)
        self.cell(5, 6.5, _safe("\xb7"))  # middle dot (cp1252 safe)
        self.set_font("times", "", 12)
        self.set_text_color(*INK_BRIGHT)
        self.cell(0, 6.5, _safe(primary), new_x="LMARGIN", new_y="NEXT")
        if secondary:
            self.set_x(self.l_margin + 5)
            self.set_font("helvetica", "", 9.5)
            self.set_text_color(*MUTED)
            self.multi_cell(usable_w - 5, 5, _safe(secondary), new_x="LMARGIN", new_y="NEXT")
        self.ln(0.5)

    def pull_quote(self, text: str, attribution: str) -> None:
        """Indented italic block with a vertical gold accent bar."""
        x_start = self.l_margin
        usable_w = self.w - self.l_margin - self.r_margin - 10
        y_start = self.get_y()

        self.set_font("times", "I", 12.5)
        self.set_text_color(*INK_BRIGHT)
        self.set_xy(x_start + 8, y_start)
        # Use cp1252 left/right double quotation marks (\x93 / \x94)
        self.multi_cell(
            usable_w, 6.5,
            _safe(f"\x93{text}\x94"),
            new_x="LMARGIN", new_y="NEXT",
        )
        y_end = self.get_y()

        self.set_fill_color(*GOLD_DIM)
        self.rect(x_start, y_start + 1, 1.2, y_end - y_start - 2, style="F")

        self.ln(1)
        self.set_x(x_start + 8)
        self.set_font("helvetica", "", 9)
        self.set_text_color(*FAINT)
        self.cell(0, 4, _safe(f"\x97 {attribution}"), new_x="LMARGIN", new_y="NEXT")

    def reflection_item(self, text: str) -> None:
        usable_w = self.w - self.l_margin - self.r_margin
        self.set_font("times", "B", 12)
        self.set_text_color(*GOLD)
        self.cell(5, 6.8, _safe("\xb7"))
        self.set_font("times", "I", 11.5)
        self.set_text_color(*INK)
        self.multi_cell(usable_w - 5, 6.5, _safe(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def cover_block(self, *, kicker: str, headline: str, date_range: str) -> None:
        """The opening masthead. The middle word of the headline becomes an
        italic gold accent, mirroring the website's "Your <em>emotional</em>
        map" treatment.
        """
        self.set_y(38)
        # Kicker
        self.set_font("helvetica", "B", 8)
        self.set_text_color(*FAINT)
        self.cell(0, 5, _safe("  ".join(kicker.upper())), new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

        # Headline with italic gold accent on the middle word.
        # Pattern is "{prefix} {accent} {suffix}" (e.g. "A reflective week").
        parts = headline.split(" ")
        self.set_font("times", "", 30)
        self.set_text_color(*INK_BRIGHT)
        if len(parts) == 3:
            prefix, accent, suffix = parts
            # First word
            w_prefix = self.get_string_width(prefix + " ")
            self.cell(w_prefix, 13, _safe(prefix + " "))
            # Italic gold accent
            self.set_font("times", "I", 30)
            self.set_text_color(*GOLD)
            w_accent = self.get_string_width(accent)
            self.cell(w_accent, 13, _safe(accent))
            # Trailing word
            self.set_font("times", "", 30)
            self.set_text_color(*INK_BRIGHT)
            self.cell(0, 13, _safe(" " + suffix), new_x="LMARGIN", new_y="NEXT")
        else:
            self.cell(0, 13, _safe(headline), new_x="LMARGIN", new_y="NEXT")

        # Gold accent rule
        self.ln(2)
        y = self.get_y()
        self.set_draw_color(*GOLD)
        self.set_line_width(0.6)
        self.line(self.l_margin, y, self.l_margin + 22, y)

        # Date range
        self.ln(5)
        self.set_font("helvetica", "", 10)
        self.set_text_color(*MUTED)
        self.cell(0, 5, _safe(date_range), new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def closing_block(self, message: str) -> None:
        """Hairline divider, small centered gold ornament, and italic sign-off.

        If a lot of vertical space remains on the current page, float the
        block toward the lower third so the whitespace below the prompts
        feels like an intentional pause rather than a layout accident.
        """
        target_y = self.h * 0.62
        if self.get_y() < target_y - 12:
            self.set_y(target_y)
        else:
            self.ln(6)

        # Hairline divider
        y = self.get_y()
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin, y, self.w - self.r_margin, y)

        # Small centered gold ornament — visual breath between divider and message
        self.ln(7)
        self.set_font("times", "B", 11)
        self.set_text_color(*GOLD_DIM)
        self.cell(0, 4, _safe("\xb7  \xb7  \xb7"), align="C", new_x="LMARGIN", new_y="NEXT")

        # Italic gold sign-off
        self.ln(4)
        self.set_font("times", "I", 12)
        self.set_text_color(*GOLD)
        self.cell(0, 6, _safe(message), align="C", new_x="LMARGIN", new_y="NEXT")


# --- Public renderer --------------------------------------------------------
def generate_weekly_report(
    file_path: str,
    *,
    start_date: str,
    end_date: str,
    headline: str,
    summary: str,
    top_emotions: list,         # list[tuple[str, int]] e.g. [("Joy", 4), ...]
    themes: list,               # list[str] e.g. ["Work, stress, deadlines", ...]
    quote: Optional[dict],      # {"text": "...", "attribution": "Tuesday morning"} or None
    reflection_prompts: list,   # list[str]
    days_logged: int,
    sign_off: str = "Take care of yourself this week.",
) -> str:
    pdf = WeeklyReportPDF()
    pdf.add_page()

    # Cover
    pdf.cover_block(
        kicker="Weekly Reflection",
        headline=headline,
        date_range=f"{start_date} \x96 {end_date}",  # en-dash (cp1252 \x96)
    )

    # The shape of your week
    pdf.section_heading("The shape of your week")
    pdf.body_paragraph(summary)

    # What you felt most
    if top_emotions:
        pdf.section_heading("What you felt most")
        pdf.emotion_bars(top_emotions)

    # What was on your mind
    if themes:
        pdf.section_heading("What was on your mind")
        for theme in themes[:3]:
            pdf.theme_item(theme)

    # A moment from this week
    if quote and quote.get("text"):
        pdf.section_heading("A moment from this week")
        pdf.pull_quote(quote["text"], quote.get("attribution", ""))

    # Looking ahead — keep this section + closing together. If the heading,
    # 3 prompts, hairline, and sign-off won't fit on the current page, start
    # fresh so the user doesn't get one orphan bullet at the bottom.
    if reflection_prompts:
        pdf.ensure_room_for(70)
        pdf.section_heading("Looking ahead")
        for prompt in reflection_prompts[:3]:
            pdf.reflection_item(prompt)

    # Closing
    pdf.closing_block(sign_off)

    pdf.output(file_path)
    return file_path

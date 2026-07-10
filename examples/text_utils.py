# examples/text_utils.py
import re


def clean_html(html: str) -> str:
    """Strip scripts, styles, and HTML tags, and clean up whitespace."""
    # Remove script and style blocks
    clean = re.sub(
        r"<(script|style).*?>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    # Remove all remaining HTML tags
    clean = re.sub(r"<.*?>", "", clean)
    # Collapse multiple spaces and newlines
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()[:800]

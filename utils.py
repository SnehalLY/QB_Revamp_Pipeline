import html
import re


TEXTAREA_PLACEHOLDER_RE = re.compile(
    r'<textarea[^>]*placeholder=["\']([^"\']+)["\'][^>]*>(.*?)</textarea>',
    re.IGNORECASE | re.DOTALL,
)


def strip_html(text):
    if text is None:
        return ""

    cleaned = str(text)
    cleaned = re.sub(r"(?is)<style[^>]*>.*?</style>", "", cleaned)

    def _textarea_replacer(match):
        placeholder = match.group(1) or ""
        inner_text = (match.group(2) or "").strip()
        return placeholder if placeholder else inner_text

    cleaned = TEXTAREA_PLACEHOLDER_RE.sub(_textarea_replacer, cleaned)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</div\s*>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</p\s*>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</li\s*>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</tr\s*>", "\n", cleaned)
    cleaned = re.sub(r"(?i)<li[^>]*>", "", cleaned)
    cleaned = re.sub(r"(?i)<tr[^>]*>", "", cleaned)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_question_blocks(question_text):
    """
    Split the cleaned question text into the part before the Sample Script marker
    and the code snippet after it.
    """
    content = strip_html(question_text)
    if not content:
        return {"question_text": "", "code_snippet": ""}

    marker = re.search(r"(?i)Sample\s+Script\s*:", content)
    if not marker:
        return {"question_text": content, "code_snippet": ""}

    question_part = content[:marker.start()].strip()
    code_part = content[marker.end():].strip()
    return {"question_text": question_part, "code_snippet": code_part}

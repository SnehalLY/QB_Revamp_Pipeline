import logging
import re

from utils import extract_question_blocks, strip_html

logger = logging.getLogger(__name__)

TAG_NOISE_PATTERNS = [
    re.compile(r"^SME\s*:\s*.+", re.IGNORECASE),
    re.compile(r"^Created\s+By\s*:\s*.+", re.IGNORECASE),
    re.compile(r"^Given\s+by\s*.+", re.IGNORECASE),
    re.compile(r".*Date\s+Created\s*:\s*.+", re.IGNORECASE),
    re.compile(r".*Date\s+created\s*:\s*.+", re.IGNORECASE),
]


def _looks_like_tag_noise(value: str) -> bool:
    cleaned = value.strip()
    return any(pattern.match(cleaned) for pattern in TAG_NOISE_PATTERNS)


def parse_question_content(question_html):
    """
    Clean the raw `Question` field, split off the Sample Script block,
    then best-effort separate scenario and instructions.
    """
    cleaned = strip_html(question_html)
    blocks = extract_question_blocks(cleaned)
    question_text = blocks.get("question_text", "")
    code_snippet = blocks.get("code_snippet", "")

    scenario = question_text.strip()
    instructions = ""

    instruction_markers = [
        "Complete the code as per the given instructions:",
        "Instructions:",
        "Instruction:",
    ]

    lower_question_text = question_text.lower()
    for marker in instruction_markers:
        marker_index = lower_question_text.find(marker.lower())
        if marker_index != -1:
            scenario = question_text[:marker_index].strip()
            instructions = question_text[marker_index:].strip()
            break

    if not instructions:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", question_text) if part.strip()]
        if len(paragraphs) >= 2:
            scenario = "\n\n".join(paragraphs[:-1]).strip()
            instructions = paragraphs[-1].strip()

    return {
        "scenario": scenario,
        "instructions": instructions,
        "code_snippet": code_snippet or question_text,
    }


def parse_tags(tags_str):
    """
    Extract topic/subtopic from the Tags field.
    Skips metadata noise like 'SME: ...', 'Created By: ...', 'Date Created: ...'.
    Supports common delimiters: '::', '|', ':', ','
    """
    raw = str(tags_str or "").strip()
    if not raw:
        return {"topic": "", "subtopic": ""}

    logger.debug("Parsing tags raw value: %r", raw)

    if _looks_like_tag_noise(raw):
        logger.debug("Tags value looks like metadata noise, skipping")
        return {"topic": "", "subtopic": ""}

    for delimiter in ("::", "|", ":", ","):
        if delimiter in raw:
            parts = [part.strip() for part in raw.split(delimiter) if part.strip()]
            if len(parts) >= 2:
                return {"topic": parts[0], "subtopic": parts[1]}
            if len(parts) == 1:
                return {"topic": parts[0], "subtopic": ""}

    return {"topic": raw, "subtopic": ""}


DIFFICULTY_MAP = {
    1: "Easy",
    2: "Medium",
    3: "Hard",
}


def map_db_row_to_qc_input(question_record):
    """
    Converts a fetched question dict into the format qc_and_revamp_chain expects.
    """
    if not isinstance(question_record, dict):
        raise TypeError("question_record must be a dict")

    que_id = question_record.get("QueId")
    logger.debug("Mapping question QueId=%s", que_id)

    question_text = question_record.get("Question", "") or ""
    content = parse_question_content(question_text)
    tags = parse_tags(question_record.get("Tags"))

    answers_raw = question_record.get("Answers", []) or []
    answers_sorted = sorted(answers_raw, key=lambda a: a.get("AnsId", 0))
    answers = {f"Blank {i+1}": answer_row.get("Answer", "") for i, answer_row in enumerate(answers_sorted[:5])}

    difficulty_value = question_record.get("DifficultyLevel", "Medium")
    if isinstance(difficulty_value, (int, float)) and not isinstance(difficulty_value, bool):
        difficulty_value = int(difficulty_value)

    mapped = {
        "topic": tags.get("topic", "") or question_record.get("QBName", ""),
        "sub_topic": tags.get("subtopic", ""),
        "difficulty": DIFFICULTY_MAP.get(difficulty_value, "Medium") if isinstance(difficulty_value, int) else str(difficulty_value or "Medium"),
        "scenario": content.get("scenario", ""),
        "instructions": content.get("instructions", ""),
        "code_snippet": content.get("code_snippet", "") or question_text,
        "answers": answers,
        "_meta": {
            "QueId": que_id
        }
    }

    logger.debug("Mapped topic=%r subtopic=%r difficulty=%r", mapped["topic"], mapped["sub_topic"], mapped["difficulty"])
    return mapped
import json
import re
from typing import Any, Dict, Iterable, List, Optional

from openai import AzureOpenAI

from config import AZURE_OPENAI_API_BASE, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_API_BASE.rstrip("/") + "/",
)


Difficulty_level_json = {
    "Easy": {
        "min_blank_count": 5,
        "expected_code_tokens": {"min": 70, "max": 180},
        "scenario_guidance": "Keep the scenario concise and directly relevant to the task.",
    },
    "Medium": {
        "min_blank_count": 5,
        "expected_code_tokens": {"min": 110, "max": 260},
        "scenario_guidance": "Use a moderately detailed scenario that provides enough context without over-explaining.",
    },
    "Hard": {
        "min_blank_count": 5,
        "expected_code_tokens": {"min": 150, "max": 340},
        "scenario_guidance": "Use a richer scenario with realistic constraints and enough detail to justify the coding task.",
    },
}


def get_completion_0temp(prompt, engine="gpt-4o-aispeaking"):
    response = client.chat.completions.create(
        model=engine,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    content = response.choices[0].message.content
    if content.startswith("```json") and content.endswith("```"):
        content = content[7:-3].strip()
    return content


def extract_json(content):
    if content is None:
        return None

    if isinstance(content, (dict, list)):
        return content

    if not isinstance(content, str):
        content = str(content)

    stripped = content.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:]
    if stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    stripped = stripped.strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        match = re.search(r"\[.*\]", stripped, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    return None


def normalize_qc_payload(payload):
    if not isinstance(payload, dict):
        return {"qc_result": "fail", "reasons": ["Unable to parse QC response."], "raw_response": payload}

    normalized = dict(payload)
    qc_value = normalized.get("qc_result", normalized.get("status", "fail"))
    qc_text = str(qc_value).strip().lower()
    if qc_text not in {"pass", "fail"}:
        qc_text = "fail"
    normalized["qc_result"] = qc_text
    if "status" in normalized:
        normalized.pop("status", None)

    reasons = normalized.get("reasons", [])
    if isinstance(reasons, str):
        reasons = [reasons]
    elif not isinstance(reasons, list):
        reasons = [str(reasons)] if reasons else []
    normalized["reasons"] = [str(reason) for reason in reasons if str(reason).strip()]
    return normalized


def filter_unique_answers(answers: Iterable[Any]) -> List[Any]:
    unique_answers = []
    seen = set()

    for answer in answers:
        if isinstance(answer, dict):
            normalized = json.dumps(answer, sort_keys=True, default=str)
            dedupe_key = normalized.lower()
        else:
            normalized = str(answer)
            dedupe_key = normalized.strip().lower()

        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        unique_answers.append(answer)

    return unique_answers


def format_alternate_answers(answers: Any) -> str:
    if not answers:
        return "No alternate answers provided."

    lines = []

    if isinstance(answers, dict):
        items = answers.items()
    else:
        items = enumerate(answers, start=1)

    for key, value in items:
        if isinstance(value, dict) and "alternates" in value:
            alternates = filter_unique_answers(value.get("alternates", []))
            lines.append(f"{key}: {value.get('answer', '')}")
            for alt_index, alt in enumerate(alternates, start=1):
                lines.append(f"  - Alt {alt_index}: {alt}")
        elif isinstance(value, list):
            alternates = filter_unique_answers(value)
            lines.append(f"{key}:")
            for alt_index, alt in enumerate(alternates, start=1):
                lines.append(f"  - Alt {alt_index}: {alt}")
        else:
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


def get_scenario_description(difficulty: str) -> str:
    rules = Difficulty_level_json.get(difficulty, Difficulty_level_json["Medium"])
    return (
        f"Difficulty: {difficulty}\n"
        f"Scenario guidance: {rules['scenario_guidance']}\n"
        f"Expected code token range: {rules['expected_code_tokens']['min']} to {rules['expected_code_tokens']['max']} tokens\n"
        f"Blank count requirement: {rules['min_blank_count']} blanks"
    )


def _safe_answers_text(answers: Any) -> str:
    if isinstance(answers, dict):
        return format_alternate_answers(answers)
    if isinstance(answers, list):
        return format_alternate_answers({f"Blank {index}": answer for index, answer in enumerate(answers, start=1)})
    return str(answers)


def evaluate_code_snippet(topic, sub_topic, difficulty, code_snippet, scenario, instructions, answers):
    difficulty_rules = Difficulty_level_json.get(difficulty, Difficulty_level_json["Medium"])
    prompt = f"""
You are evaluating a coding assessment question.

Return only valid JSON with keys: qc_result and reasons.

Evaluation rules:
- The snippet must contain exactly {difficulty_rules['min_blank_count']} blanks.
- Each blank must be marked in the form 'Blank N: Enter your code here'.
- Surrounding code must be syntactically coherent and useful as a coding assessment.
- Check that the snippet length is roughly within the expected token range for this difficulty: {difficulty_rules['expected_code_tokens']['min']} to {difficulty_rules['expected_code_tokens']['max']} tokens.
- Do not leak answers into the visible code or instructions.

Topic: {topic}
Sub-topic: {sub_topic}
Difficulty: {difficulty}
Scenario: {scenario}
Instructions: {instructions}
Answers:\n{_safe_answers_text(answers)}

Code snippet to evaluate:\n{code_snippet}

Return JSON in this format:
{{
  "qc_result": "pass" or "fail",
  "reasons": ["..."]
}}
""".strip()
    return get_completion_0temp(prompt)


def evaluate_instructions(code_snippet, instructions, answers, difficulty):
    prompt = f"""
You are evaluating the instructions for a coding assessment question.

Return only valid JSON with keys: qc_result and reasons.

Check that the instructions:
- Are conceptual and do not directly reveal the answer.
- Refer to the code snippet and blanks clearly enough for a candidate to solve the task.
- Use exact variable names, strings, or code context only when needed.
- Match the difficulty level: {difficulty}.

Code snippet:\n{code_snippet}

Instructions:\n{instructions}

Answers:\n{_safe_answers_text(answers)}

Return JSON in this format:
{{
  "qc_result": "pass" or "fail",
  "reasons": ["..."],
  "revamped_instructions": "..."  // only include if qc_result is fail
}}
""".strip()
    return get_completion_0temp(prompt)


def qc_and_revamp_scenario(topic, subtopic, difficulty, scenario, instructions, code_snippet, answers):
    prompt = f"""
You are evaluating a scenario for a coding assessment question.

Return only valid JSON with keys: qc_result, reasons, and optionally revamped_scenario when failed.
If the scenario contains HTML tags, CSS, or any non-scenario markup, this is an automatic FAIL.
The scenario must start with "You are working on..." and must not contain business/role-based phrasing or unrelated content.
If qc_result is fail, revamped_scenario must be a PLAIN STRING containing ONLY the rewritten scenario text.
If topic or subtopic also need to change, return them as separate top-level keys such as revamped_topic or revamped_subtopic.

Evaluate whether the scenario is clear, relevant, realistic, and aligned to the topic and difficulty.

Topic: {topic}
Subtopic: {subtopic}
Difficulty: {difficulty}
Scenario: {scenario}
Instructions: {instructions}
Code snippet:\n{code_snippet}
Answers:\n{_safe_answers_text(answers)}

Return JSON in this format:
{{
    "qc_result": "pass" or "fail",
    "reasons": ["..."],
    "revamped_scenario": "..."  // only include if qc_result is fail and must be a plain string
}}
""".strip()
    raw_response = get_completion_0temp(prompt)
    extracted = extract_json(raw_response)
    normalized = normalize_qc_payload(extracted if isinstance(extracted, dict) else {"qc_result": "fail", "reasons": ["Unable to parse scenario QC response."], "raw_response": raw_response})
    return normalized


def generate_alternate_answers(topic, sub_topic, difficulty, code_snippet, instructions, answers):
    """
    Generate alternate valid answers for each blank while preserving equivalent logic.
    """
    prompt = f"""
You are generating alternate valid answers for a coding assessment.

For each blank in the provided answers dictionary, generate 3 to 5 alternate answers
that represent equivalent logic using different syntax or approach.

Important rules:
- Return ONLY valid JSON.
- The JSON must be an object where each key is the blank label (for example, "Blank 1").
- Each value must be a list of strings.
- Do not include explanations.

Topic: {topic}
Sub-topic: {sub_topic}
Difficulty: {difficulty}
Code snippet:\n{code_snippet}
Instructions:\n{instructions}
Original answers:\n{_safe_answers_text(answers)}

Expected output format:
{{
  "Blank 1": ["alt1", "alt2", "alt3"],
  "Blank 2": ["alt1", "alt2", "alt3"]
}}
""".strip()

    raw_response = get_completion_0temp(prompt)
    extracted = extract_json(raw_response)

    parsed = None
    if isinstance(extracted, dict):
        parsed = extracted
    elif isinstance(extracted, str):
        try:
            parsed = json.loads(extracted)
        except json.JSONDecodeError:
            parsed = None
    elif isinstance(raw_response, str):
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            parsed = None

    if not isinstance(parsed, dict):
        return {}

    cleaned = {}
    for blank, alt_list in parsed.items():
        original_answer = str(answers.get(blank, "")).strip() if isinstance(answers, dict) else ""

        if not isinstance(alt_list, list):
            continue

        unique_alts = filter_unique_answers([str(item).strip() for item in alt_list if str(item).strip()])
        filtered_alts = [alt for alt in unique_alts if alt.strip().lower() != original_answer.lower()]

        final_list = [original_answer] + filtered_alts if original_answer else filtered_alts

        if final_list:
            cleaned[blank] = final_list

    return cleaned


def qc_and_revamp_chain(topic, sub_topic, difficulty, code_snippet, instructions, answers, scenario):
    code_snippet_result_raw = evaluate_code_snippet(
        topic=topic,
        sub_topic=sub_topic,
        difficulty=difficulty,
        code_snippet=code_snippet,
        scenario=scenario,
        instructions=instructions,
        answers=answers,
    )
    code_snippet_result = normalize_qc_payload(extract_json(code_snippet_result_raw) or {"qc_result": "fail", "reasons": ["Unable to parse code snippet QC response."], "raw_response": code_snippet_result_raw})

    instructions_result_raw = evaluate_instructions(
        code_snippet=code_snippet,
        instructions=instructions,
        answers=answers,
        difficulty=difficulty,
    )
    instructions_result = normalize_qc_payload(extract_json(instructions_result_raw) or {"qc_result": "fail", "reasons": ["Unable to parse instructions QC response."], "raw_response": instructions_result_raw})

    scenario_result_raw = qc_and_revamp_scenario(
        topic=topic,
        subtopic=sub_topic,
        difficulty=difficulty,
        scenario=scenario,
        instructions=instructions,
        code_snippet=code_snippet,
        answers=answers,
    )
    scenario_result = normalize_qc_payload(scenario_result_raw if isinstance(scenario_result_raw, dict) else extract_json(scenario_result_raw) or {"qc_result": "fail", "reasons": ["Unable to parse scenario QC response."], "raw_response": scenario_result_raw})

    alternate_answers = generate_alternate_answers(
        topic=topic,
        sub_topic=sub_topic,
        difficulty=difficulty,
        code_snippet=code_snippet,
        instructions=instructions,
        answers=answers,
    )

    overall_result = "pass"
    if any(str(result.get("qc_result", "")).strip().lower() != "pass" for result in [code_snippet_result, instructions_result, scenario_result]):
        overall_result = "fail"

    combined_result = {
        "topic": topic,
        "sub_topic": sub_topic,
        "difficulty": difficulty,
        "scenario": scenario,
        "instructions": instructions,
        "code_snippet": code_snippet,
        "answers": answers,
        "alternate_answers": alternate_answers,
        "scenario_qc": scenario_result,
        "code_snippet_qc": code_snippet_result,
        "instructions_qc": instructions_result,
        "overall_qc_result": overall_result,
    }

    if str(scenario_result.get("qc_result", "")).strip().lower() == "fail" and scenario_result.get("revamped_scenario"):
        combined_result["revamped_scenario"] = scenario_result.get("revamped_scenario")

    if str(instructions_result.get("qc_result", "")).strip().lower() == "fail" and instructions_result.get("revamped_instructions"):
        combined_result["revamped_instructions"] = instructions_result.get("revamped_instructions")

    return combined_result
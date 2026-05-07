"""Extract a JSON array from LLM chat answers (markdown fences, prose)."""

from __future__ import annotations

import json
import re


def parse_json_array(answer: str) -> list:
    answer = answer.strip()
    answer = re.sub(r"^```(?:json)?\s*", "", answer)
    answer = re.sub(r"\s*```$", "", answer)
    m = re.search(r"\[.*\]", answer, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    return []

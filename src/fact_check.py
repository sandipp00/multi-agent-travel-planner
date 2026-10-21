"""Deterministic fact check of the planner's reply against the tool data.

The orchestrator model sometimes miscopies details it was given — pairing
the cheapest fare with the wrong airline, rounding a $76 total to $75, or
stretching a 12h layover to "13-hour". These checks compare the reply,
line by line, with the specialists' results and describe each mismatch so
it can be corrected (see `revise`) or shown to the traveler.
"""

import re
import unicodedata

from src.config import AGENT_MAX_TOKENS, MODEL_AGENT

# "$1,500", "$1 500" (thin/nbsp separators too), "$76", "$12.50"
_AMOUNT_RE = re.compile(r"\$\s?(\d{1,3}(?:[,    ]\d{3})+|\d+)(?:\.(\d{1,2}))?")
_HYPHENS = "\\-\u2010\u2011\u2012\u2013"  # escaped "-" first, then Unicode hyphens/dashes
# "13-hour layover", "12 h overnight layover", "12-hour lay-over"
_HOURS_BEFORE_LAYOVER_RE = re.compile(
    rf"(\d+(?:\.\d+)?)[\s{_HYPHENS}]*(?:hours?|hrs?|h)[\s{_HYPHENS}]*(?:\w+[\s{_HYPHENS}]+)?lay[\s{_HYPHENS}]?over",
    re.IGNORECASE,
)
# "layover of 12 hours", "layover of about 12h"
_HOURS_AFTER_LAYOVER_RE = re.compile(
    r"lay[\s\-‑]?over\s+(?:of\s+)?(?:about\s+|around\s+|~\s*|≈\s*)?(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b",
    re.IGNORECASE,
)
_NOTE_LAYOVER_RE = re.compile(r"Layover (\d+)h (\d+)m in ([A-Z]{3})")

# A number this close to a real one, without matching it, is a miscopy.
_NEAR_MISS_RATIO = 0.03
_NEAR_MISS_MIN_VALUE = 50
_LAYOVER_TOLERANCE_HOURS = 0.75

EDITOR_SYSTEM = """You are a careful editor. You get a travel plan and a list of factual \
errors in it, each with the correct value from the source data. Rewrite the plan fixing \
exactly those errors and nothing else: keep all other wording, structure, and formatting \
identical. Output only the corrected plan."""


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def _amounts(line: str) -> list:
    values = []
    for whole, cents in _AMOUNT_RE.findall(line):
        value = float(re.sub(r"[^\d]", "", whole))
        if cents:
            value += float(cents) / 10 ** len(cents)
        values.append(value)
    return values


def _options_of(result):
    if isinstance(result, dict):
        result = result.get("options", [])
    return [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []


def _entities(results: list) -> list:
    """Named things from the data, each with its prices and layovers."""
    entities = []
    for name, _args, result in results:
        for item in _options_of(result):
            if name == "search_flights":
                names = [part.strip() for part in str(item.get("airline", "")).split(",")]
                amounts = {item.get("price_usd")}
                layovers = [int(h) * 60 + int(m) for h, m, _ in _NOTE_LAYOVER_RE.findall(item.get("notes", ""))]
                label = f"{item.get('airline')} (${item.get('price_usd')})"
            elif name == "search_hotels":
                names = [str(item.get("name", ""))]
                amounts = {item.get("price_per_night_usd"), item.get("total_usd")}
                layovers = []
                label = str(item.get("name"))
            elif name == "search_activities":
                names = [str(item.get("name", ""))]
                amounts = {item.get("estimated_cost_usd")}
                layovers = []
                label = str(item.get("name"))
            else:
                continue
            entities.append({
                "kind": name,
                "names": [_normalize(n) for n in names if len(n.strip()) >= 3],
                "amounts": {float(a) for a in amounts if isinstance(a, (int, float))},
                "layovers": layovers,
                "label": label,
            })
    return entities


def _known_amounts(results: list, entities: list) -> set:
    known = set()
    for entity in entities:
        known |= entity["amounts"]
    for name, _args, result in results:
        if name == "analyze_budget" and isinstance(result, dict):
            known |= {float(v) for v in result.values() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    # Plans legitimately state differences and sums ("$139 more than SWISS").
    base = list(known)
    known |= {round(abs(a - b), 2) for a in base for b in base} | {round(a + b, 2) for a in base for b in base}
    return known


def check(reply: str, results: list) -> list:
    """Return human-readable descriptions of statements that contradict the data."""
    entities = _entities(results)
    known = _known_amounts(results, entities)
    flights = [e for e in entities if e["kind"] == "search_flights"]
    issues = []

    for raw_line in reply.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = _normalize(line)
        mentioned = [e for e in entities if any(n in normalized for n in e["names"])]
        snippet = line if len(line) <= 140 else line[:137] + "..."

        for amount in _amounts(line):
            owners = [e for e in entities if amount in e["amounts"]]
            # A price that belongs to one option, written next to a different one.
            if owners and mentioned and not any(o in mentioned for o in owners):
                same_kind = [m for m in mentioned if m["kind"] == owners[0]["kind"]]
                if same_kind:
                    issues.append(
                        f'"{snippet}" — ${amount:,.0f} belongs to {owners[0]["label"]}, '
                        f'not {", ".join(m["label"] for m in same_kind)}.'
                    )
                    continue
            # A number just off a real one: rounded or miscopied.
            if amount not in known:
                near = [k for k in known if k >= _NEAR_MISS_MIN_VALUE and 0 < abs(amount - k) <= k * _NEAR_MISS_RATIO]
                if near:
                    closest = min(near, key=lambda k: abs(amount - k))
                    issues.append(f'"{snippet}" — ${amount:,.0f} should be ${closest:,.0f} (the exact figure in the data).')

        if "layover" in normalized.replace(" ", "") or "lay over" in normalized:
            stated = [float(h) for h in _HOURS_BEFORE_LAYOVER_RE.findall(line) + _HOURS_AFTER_LAYOVER_RE.findall(line)]
            candidates = [e for e in mentioned if e["kind"] == "search_flights"] or flights
            real = [minutes / 60 for e in candidates for minutes in e["layovers"]]
            for hours in stated:
                if real and not any(abs(hours - r) <= _LAYOVER_TOLERANCE_HOURS for r in real):
                    closest = min(real, key=lambda r: abs(hours - r))
                    issues.append(
                        f'"{snippet}" — no layover of about {hours:g} hours in the data; '
                        f"the closest is {int(closest)}h {round((closest % 1) * 60)}m."
                    )

    # The same mistake repeated on several lines only needs fixing once per line.
    return list(dict.fromkeys(issues))


def revise(client, reply: str, issues: list) -> str:
    """Ask the (smaller) agent model to fix exactly the listed errors."""
    response = client.chat.completions.create(
        model=MODEL_AGENT,
        max_tokens=AGENT_MAX_TOKENS * 2,
        messages=[
            {"role": "system", "content": EDITOR_SYSTEM},
            {"role": "user", "content": "Errors to fix:\n- " + "\n- ".join(issues) + "\n\nPlan:\n" + reply},
        ],
    )
    return response.choices[0].message.content or reply

from __future__ import annotations

from .purpose_models import PurposeFacts

_VOWEL_Y = set("aeiou")

_INFO_VERBS: set[str] = {
    "authenticate", "authorize", "compute", "enrich", "fetch",
    "find", "get", "load", "parse", "process", "query", "read",
    "search", "transform", "validate",
}


def _pluralize(word: str) -> str:
    """     pluralize.

    Args:
        word (str): Word.

    Returns:
        str: Description.
    """
    if not word:
        return word
    lower = word.lower()
    if lower.endswith("s"):
        return word
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in _VOWEL_Y:
        return word[:-1] + "ies"
    if lower.endswith(("sh", "ch", "x", "z")):
        return word + "es"
    return word + "s"


def _gerund(verb: str) -> str:
    """     gerund.

    Args:
        verb (str): Verb.

    Returns:
        str: Description.
    """
    lower = verb.lower()
    if lower.endswith("ee"):
        return verb + "ing"
    if lower.endswith("ie"):
        return verb[:-2] + "ying"
    if lower.endswith("e"):
        return verb[:-1] + "ing"
    if len(lower) >= 3 and lower[-1] not in "aeiouywx" and lower[-2] in "aeiou" and lower[-3] not in "aeiou":
        return verb + verb[-1] + "ing"
    return verb + "ing"


def _humanize_obj(verb: str, obj: str) -> str:
    """     humanize obj.

    Args:
        verb (str): Verb.
        obj (str): Obj.

    Returns:
        str: Description.
    """
    lower = obj.lower()
    if lower == "user" and verb.lower() in _INFO_VERBS:
        return "user information"
    return _pluralize(obj)


def _render_phrase(phrase: str) -> str:
    """     render phrase.

    Args:
        phrase (str): Phrase.

    Returns:
        str: Description.
    """
    parts = phrase.split(" ", 1)
    verb = parts[0]
    obj = parts[1] if len(parts) > 1 else None
    if obj is None:
        return verb
    human_obj = _humanize_obj(verb, obj)
    return f"{verb} {human_obj}"


class PurposeSynthesizer:
    """Purposesynthesizer."""
    def synthesize(self, facts: PurposeFacts) -> str | None:
        """    Synthesize.

    Args:
        facts (PurposeFacts): Facts.

    Returns:
        str | None: Description.
    """
        if not facts.outcomes and not facts.major_steps and not facts.side_effects:
            return None

        # Case 1: Outcome + Steps
        if facts.outcomes and facts.major_steps:
            return self._case_outcome_steps(facts)

        # Case 2: Outcome only
        if facts.outcomes:
            return self._case_outcome_only(facts)

        # Case 3: Steps only
        if facts.major_steps:
            return self._case_steps_only(facts)

        # Case 4: Side effects only
        if facts.side_effects:
            return self._case_side_effects(facts)

        return None

    def _case_outcome_steps(self, facts: PurposeFacts) -> str:
        """     case outcome steps.

    Args:
        facts (PurposeFacts): Facts.

    Returns:
        str: Description.
    """
        steps = facts.major_steps
        outcome = facts.outcomes[0]

        step_objs = [s.split(" ", 1)[1] if " " in s else None for s in steps]
        shared = step_objs[0] if len(set(step_objs)) == 1 and step_objs[0] is not None else None

        outcome_verb = outcome.split(" ", 1)[0]

        if shared:
            step_verbs = [s.split(" ", 1)[0] for s in steps]
            combined = f"{step_verbs[0]} and {step_verbs[1]} {shared}" if len(step_verbs) == 2 else \
                       ", ".join(f"{v}" for v in step_verbs[:1]) + f" and {step_verbs[-1]} {shared}"
            result = f"{combined} before {_gerund(outcome_verb)}."
        else:
            rendered = [_render_phrase(s) for s in steps]
            if len(rendered) == 2:
                result = f"{rendered[0]} and {rendered[1]} before {_gerund(outcome_verb)}."
            else:
                *rest, last = rendered
                result = ", ".join(rest) + ", and " + last + f" before {_gerund(outcome_verb)}."

        return result[0].upper() + result[1:]

    def _case_outcome_only(self, facts: PurposeFacts) -> str:
        """     case outcome only.

    Args:
        facts (PurposeFacts): Facts.

    Returns:
        str: Description.
    """
        outcome = facts.outcomes[0]
        parts = outcome.split(" ", 1)
        verb = parts[0]
        obj = parts[1] if len(parts) > 1 else None
        if obj is None:
            return verb[0].upper() + verb[1:] + "."
        return f"{verb[0].upper()}{verb[1:]} {obj}."

    def _case_steps_only(self, facts: PurposeFacts) -> str:
        """     case steps only.

    Args:
        facts (PurposeFacts): Facts.

    Returns:
        str: Description.
    """
        rendered = [_render_phrase(s) for s in facts.major_steps]
        if len(rendered) == 1:
            return rendered[0][0].upper() + rendered[0][1:] + "."
        if len(rendered) == 2:
            return f"{rendered[0]} and {rendered[1]}.".capitalize()
        *rest, last = rendered
        result = ", ".join(rest) + ", and " + last + "."
        return result[0].upper() + result[1:]

    def _case_side_effects(self, facts: PurposeFacts) -> str:
        """     case side effects.

    Args:
        facts (PurposeFacts): Facts.

    Returns:
        str: Description.
    """
        rendered = [_render_phrase(s) for s in facts.side_effects]
        if len(rendered) == 1:
            return f"{rendered[0][0].upper()}{rendered[0][1:]} to downstream consumers."
        if len(rendered) == 2:
            return f"{rendered[0][0].upper()}{rendered[0][1:]} and {rendered[1]} to downstream consumers."
        *rest, last = rendered
        result = ", ".join(rest) + ", and " + last + " to downstream consumers."
        return result[0].upper() + result[1:]

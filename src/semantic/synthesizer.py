from __future__ import annotations

from .models import Action

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


class SummarySynthesizer:
    """Summarysynthesizer."""
    def synthesize(self, actions: list[Action]) -> str | None:
        """    Synthesize.

    Args:
        actions (list[Action]): Actions.

    Returns:
        str | None: Description.
    """
        if not actions:
            return None
        rendered = [self._render(a) for a in actions]
        return self._join(rendered)

    def _render(self, action: Action) -> str:
        """     render.

    Args:
        action (Action): Action.

    Returns:
        str: Description.
    """
        verb = action.verb
        obj = action.obj
        if obj is None:
            return verb
        human_obj = _humanize_obj(verb, obj)
        return f"{verb} {human_obj}"

    def _join(self, parts: list[str]) -> str:
        """     join.

    Args:
        parts (list[str]): Parts.

    Returns:
        str: Description.
    """
        if len(parts) == 1:
            result = parts[0]
        elif len(parts) == 2:
            result = f"{parts[0]} and {parts[1]}"
        else:
            *rest, last = parts
            result = ", ".join(rest) + ", and " + last
        return result[0].upper() + result[1:] + "."

from pathlib import Path
from typing import Any, Optional


class ConfigParser:
    """Configparser."""
    def __init__(self, path: Path) -> None:
        """Initialise ConfigParser."""
        self.path = path
        self._data: dict[str, Any] = {}

    def get_config(self, key: str, default: Optional[Any] = None) -> Any:
        """    Return config.

    Args:
        key (str): Description.
        default (Optional[Any]): Description.

    Returns:
        Any: Description.
    """
        return self._data.get(key, default)

    def validate_path(self) -> bool:
        """    Validate path.

    Returns:
        bool: Description.
    """
        if not self.path.exists():
            return False
        if not self.path.is_file():
            return False
        return True

    def parse_with_fallback(self, fallback: dict[str, Any]) -> dict[str, Any]:
        """    Parse with fallback and return the result.

    Args:
        fallback (dict[str, Any]): Description.

    Returns:
        dict[str, Any]: Description.
    """
        result: dict[str, Any] = {}
        for k, v in fallback.items():
            if k in self._data:
                result[k] = self._data[k]
            else:
                result[k] = v
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    combined_key = f"{k}.{k2}"
                    if combined_key in self._data:
                        result[combined_key] = self._data[combined_key]
        return result

    @staticmethod
    def default_config() -> dict[str, Any]:
        """    Default config.

    Returns:
        dict[str, Any]: Description.
    """
        return {"version": 1, "debug": False}

    def complex_parse(self) -> dict[str, Any]:
        """    Complex parse.

    Returns:
        dict[str, Any]: Description.
    """
        result: dict[str, Any] = {}
        for key, value in self._data.items():
            if isinstance(value, dict) and "type" in value:
                if value["type"] == "string":
                    result[key] = str(value.get("default", ""))
                elif value["type"] == "integer":
                    result[key] = int(value.get("default", 0))
                elif value["type"] == "boolean":
                    result[key] = bool(value.get("default", False))
                elif value["type"] == "list":
                    items = value.get("items", [])
                    processed = []
                    for item in items:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                processed.append({k: v})
                        else:
                            processed.append(item)
                    result[key] = processed
                elif value["type"] == "nested":
                    nested = {}
                    for nk, nv in value.get("properties", {}).items():
                        if isinstance(nv, dict) and "default" in nv:
                            nested[nk] = nv["default"]
                        else:
                            nested[nk] = nv
                    result[key] = nested
                else:
                    result[key] = value.get("default")
            else:
                result[key] = value
        return result

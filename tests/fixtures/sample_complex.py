from typing import Any


def deeply_nested(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deeply nested."""
    result: list[dict[str, Any]] = []
    for item in items:
        if "type" in item:
            t = item["type"]
            if t == "a":
                for sub in item.get("sub", []):
                    if sub.get("active"):
                        for x in sub.get("values", []):
                            if x > 0:
                                for y in range(x):
                                    result.append({"a": y})
                                    if y % 2 == 0:
                                        if y > 10:
                                            result.append({"even_large": y})
                                        else:
                                            result.append({"even_small": y})
                                    else:
                                        if y > 10:
                                            result.append({"odd_large": y})
            elif t == "b":
                for sub in item.get("sub", []):
                    if sub.get("enabled"):
                        for i in range(10):
                            for j in range(10):
                                if i + j > 5:
                                    if i > j:
                                        if i - j > 2:
                                            result.append({"diff": i - j})
                                        else:
                                            result.append({"small_diff": i - j})
            elif t == "c":
                nested = item.get("nested", {})
                for k, v in nested.items():
                    if isinstance(v, dict):
                        for k2, v2 in v.items():
                            if isinstance(v2, list):
                                for elem in v2:
                                    if elem not in result:
                                        result.append(elem)
                            elif v2 is not None:
                                result.append({f"{k}.{k2}": v2})
        else:
            result.append(item)
    return result

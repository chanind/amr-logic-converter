import re


def fmt_logic(text: str) -> str:
    """Strip excess whitespace and newlines from a string."""
    updated_txt = re.sub(r"[\s\n]+", " ", text.strip(), flags=re.MULTILINE)
    updated_txt = re.sub(r"(\()\s+", r"\1", updated_txt)
    updated_txt = re.sub(r"\s+(\))", r"\1", updated_txt)
    return updated_txt

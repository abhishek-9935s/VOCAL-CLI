"""Render untrusted text without terminal control or bidirectional formatting codes."""
import unicodedata


def unsafe_character(char: str) -> bool:
    # Newlines and tabs are permitted in commands, but remain visible as line
    # breaks / spaces. Control characters and bidi controls can spoof the card.
    return char not in "\n\t" and (unicodedata.category(char).startswith("C") or unicodedata.category(char) in {"Zl", "Zp"})


def safe_display(value: str) -> str:
    def escape(char: str) -> str:
        code = ord(char)
        if code <= 0xff:
            return f"\\x{code:02x}"
        if code <= 0xffff:
            return f"\\u{code:04x}"
        return f"\\U{code:08x}"

    return "".join(escape(char) if unsafe_character(char) else char for char in value)

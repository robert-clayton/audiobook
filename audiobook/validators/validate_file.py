"""Text cleaning and validation for scraped chapter files.

Fixes encoding issues, expands acronyms, applies series-specific replacements,
and warns about remaining undecodable characters.
"""

import os
import re
from ..utils.colors import GREEN, RED, YELLOW, PURPLE, RESET

KNOWN_ACRONYMS = {
    "exp": "E-X-P",
    "mps": "M-P-S",
    "hps": "H-P-S",
    "mp/s": "M-P-S",
    "hp/s": "H-P-S",
}

REPLACEMENTS = {
    # Unreadable replacements
    b'\xe2\x80\x9c': b'"',          # Left double quotation mark “
    b'\xe2\x80\x9d': b'"',          # Right double quotation mark ”
    b'\xe2\x80\x98': b"'",          # Left single quotation mark ‘
    b'\xe2\x80\x99': b"'",          # Right single quotation mark ’
    b'\xe2\x80\xa6': b'...',        # Ellipsis …
    b'%': b'-percent',              # Percent sign %
    b'\xe2\x80\x94': b';',          # Em dash —
    b'\xe2\x80\x93': b'-',          # En dash –
    b'\xc2\xa0': b' ',              # Non-breaking space
    b'\xc2\xad': b'',               # Soft hyphen (invisible, used for line breaks)
    b'\xe2\x80\x8b': b'',           # Zero-width space (invisible)
    b'\xe2\x80\x8c': b'',           # Zero-width non-joiner (invisible)
    b'\xe2\x80\x8d': b'',           # Zero-width joiner (invisible)
    b'\xe2\x80\xb2': b" feet",      # Prime symbol ′ (often used for feet, etc.)
    b'\xe2\x80\xb3': b' inches',    # Double prime symbol ″ (often used for inches, etc.)
}

def validate(file_name, series_specific_replacements, encoding="utf-8"):
    """Clean a text file for TTS consumption and write the result as a new ``_cleaned.txt`` file.

    Applies encoding fixes, acronym expansion, series-specific word replacements,
    and bracket stripping. Warns if undecodable characters remain.

    Args:
        file_name: Path to the raw text file.
        series_specific_replacements: Dict of word-to-replacement mappings, or None.
        encoding: Text encoding to use for reading/writing.

    Returns:
        Path to the newly created cleaned file.
    """
    with open(file_name, "r", encoding=encoding) as file:
        lines = file.readlines()

    # Convert lines to a single string
    text = ''.join(lines)

    # Perform varied replacements
    for unreadable, replacement in REPLACEMENTS.items():
        text = text.replace(unreadable.decode(encoding), replacement.decode(encoding))

    # Acronym replacements
    text = replace_series_specific(text, series_specific_replacements)
    text = replace_acronyms(text)

    # Use regex to replace [*] with *
    text = re.sub(r'\[(.*?)\]', r'\1', text)

    # Replace number/number patterns (e.g. "100/100") with "number out of number" for TTS
    # Negative lookahead prevents partial matching of dates like "3/15/2024"
    text = re.sub(r'(\d+)\s*/\s*(\d+)(?!\s*/\s*\d)', r'\1 out of \2', text)

    # Replace +/- before numbers with "plus"/"minus" for TTS (avoid word-hyphens like "well-known")
    text = re.sub(r'(?<!\w)\+(\d)', r'plus \1', text)
    text = re.sub(r'(?<!\w)-(\d)', r'minus \1', text)

    # Write the cleaned data back to a new file
    cleaned_file_name = os.path.splitext(file_name)[0] + "_cleaned.txt"
    with open(cleaned_file_name, "w", encoding=encoding) as file:
        file.write(text)

    # Check for any remaining undecodable characters
    raw_data = text.encode(encoding)
    undecodable_chars = find_undecodable_chars(raw_data, encoding)
    if undecodable_chars:
        print(f"{YELLOW}Warning: Found remaining undecodable characters:{RESET}")
        for char, pos in undecodable_chars:
            print(f"\t{PURPLE}Character:{RESET} {char!r}{PURPLE}, Position: {RESET}{pos}")

    return cleaned_file_name

def replace_acronyms(text):
    """Expand known acronyms to hyphenated letter form while preserving speaker tags.

    Args:
        text: Input text that may contain ``<<SPEAKER=...>>`` tags and acronyms.

    Returns:
        Text with acronyms replaced (e.g., "exp" becomes "E-X-P").
    """
    # Regex to find tags
    tag_pattern = r'<<[^>]+>>'
    
    # Replace tags with unique placeholders
    tags = {}
    tag_counter = 1
    for idx, match in enumerate(re.finditer(tag_pattern, text)):
        placeholder = f"__tag_{idx}__"
        tags[placeholder] = match.group(0)
        text = text.replace(match.group(0), placeholder)

    # Force known acronyms to hyphenated uppercase
    for acronym, replacement in KNOWN_ACRONYMS.items():
        text = re.sub(rf'\b{re.escape(acronym)}\b', replacement, text, flags=re.IGNORECASE)

    # # Replace all caps with hyphenated version
    # text = re.sub(r'\b([A-Z]+)\b', lambda match: '-'.join(match.group(1)), text)

    # Replace placeholders back with original tags
    for placeholder, tag in tags.items():
        text = text.replace(placeholder, tag)

    return text

def replace_series_specific(text, word_dict):
    """Replaces full words in text based on a dictionary of word mappings."""
    if word_dict is None:
        return text
    for word, replacement in word_dict.items():
        # \b ensures that only full words are matched
        text = re.sub(rf'\b{re.escape(word)}\b', replacement, text)
    return text

def find_undecodable_chars(raw_data, encoding):
    """Scan raw bytes for characters that cannot be decoded with the given encoding.

    Args:
        raw_data: Bytes to scan.
        encoding: Target encoding (e.g., "utf-8").

    Returns:
        List of (byte_value, position) tuples for each undecodable character.
    """
    undecodable_chars = []
    position = 0
    while position < len(raw_data):
        try:
            # Try to decode a portion of the data
            chunk = raw_data[position:position + 1024].decode(encoding)
            position += 1024
        except UnicodeDecodeError as e:
            # Capture the undecodable character and its position
            undecodable_chars.append((raw_data[position], position))
            position += 1  # Move past the undecodable character

    return undecodable_chars

if __name__ == "__main__":
    file_name = input(f"{GREEN}Please enter the text file name: {RESET}")
    if os.path.isfile(file_name):
        validate(file_name, {})
    else:
        print(f"{RED}File '{file_name}' does not exist.{RESET}")

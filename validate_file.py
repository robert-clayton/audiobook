import os
import re

KNOWN_ACRONYMS = {
    "exp": "EXP",
    "mps": "MPS",
    "hps": "HPS",
    "mp/s": "MPS",
    "hp/s": "HPS",
}

REPLACEMENTS = {
        b'\xe2\x80\x9c': b'"',    # Left double quotation mark “
        b'\xe2\x80\x9d': b'"',    # Right double quotation mark ”
        b'\xe2\x80\x98': b"'",    # Left single quotation mark ‘
        b'\xe2\x80\x99': b"'",    # Right single quotation mark ’
        b'\xe2\x80\xa6': b'...',  # Ellipsis …
        b'%': b'-percent',        # Percent sign %
        b'\xe2\x80\x94': b';',    # Em dash — replaced with semicolon ;
    }

def validate(file_name, series_specific_replacements, encoding="utf-8"):
    with open(file_name, "r", encoding=encoding) as file:
        lines = file.readlines()

    # Convert lines to a single string
    text = ''.join(lines)

    # Perform smart quote replacements
    for smart_quote, replacement in REPLACEMENTS.items():
        text = text.replace(smart_quote.decode(encoding), replacement.decode(encoding))

    # Acronym replacements
    text = replace_series_specific(text, series_specific_replacements)
    text = replace_acronyms(text)

    # Use regex to replace [*] with *
    text = re.sub(r'\[(.*?)\]', r'\1', text)

    # Write the cleaned data back to a new file
    cleaned_file_name = os.path.splitext(file_name)[0] + "_cleaned.txt"
    with open(cleaned_file_name, "w", encoding=encoding) as file:
        file.write(text)

    print(f"Any issues have been replaced. Cleaned file saved as {cleaned_file_name}.")

    # Check for any remaining undecodable characters
    raw_data = text.encode(encoding)
    undecodable_chars = find_undecodable_chars(raw_data, encoding)
    if undecodable_chars:
        print("Warning: Found remaining undecodable characters:")
        for char, pos in undecodable_chars:
            print(f"Character: {char!r}, Position: {pos}")
    else:
        print("No remaining undecodable characters found.")

    return cleaned_file_name

def replace_acronyms(text):
    # Regex to find tags
    tag_pattern = r'<<[^>]+>>'
    
    # Replace tags with unique placeholders
    tags = {}
    tag_counter = 1
    for idx, match in enumerate(re.finditer(tag_pattern, text)):
        placeholder = f"__tag_{idx}__"
        tags[placeholder] = match.group(0)
        text = text.replace(match.group(0), placeholder)

    # Force known acronyms to uppercase
    for acronym, replacement in KNOWN_ACRONYMS.items():
        text = re.sub(rf'\b{re.escape(acronym)}\b', replacement, text, flags=re.IGNORECASE)

    # Replace acronyms with hyphenated version
    text = re.sub(r'\b([A-Z]+)\b', lambda match: '-'.join(match.group(1)), text)

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
    file_name = input("Please enter the text file name: ")
    if os.path.isfile(file_name):
        validate(file_name, {})
    else:
        print(f"File '{file_name}' does not exist.")

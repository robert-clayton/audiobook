import os

def find_and_replace_smart_quotes(file_name, encoding="utf-8"):
  replacements = {
    b'\xe2\x80\x9c': b'"',    # Left double quotation mark “
    b'\xe2\x80\x9d': b'"',    # Right double quotation mark ”
    b'\xe2\x80\x98': b"'",    # Left single quotation mark ‘
    b'\xe2\x80\x99': b"'",    # Right single quotation mark ’
    b'\xe2\x80\xa6': b'...',  # Ellipsis …
    b'%': b'-percent',        # Percent sign %
    b'\xe2\x80\x94': b';',   # Em dash — replaced with double vertical bars ||
  }
  
  # Read the file as raw binary data
  with open(file_name, "rb") as file:
    raw_data = file.read()

  # Replace smart quotes with standard ones
  for smart_quote, replacement in replacements.items():
    raw_data = raw_data.replace(smart_quote, replacement)

  # Write the cleaned data back to a new file
  cleaned_file_name = os.path.splitext(file_name)[0] + "_cleaned.txt"
  with open(cleaned_file_name, "wb") as file:
    file.write(raw_data)

  print(f"Any issues have been replaced. Cleaned file saved as {cleaned_file_name}.")

  # Check for any remaining undecodable characters
  undecodable_chars = find_undecodable_chars(raw_data, encoding)
  if undecodable_chars:
    print("Warning: Found remaining undecodable characters:")
    for char, pos in undecodable_chars:
      print(f"Character: {char!r}, Position: {pos}")
  else:
    print("No remaining undecodable characters found.")

  return cleaned_file_name

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
        find_and_replace_smart_quotes(file_name)
    else:
        print(f"File '{file_name}' does not exist.")

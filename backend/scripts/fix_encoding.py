"""
Fix Windows encoding issue in build_git_history.py.
Strips non-ASCII characters from print() statements only.
The code content strings (triple-quoted) are left intact since Python will
write them as bytes to the file system.
"""
import re
import unicodedata

input_file = "scripts/build_git_history.py"

with open(input_file, encoding='utf-8') as f:
    content = f.read()

# For each print() call, replace any non-ASCII chars in the string literals
def clean_print_line(match):
    line = match.group(0)
    # Replace all non-ASCII chars with '?'
    cleaned = ''
    for c in line:
        if ord(c) < 128:
            cleaned += c
        else:
            cleaned += '?'
    return cleaned

# Only process lines that contain print( 
lines = content.split('\n')
cleaned_lines = []
for line in lines:
    if 'print(' in line and any(ord(c) > 127 for c in line):
        cleaned_line = ''.join(c if ord(c) < 128 else '?' for c in line)
        cleaned_lines.append(cleaned_line)
    else:
        cleaned_lines.append(line)

result = '\n'.join(cleaned_lines)

with open(input_file, 'w', encoding='utf-8') as f:
    f.write(result)

print("Done. Cleaned print statements.")

# Verify the script can now run without encoding errors in print statements
print_lines = [(i+1, l) for i, l in enumerate(result.split('\n'))
               if 'print(' in l and any(ord(c) > 127 for c in l)]
if print_lines:
    print(f"WARNING: {len(print_lines)} print lines still have non-ASCII")
    for lineno, line in print_lines[:3]:
        print(f"  Line {lineno}: {line[:60]}")
else:
    print("All print statements are now ASCII-clean.")

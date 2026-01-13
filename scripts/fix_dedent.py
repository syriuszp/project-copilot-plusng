import os

file_path = "app/core/extractors/docx.py"
with open(file_path, "r") as f:
    lines = f.readlines()

new_lines = []
# Lines 74-91 (0-indexed 73-90)
start_idx = 73
end_idx = 90
target_indent = " " * 37

for i, line in enumerate(lines):
    if start_idx <= i <= end_idx:
        # Strip existing leading whitespace and apply target
        stripped = line.lstrip()
        if stripped: # Don't indent empty lines
             new_lines.append(target_indent + stripped)
        else:
             new_lines.append(line)
    else:
        new_lines.append(line)

with open(file_path, "w") as f:
    f.writelines(new_lines)

print("Fixed indentation.")

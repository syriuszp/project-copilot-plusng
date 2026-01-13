import os

file_path = "app/core/extractors/docx.py"
with open(file_path, "r") as f:
    lines = f.readlines()

new_lines = []
# Lines 74-91 correspond to indices 73-90 (0-indexed)
start_idx = 73
end_idx = 90
# Verify context
print(f"Line 74 (before): {lines[start_idx]}")
print(f"Line 91 (before): {lines[end_idx]}")

for i, line in enumerate(lines):
    if start_idx <= i <= end_idx:
        new_lines.append("    " + line)
    else:
        new_lines.append(line)

print(f"Line 74 (after): {new_lines[start_idx]}")

with open(file_path, "w") as f:
    f.writelines(new_lines)
print("Done.")

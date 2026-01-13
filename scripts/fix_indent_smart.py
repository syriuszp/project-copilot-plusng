import os

file_path = "app/core/extractors/docx.py"
with open(file_path, "r") as f:
    lines = f.readlines()

new_lines = []
# 0-indexed mapping
# Base indent is 37
base = " " * 37
# Level 1 is 41
l1 = " " * 41
# Level 2 is 45
l2 = " " * 45
# Level 3 is 49
l3 = " " * 49

indent_map = {
    73: base, # with tempfile...
    74: l1,   # tmp.write
    75: l1,   # tmp_path =
    77: base, # try:
    78: l1,   # res =
    79: l1,   # with open logging
    80: l2,   # f.write
    82: l1,   # if res.content
    83: l2,   # text.append
    84: l1,   # else
    86: l2,   # if res.metadata...
    87: l3,   # text.append
    88: base, # finally
    89: l1,   # if os.path
    90: l2    # os.unlink
}

for i, line in enumerate(lines):
    if i in indent_map:
        stripped = line.lstrip()
        if stripped:
             new_lines.append(indent_map[i] + stripped)
        else:
             new_lines.append(line)
    else:
        new_lines.append(line)

with open(file_path, "w") as f:
    f.writelines(new_lines)

print("Fixed indentation smartly.")

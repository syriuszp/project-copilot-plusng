import os

file_path = "app/core/extractors/docx.py"
with open(file_path, "r") as f:
    lines = f.readlines()

new_lines = []
indenting = False
start_marker = "with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:"
end_marker = "except Exception as e:"
# The end marker we want is the one closing the 'try' block started BEFORE the 'with' block.
# Actually, the 'try' block starts at line 67. The 'except' is at line 92.
# Lines 74-91 (inclusive) need indenting.
# Line 91 is 'os.unlink(tmp_path)'.
# Line 92 is 'except Exception as e:'.

for i, line in enumerate(lines):
    stripped = line.lstrip()
    if start_marker in line:
        indenting = True
    
    if indenting:
        # Check if we hit the 'except' block that closes the outer try
        # formatting of that line is likely '                                 except Exception as e:' (33 spaces)
        if line.strip().startswith("except Exception as e:") and len(line) - len(line.lstrip()) == 33:
             indenting = False
    
    if indenting:
        # Add 4 spaces
        new_lines.append("    " + line)
    else:
        new_lines.append(line)

with open(file_path, "w") as f:
    f.writelines(new_lines)

print("Fixed indentation.")

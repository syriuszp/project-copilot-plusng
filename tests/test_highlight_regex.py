
import pytest
import re

def highlight_logic(query, content_to_show):
    # Copy of logic from search.py
    if query and content_to_show:
        tokens = [t for t in re.split(r"\s+", query.strip()) if t]
        if tokens:
             pattern_str = "|".join([re.escape(t) for t in tokens])
             pattern = re.compile(pattern_str, re.IGNORECASE)
             highlighted = pattern.sub(lambda m: f"**:{'orange'}[{m.group(0)}]**", content_to_show)
             return highlighted, pattern_str
    return content_to_show, ""

def test_highlight_regex_escaping():
    # Case 1: Simple
    q = "test plan"
    text = "This is a Test Plan document."
    hl, pat = highlight_logic(q, text)
    
    assert "Test" in hl
    assert "Plan" in hl
    assert "**:" in hl # check if highlighted
    assert pat == "test|plan"

def test_highlight_regex_special_chars():
    # Case 2: Special chars (parens)
    q = "function(a)"
    text = "def function(a): pass"
    hl, pat = highlight_logic(q, text)
    
    # regex should escape ( and )
    # pattern should be function\(a\)
    assert re.search(r"function\\\(a\\\)", pat) or "function\\(a\\)" in pat
    assert "**:" in hl
    
    # Verify split logic
    # "function(a)" splits by whitespace? It is one token.
    # q = "func (param)"
    q2 = "func (param)"
    hl2, pat2 = highlight_logic(q2, text)
    # pat2 should be func|\(param\)
    assert "func" in pat2
    assert "\\(param\\)" in pat2

def test_highlight_or_logic():
    q = "foo bar"
    text = "Only foo is here"
    hl, pat = highlight_logic(q, text)
    
    assert "foo" in pat
    assert "bar" in pat
    # verify 'foo' IS highlighted
    assert "**:" in hl 
    # verify rest of text remains
    assert "Only " in hl

import re
from django import template
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(is_safe=False)
def format_question(value):
    """Format question text for display:
    - escape HTML
    - bold leading subquestion labels (a., b., c., etc.) and top-level numbers
    - convert newlines to <br>
    """
    if not value:
        return ''
    text = str(value)
    esc = conditional_escape(text)

    # Bold labels at the start of lines: 'a.' or 'a)' or '1.' etc.
    def _bold_label(match):
        label = match.group(1)
        rest = match.group(2) or ''
        return f"<strong>{escape(label)}</strong>{rest}"

    # Pattern: line start, optional whitespace, (label), then whitespace
    pattern = re.compile(r"(?m)^(\s*([0-9]+[\.\)]|[a-eA-E][\.\)]))\s*(.*)$")

    lines = esc.splitlines()
    out_lines = []
    for line in lines:
        m = pattern.match(line)
        if m:
            label = m.group(2)
            rest = m.group(3)
            out_lines.append(f"<strong>{escape(label)}</strong> {rest}")
        else:
            out_lines.append(line)

    html = '<br>'.join(out_lines)
    return mark_safe(html)

"""Display-only C token colouring; compiler diagnostics remain authoritative."""
import re

KEYWORDS = set('auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while _Alignas _Alignof _Atomic _Bool _Complex _Generic _Imaginary _Noreturn _Static_assert _Thread_local'.split())
TOKENS = re.compile(
    r'(?P<comment>//[^\n]*|/\*[\s\S]*?(?:\*/|\Z))'
    r'|(?P<string>"(?:\\.|[^"\\\n])*(?:"|(?=\n)|\Z)|\'(?:\\.|[^\'\\\n])*(?:\'|(?=\n)|\Z))'
    r'|(?P<directive>^[ \t]*\#[^\n]*)'
    r'|(?P<number>\b(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)[uUlLfF]*\b)'
    r'|(?P<word>\b[A-Za-z_]\w*\b)', re.MULTILINE)


def spans(source):
    for match in TOKENS.finditer(source):
        kind = match.lastgroup
        if kind == 'word':
            if match.group() not in KEYWORDS:
                continue
            kind = 'keyword'
        yield kind, match.start(), match.end()

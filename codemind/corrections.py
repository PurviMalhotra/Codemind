"""Explicit source edits for preview. Checking a preview does not prove correctness."""
from dataclasses import dataclass

from .engine import FixIt
from .syntax import TOKENS


@dataclass
class Suggestion:
    title: str
    source: str
    line: int


def byte_offset(source, line, column):
    """GCC/Clang fix-it columns are 1-based UTF-8 byte offsets, not characters."""
    lines = source.splitlines(keepends=True)
    if line == len(lines) + 1 and column == 1:
        return len(source)
    if not 1 <= line <= len(lines) or column < 1:
        raise ValueError('Edit position outside source')
    current = lines[line - 1]
    raw = current.encode('utf-8')
    if column - 1 > len(raw):
        raise ValueError('Edit column outside line')
    prefix = raw[:column - 1].decode('utf-8')
    return sum(map(len, lines[:line - 1])) + len(prefix)


def apply_fixit(source, edit: FixIt):
    start = byte_offset(source, edit.start_line, edit.start_column)
    end = byte_offset(source, edit.end_line, edit.end_column)
    if end < start:
        raise ValueError('Reversed edit range')
    return source[:start] + edit.replacement + source[end:]


def suggestions(source, report):
    result = []
    for edit in report.fixits:
        if edit.file != report.filename:
            continue
        try:
            modified = apply_fixit(source, edit)
        except (ValueError, UnicodeError):
            continue
        result.append(Suggestion(f'Compiler edit · line {edit.start_line}: {edit.replacement!r}', modified, edit.start_line))
    # Mask comments and strings before looking for a small delimiter insertion.
    masked = list(source)
    for match in TOKENS.finditer(source):
        if match.lastgroup in ('comment', 'string', 'directive'):
            for i in range(match.start(), match.end()):
                if masked[i] != '\n':
                    masked[i] = ' '
    masked = ''.join(masked)
    for diagnostic in report.diagnostics:
        if diagnostic.file != report.filename or diagnostic.rule != 'missing-delimiter':
            continue
        message = diagnostic.message.replace('‘', "'").replace('’', "'")
        if "expected ')'" not in message:
            continue
        try:
            offset = byte_offset(source, diagnostic.line, diagnostic.column)
        except (ValueError, UnicodeError):
            continue
        if offset >= len(source) or masked[offset] not in '{;':
            continue
        depth = 0
        for char in masked[:offset]:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
        if depth <= 0:
            continue
        insertion = offset
        while insertion > 0 and source[insertion - 1] in ' \t':
            insertion -= 1
        result.append(Suggestion(f'Rule suggestion · close condition/expression on line {diagnostic.line}',
                                 source[:insertion] + ')' + source[insertion:], diagnostic.line))
    unique = []
    for item in result:
        if item.source != source and item.source not in [x.source for x in unique]:
            unique.append(item)
    return unique

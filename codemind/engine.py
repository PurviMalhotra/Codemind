"""Compiler adapter, diagnostic parser, and beginner explanation rules.

The compiler decides whether a program is valid. Rules explain selected messages;
they never change source code or claim that a suggested edit has been verified.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


class AnalysisError(Exception):
    """An input or compiler infrastructure failure, rather than a C error."""


@dataclass
class Diagnostic:
    file: str
    line: int
    column: int
    severity: str
    message: str
    category: str
    rule: str
    explanation: str
    suggestion: str
    source: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class FixIt:
    file: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    replacement: str


@dataclass
class Report:
    filename: str
    compiler: str
    standard: str
    returncode: int
    diagnostics: list[Diagnostic]
    raw_output: str
    fixits: list[FixIt] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(d.severity in ("error", "fatal error") for d in self.diagnostics)

    @property
    def warnings(self) -> int:
        return sum(d.severity == "warning" for d in self.diagnostics)

    @property
    def success(self) -> bool:
        return self.returncode == 0 and self.errors == 0

    def to_dict(self) -> dict:
        return {**asdict(self), "success": self.success,
                "errors": self.errors, "warnings": self.warnings}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


def explain(message: str) -> tuple[str, str, str, str]:
    """Return category, stable rule id, explanation, and a possible correction."""
    m = message.lower().replace("‘", "'").replace("’", "'")
    if ("'main' must return 'int'" in m
            or "return type of 'main' is not 'int'" in m
            or "return type of 'main' is not int" in m):
        return ("Semantic", "main-return-type",
                "The main function is the program's entry point. In a standard hosted C program it returns int, an exit status reported to the operating system. Declaring it void gives it the wrong return type.",
                "Change void main(void) to int main(void). Keep return 0; to indicate successful completion.")
    if "file not found" in m or "no such file or directory" in m:
        return ("Preprocessor", "missing-header", "The preprocessor cannot find an included header file.",
                "Check the header spelling. Use a standard header such as <stdio.h>, or supply the directory containing your own header.")
    if "unterminated" in m or "missing terminating" in m:
        comment = "comment" in m
        return ("Lexical", "unterminated-comment" if comment else "unterminated-literal",
                "A comment has no closing marker." if comment else "A string or character literal has no matching closing quote.",
                "Close the comment with */." if comment else "Close the literal with the same quote that opened it. Use \\n for a newline inside a string.")
    if any(s in m for s in ("stray", "invalid suffix", "invalid digit", "invalid token", "unexpected character", "null character")):
        return ("Lexical", "invalid-token", "The compiler cannot read this character or number as a valid C token.",
                "Remove the unexpected character or correct the number. C uses straight quotes and valid numeric suffixes.")
    if re.search(r"expected\s+';'", m):
        return ("Syntax", "missing-semicolon", "A declaration or statement is missing its ending semicolon. The compiler may point to the next line where it noticed the problem.",
                "Check this line and the preceding statement, then add ; at the end of the incomplete statement.")
    if re.search(r"expected\s+'[)}\]]'", m) or "expected declaration or statement at end of input" in m:
        match = re.search(r"expected\s+'([)}\]])'", m)
        closing = match.group(1) if match else "}"
        return ("Syntax", "missing-delimiter", f"An opening bracket or parenthesis has no matching {closing} at the expected position.",
                f"Check the matching opening delimiter and insert {closing} before the next block or at the end of the incomplete construct.")
    if "undeclared" in m and "function" not in m:
        return ("Semantic", "undeclared-name", "This name is used where the compiler cannot find a declaration in the current scope.",
                "Check the spelling and declare the variable before using it. If it belongs to another block, move or pass the value into this scope.")
    if "unknown type name" in m:
        return ("Semantic", "unknown-type", "The compiler does not recognize this type name.",
                "Check the spelling of the type, include its header, or define the typedef before using it.")
    if "redefinition" in m or "redeclaration" in m:
        return ("Semantic", "duplicate-declaration", "This name has a conflicting or repeated definition in the same scope.",
                "Inspect the previous declaration shown in the compiler notes. Remove the duplicate definition or use a different name.")
    if any(s in m for s in ("implicit declaration of function", "implicit function declaration", "undeclared function", "undeclared library function")):
        return ("Semantic", "missing-function-declaration", "The compiler sees a function call before a declaration that describes the function.",
                "Include the correct header (for example <stdio.h> for printf), correct the function spelling, or add a matching prototype before the call.")
    if "division by zero" in m or "remainder by zero" in m:
        return ("Semantic", "zero-divisor", "This expression divides by zero or takes a remainder with zero, which is invalid for integer arithmetic.",
                "Use a nonzero divisor and check computed divisors before performing / or %.")
    if "uninitialized" in m:
        return ("Semantic", "uninitialized-value", "A local variable may be read before your program gives it a value.",
                "Initialize the variable at its declaration or assign it on every path before reading it.")
    if "unused variable" in m or "unused parameter" in m:
        return ("Semantic", "unused-name", "A declared variable or parameter is never used.",
                "Use the value if it is needed, or remove the unused declaration. This is usually a warning, not a compilation failure.")
    if "format specifies" in m or ("format" in m and any(s in m for s in ("expects", "argument", "conversion"))):
        return ("Semantic", "format-mismatch", "A printf or scanf format does not match the supplied arguments.",
                "Match each format specifier to its argument type and count. For scanf, pass an address such as &age for an int with %d.")
    if any(s in m for s in ("incompatible", "conflicting types", "invalid operands", "makes pointer from integer", "makes integer from pointer")):
        return ("Semantic", "type-mismatch", "The types used here do not agree with the operation, assignment, or declaration.",
                "Compare the types in the original message and related notes. Correct the declaration or pass a value of the required type.")
    if "too few arguments" in m or "too many arguments" in m:
        return ("Semantic", "argument-count", "The function call supplies a different number of arguments than its declaration allows.",
                "Check the function declaration and add or remove arguments so the call matches it.")
    if "expected expression" in m:
        return ("Syntax", "missing-expression", "The compiler needs a value or expression at this position.",
                "Check for a missing operand after an operator, an empty condition, or an extra operator before ; or ).")
    if "expected" in m or "extraneous" in m:
        return ("Syntax", "syntax-structure", "The sequence of tokens does not match C grammar at this position. An earlier mistake can also trigger this message.",
                "Use the original message to identify the expected token. Check nearby punctuation, declarations, and braces, starting with the first error.")
    return ("Unclassified", "compiler-message", "CodeMind has no specific explanation rule for this compiler message yet.",
            "Read the original compiler message and related notes below. Review the indicated source and fix earlier errors before checking again.")


_LOCATION = re.compile(r"^(.*?):(\d+)(?::(\d+))?:\s*(fatal error|error|warning|note):\s*(.*)$")
_GLOBAL = re.compile(r"^(.*?):\s*(fatal error|error|warning|note):\s*(.*)$")


def parse_diagnostics(output: str, source: str, compiler_path: str, filename: str) -> list[Diagnostic]:
    lines = source.splitlines()
    result: list[Diagnostic] = []
    seen: set[tuple] = set()
    for text in output.splitlines():
        match = _LOCATION.match(text)
        if match:
            path, line, column, severity, message = match.groups()
            line, column = int(line), int(column or 0)
        else:
            match = _GLOBAL.match(text)
            if not match:
                continue
            path, severity, message = match.groups()
            line, column = 0, 0
        if severity == "note":
            if result:
                location = filename if path == compiler_path else path
                result[-1].notes.append(f"{location}:{line}:{column}: {message}")
            continue
        own_source = path == compiler_path
        display = filename if own_source else path
        key = display, line, column, severity, message
        if key in seen:
            continue
        seen.add(key)
        category, rule, explanation, suggestion = explain(message)
        result.append(Diagnostic(display, line, column, severity, message, category,
                                 rule, explanation, suggestion,
                                 lines[line - 1] if own_source and 0 < line <= len(lines) else ""))
    return result


def find_compiler(requested: str | None = None) -> str:
    choices = [requested] if requested else ["clang", "gcc", "cc"]
    for choice in choices:
        path = shutil.which(choice)
        if path:
            return path
    raise AnalysisError("No C compiler found. Install GCC or Clang and put it on PATH, or use --compiler /path/to/compiler.")


def parse_fixits(output: str, compiler_path: str, filename: str) -> list[FixIt]:
    pattern = re.compile(r'^fix-it:("(?:\\.|[^"\\])*"):\{(\d+):(\d+)-(\d+):(\d+)\}:("(?:\\.|[^"\\])*")$')
    edits = []
    for line in output.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        path, sl, sc, el, ec, replacement = match.groups()
        try:
            if json.loads(path) == compiler_path:
                edit = FixIt(filename, int(sl), int(sc), int(el), int(ec), json.loads(replacement))
                if edit not in edits:
                    edits.append(edit)
        except (ValueError, TypeError):
            continue
    return edits


def analyze(source: str, filename: str = "program.c", compiler: str | None = None,
            standard: str = "c11", include_dir: str | None = None) -> Report:
    if standard not in ("c99", "c11", "c17"):
        raise AnalysisError("Supported C standards: c99, c11, c17.")
    if len(source.encode("utf-8")) > 1_000_000:
        raise AnalysisError("Please use a source file smaller than 1 MB for this classroom tool.")
    if "\x00" in source:
        raise AnalysisError("The input contains a NUL byte. Open a plain UTF-8 C source file.")
    executable = find_compiler(compiler)
    with tempfile.TemporaryDirectory(prefix="codemind-") as directory:
        path = Path(directory) / "input.c"
        path.write_text(source, encoding="utf-8")
        command = [executable, f"-std={standard}", "-Wall", "-Wextra", "-Wpedantic",
                   "-fsyntax-only", "-fno-diagnostics-color", "-fdiagnostics-parseable-fixits", str(path)]
        if include_dir:
            command.extend(["-iquote", str(Path(include_dir).resolve())])
        try:
            process = subprocess.run(command, capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=15,
                                     env={**os.environ, "LC_ALL": "C", "LANG": "C"})
        except subprocess.TimeoutExpired as error:
            raise AnalysisError("The compiler exceeded the 15 second analysis limit.") from error
        except OSError as error:
            raise AnalysisError(f"Could not launch the compiler: {error}") from error
        output = process.stdout + process.stderr
        diagnostics = parse_diagnostics(output, source, str(path), filename)
        # Preserve failures that do not follow GCC/Clang's diagnostic format.
        if process.returncode and not any(d.severity in ("error", "fatal error") for d in diagnostics):
            diagnostics.append(Diagnostic(filename, 0, 0, "error", "Compiler analysis failed.",
                                          "Infrastructure", "compiler-failure",
                                          "The compiler failed without a recognized error diagnostic.",
                                          "Check the original output and the selected compiler installation."))
        return Report(filename, executable, standard, process.returncode, diagnostics,
                      output.replace(str(path), filename), parse_fixits(output, str(path), filename))


def format_text(report: Report) -> str:
    status = "No compilation errors" if report.success else "Compilation errors found"
    parts = [f"CODEMIND — {status}",
             f"{report.filename} | {report.standard} | {report.errors} error(s), {report.warnings} warning(s)"]
    if report.success:
        parts.append("Syntax and compiler checks passed. This does not check linking or runtime behavior.")
    for i, item in enumerate(report.diagnostics, 1):
        parts.extend(["", f"{i}. {item.severity.upper()} · {item.category} · {item.file}:{item.line}:{item.column}",
                      f"Compiler: {item.message}"])
        if item.source:
            expanded = item.source.expandtabs(4)
            prefix = len(item.source[:max(0, item.column - 1)].expandtabs(4))
            parts.extend([f"  {item.line} | {expanded}", " " * (len(str(item.line)) + 5 + prefix) + "^"])
        parts.extend([f"Why: {item.explanation}", f"Try: {item.suggestion}"])
        parts.extend(f"Note: {note}" for note in item.notes)
    if report.errors > 1:
        parts.extend(["", "Fix the first error and analyze again. Later messages may be consequences of the same mistake."])
    return "\n".join(parts)


def learning_question(rule: str) -> str:
    questions = {
        "main-return-type": "What does the integer returned by main tell the operating system?",
        "missing-semicolon": "Why might the compiler point to the line AFTER a missing semicolon?",
        "missing-delimiter": "Which opening delimiter should this closing delimiter match?",
        "undeclared-name": "Is the name misspelled, used too early, or outside its declared scope?",
        "missing-function-declaration": "Which header or prototype tells the compiler this function's parameter types?",
        "zero-divisor": "Could the divisor become zero with a different input even after this example is fixed?",
        "uninitialized-value": "Does every path through the program assign a value before this variable is read?",
        "format-mismatch": "What C type does each format specifier expect?",
        "type-mismatch": "What are the types on each side of this operation?",
        "duplicate-declaration": "How does a declaration differ from a definition?",
        "unterminated-literal": "How would you write a newline inside a C string without splitting the literal?",
        "unterminated-comment": "Which two characters close a C block comment?",
    }
    return questions.get(rule, "Which compiler phase found this issue, and why does your proposed change address it?")


def compare_reports(before: Report, after: Report) -> str:
    """Compare counts, without claiming that matching diagnostics are the same bug."""
    from collections import Counter
    a = Counter((d.rule, d.severity) for d in before.diagnostics)
    b = Counter((d.rule, d.severity) for d in after.diagnostics)
    text = [f"Previous check: {before.errors} error(s), {before.warnings} warning(s).",
            f"Current check: {after.errors} error(s), {after.warnings} warning(s)."]
    for rule, severity in sorted(a.keys() | b.keys()):
        if a[rule, severity] != b[rule, severity]:
            text.append(f"{rule} ({severity}): {a[rule, severity]} → {b[rule, severity]}")
    text.append("Counts compare reported diagnostic types. A disappearing message can be a cascade effect; it does not prove a particular bug is repaired.")
    return "\n".join(text)

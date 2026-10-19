# CodeMind

**A C compiler error explainer for beginner programmers, with a Flex/Yacc learning lab.**

CodeMind reads real compiler diagnostics and connects each supported message to its source line, a plain-language explanation, and a possible correction. Its rules are local and inspectable. No API key or AI service is required.

## Start on this Mac

Double-click `launch.command`, or run these commands in Terminal:

```sh
cd "/Users/purvimalhotra/Documents/ChatGPT/Compiler design/codemind"
python3 -m codemind --gui
```

The launcher selects a Python installation with Tk 8.6 or newer. Apple’s `/usr/bin/python3` uses an older Tk version that can display a blank window on this Mac, so use `launch.command` or Python 3.12 from python.org for the desktop editor.

## Other computers

Requirements: Python 3.9 or newer and GCC or Clang on PATH. The desktop interface also requires Tkinter. No pip packages are needed.

On Debian/Ubuntu:

```sh
sudo apt install python3 python3-tk gcc make flex byacc
python3 -m codemind --gui
```

On Windows, install Python with Tcl/Tk and GCC or Clang on PATH, then use `py -m codemind --gui` from the project folder. On macOS, a Python installation with Tk support and Apple Command Line Tools is sufficient. The project has been tested on the provided Mac; other platform launch instructions are provided for portability.

## Terminal mode

Run from this folder:

```sh
python3 -m codemind examples/slide_example.c
python3 -m codemind examples/slide_fixed.c
python3 -m codemind examples/undeclared_name.c --json --output report.json
python3 -m codemind examples/valid.c --std c17 --compiler clang
```

Exit codes: `0` means no compiler errors (warnings may remain), `1` means compilation errors, and `2` means an input, compiler setup, or report-writing failure. CodeMind uses `-fsyntax-only`: it checks source without linking, producing an executable, or running the C program. Local quoted includes are searched relative to the opened file. Multi-file build systems and custom compiler flags are outside this version's scope.

## Features

- Desktop source editor with Open/Save, C standard selection, and a built-in version of the slide example.
- Lexical, syntax, and semantic explanation rules, plus missing-header feedback from preprocessing.
- Exact compiler message, source context, line and column, and related compiler notes.
- First-error guidance to help beginners work through cascading messages. All diagnostics remain available.
- **Fix & check:** compare diagnostic counts between successive checks of the same document.
- **Check your understanding:** a learning question for each selected error.
- Text and JSON report export. The original compiler output stays available for verification.
- A retained Flex/Yacc lab for ASTs, symbol tables, three-address code, optimization, and Graphviz export.

Suggested corrections are guidance, not automatic edits. Analyze again after making a change. Diagnostic count changes do not establish that a particular bug has been repaired. Compiler checks do not prove runtime correctness.

## Explanation coverage

| Area | Supported examples |
| --- | --- |
| Lexical | Invalid tokens/numeric suffixes, unclosed strings/characters, unclosed comments |
| Syntax | Missing semicolons, missing closing delimiters, missing expressions, general expected-token errors |
| Semantic | Invalid main return type, undeclared names, unknown types, duplicate declarations, missing function declarations, incompatible types, argument counts |
| Warnings | Uninitialized variables, unused names, format mismatches, constant zero divisors |
| Preprocessor | Missing include files |

These are diagnostic pattern families, not a complete implementation of C. Compiler version and flags determine which diagnostics appear and whether they are warnings or errors. Unrecognized messages get an explicit fallback rather than an invented explanation. A missing semicolon may be reported on the following line, so CodeMind explains that possibility without fabricating a location.

## Flex/Yacc learning lab

```sh
make lab
cd mini_compiler
./mini_compiler example.src
```

This preserves the original compiler architecture and its `.src` teaching language. It accepts `int`/`float` declarations and arithmetic assignments; it does **not** accept full C programs, functions, or `if` blocks. Its numeric model is educational and uses real-number division, unlike C integer division. CodeMind's main C checks always use the real C compiler.

The lab writes `ast.dot`, `tac.txt`, and `optimized_tac.txt` in its working directory for valid inputs. Graphviz is optional: `dot -Tpng ast.dot -o ast.png`. Files from a prior successful lab run are not evidence that a later invalid run succeeded; use the exit status.

## Tests and project guide

```sh
make test
make test-lab
```

See `docs/PROJECT_GUIDE.md` for the prototype mapping, architecture, changes to the supplied compiler, viva notes, and a short demonstration script. `examples/` includes both failing programs and corrected examples.

# CodeMind

**A C compiler error explainer for beginner programmers, with a Flex/Yacc learning lab.**

CodeMind reads real compiler diagnostics and connects each supported message to its source line, a plain-language explanation, and a possible correction. Its rules are local and inspectable. No API key or AI service is required.

## Start on this Mac

Double-click `launch.command`, or run these commands in Terminal:

```sh
cd "/Users/purvimalhotra/Developer/Compiler design/codemind"
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

- Desktop source editor with syntax colouring, scroll-synchronised line numbers, Open/Save, C standard selection, and a built-in version of the slide example.
- **Compare correction:** side-by-side source views with red/green change highlights, compiler-provided edits where available, a missing-parenthesis suggestion, manual edits, and independent compiler checks before applying a preview.
- **Compiler lab:** an interactive Flex/Yacc pipeline with actual token output, a clickable AST diagram with zoom/scroll/Fit tree, a scope-aware symbol table, TAC, a control-flow graph, optimized TAC, and stage failure status. No Graphviz installation is required for the built-in AST viewer.
- Lexical, syntax, and semantic explanation rules, plus missing-header feedback from preprocessing.
- Exact compiler message, source context, line and column, and related compiler notes.
- First-error guidance to help beginners work through cascading messages. All diagnostics remain available.
- **Fix & check:** compare diagnostic counts between successive checks of the same document.
- **Check your understanding:** a learning question for each selected error.
- Text and JSON report export. The original compiler output stays available for verification.
- A retained Flex/Yacc lab for ASTs, symbol tables, three-address code, optimization, and Graphviz export.

Suggested corrections are guidance. A preview only changes the editor after you click Apply to editor; it does not save your source file. The comparison also permits manual edits when no exact compiler edit is available. Analyze again after making a change. Diagnostic count changes do not establish that a particular bug has been repaired. Compiler checks do not prove runtime correctness.

## Explanation coverage

| Area | Supported examples |
| --- | --- |
| Lexical | Invalid tokens/numeric suffixes, unclosed strings/characters, unclosed comments |
| Syntax | Missing semicolons, missing closing delimiters, missing expressions, general expected-token errors |
| Semantic | Invalid main return type, undeclared names, unknown types, duplicate declarations, missing function declarations, incompatible types, argument counts |
| Warnings | Uninitialized variables, unused names, format mismatches, constant zero divisors |
| Preprocessor | Missing include files |

These are diagnostic pattern families, not a complete implementation of C. Compiler version and flags determine which diagnostics appear and whether they are warnings or errors. Unrecognized messages get an explicit fallback rather than an invented explanation. A missing semicolon may be reported on the following line, so CodeMind explains that possibility without fabricating a location.

## Try the visual features

1. Launch with `./launch.command`. Code colouring and line numbers appear automatically.
2. Load the slide demo and click **Analyze C**. Select the missing-parenthesis diagnostic, then **Compare correction**.
3. The left view is the original. The editable right view previews a possible change. Changed lines have red/green backgrounds.
4. Click **Check proposed code**. The check uses a temporary copy and shows the error/warning counts. Click **Apply to editor** to accept the edit, then save and analyze again.
5. Click **Compiler lab**. Its source editor starts with a separate `.src` example. Click **Build & inspect**, then explore **Tokens**, **Parse / AST**, **Scopes**, **TAC**, **Flow graph**, and **Optimize**. Use **Loop + if/else example** to try the new control-flow syntax.
6. Click AST nodes for explanations. Zoom, scroll, or use **Fit tree** to explore the graph. Invalid programs show the failed stage and skip later stages.

The lab builds the existing Flex/Yacc C sources in a temporary directory. It needs make, Flex, Yacc/Bison, and a C compiler. Small examples are recommended; the interactive viewer limits ASTs to 300 nodes. Lab source is limited to 50 KB. These limits keep the visual teaching view responsive.

## Flex/Yacc learning lab

```sh
make lab
cd mini_compiler
./mini_compiler example.src
```

The lab accepts a C-like `.src` subset: `int`/`float` declarations with optional initializers, arithmetic assignments, comparisons, `&&`/`||`/`!`, nested `if/else`, `while`, and scoped `{ ... }` blocks. An `else` belongs to the nearest unmatched `if`. Logical operators use short-circuit branches in generated TAC. Local declarations may shadow outer names; names disappear from visibility at the closing brace, and same-scope duplicates are errors.

The **Scopes** table shows name, type, scope ID, nesting depth, unique storage name, and declaration line. Scope 0 is global. Names such as `x@S1` identify block-local variables in TAC; they are generated names, not source syntax. **Flow graph** groups actual TAC into basic blocks, shows true/false branch edges and purple loop-back edges, supports zoom/fit/click, and exports Graphviz `.dot` files. AST branch edges are labelled condition/then/else/body and clicking a node highlights its source line.

The optimizer propagates constants only within a basic block and clears facts at every label or branch. It does not propagate a loop's starting value into its later iterations or across a branch join.

This is still an educational subset: full C functions, `main`, headers, arrays, pointers, `for`, `break`, `continue`, `++`, and compound assignment are not implemented in the lab. Its generated TAC uses a simplified double-based numeric model, including real-number division; it does not emulate C integer widths or conversions. Static zero-divisor checks can reject expressions even in unreachable code. Use CodeMind's main editor for real C checks.

The lab writes `ast.dot`, `symbols.tsv`, `tac.txt`, and `optimized_tac.txt` in its working directory for valid inputs. Graphviz is optional: `dot -Tpng ast.dot -o ast.png`. Files from a prior successful lab run are not evidence that a later invalid run succeeded; use the exit status.

## Tests and project guide

```sh
make test
make test-lab
```

See `docs/PROJECT_GUIDE.md` for the prototype mapping, architecture, changes to the supplied compiler, viva notes, and a short demonstration script. `examples/` includes both failing programs and corrected examples.

## Try control flow and scope

From the desktop, open **Compiler lab → Loop + if/else example → Build & inspect**. Select the While or If AST node, then explore **Scopes** and **Flow graph**.

Other lab examples are in `mini_compiler/examples/`: `control_flow.src`, `nested_loops.src`, and `block_scope.src`. For a scope error, open `mini_compiler/tests/invalid_scope.src`. Source variables declared inside a block cannot be used after that block.

# Project guide

## Relationship to the supplied prototype

The supplied Group 14 presentation describes CodeMind as an educational diagnostic explainer for C. It proposes compiling input, classifying selected diagnostics, and showing the source, reason, and possible correction. The supplied ZIP implements a different, smaller teaching language using Flex and Yacc.

This implementation puts the diagnostic explainer first and preserves the original compiler as a separate learning lab. The two components have different inputs and purposes. The Flex/Yacc grammar does not analyze full C and does not generate the main application's diagnostics.

| Prototype requirement | Implementation |
| --- | --- |
| C programs as the initial scope | GCC/Clang checks with C99, C11, or C17 |
| Compiler output as the error source | `engine.analyze()` invokes a compiler and captures diagnostics |
| Pattern classification | Ordered explanation rules with stable identifiers |
| Lexical, syntax, semantic categories | Categorized feedback plus preprocessing and honest fallback |
| Source context | File, line, column, source text, and related notes |
| Beginner explanation and correction | Rule-specific reason and suggested action |
| Missing parenthesis demonstration | `examples/slide_example.c` and `examples/slide_fixed.c` |
| Interface and tests | Tkinter editor, terminal interface, integration tests |

## Visual features

The C editor uses display-only token colouring for keywords, strings, comments, numbers, and preprocessor directives, with line numbers that follow vertical scrolling. GCC/Clang remains responsible for determining validity.

The correction comparison shows original and proposed source side by side. It reads machine-readable compiler fix-it hints for the main source file and adds a narrowly scoped missing-parenthesis suggestion. Where no exact edit is available, the student can edit the proposed source manually. The proposed version is checked independently before Apply is enabled. The editor rejects applying a preview when the main document has changed since the preview opened. Applying a preview changes the editor buffer and preserves undo; saving is a separate action.

The visual lab builds the actual Flex/Yacc sources in a temporary directory for every inspection. The lexer’s `--tokens` mode reports real token names and lexemes. Yacc and the existing semantic/IR stages produce the AST, symbol table, TAC, and optimized TAC. The GUI renders the DOT node/edge data directly on a Tk canvas, so Graphviz is optional. Failed stages are labelled and subsequent stages are skipped. The lab is explicitly a C-like subset with arithmetic, comparisons, if/else, while, and block scope, not full C.

## Additional learning features

**Fix & check** compares counts for each diagnostic rule and severity between successive checks. It helps students see the effect of an edit without claiming that a reduced count proves correctness. Opening a different file or loading the demo starts a new comparison session.

**Check your understanding** gives a question matched to the selected diagnostic. It encourages a student to identify the cause before copying a correction.

**Compiler learning lab** keeps the AST and intermediate-code features from the ZIP. The project can demonstrate both how a tiny compiler works and how real compiler diagnostics can support beginners.

**Transparent feedback** exposes the original message, compiler notes, explanation rule, and JSON report. The implementation is deterministic and can be explained during assessment without claiming machine learning or automatic program repair.

## Architecture

```text
Desktop editor / terminal
          |
          v
Temporary C source + GCC/Clang syntax checks
          |
          v
Diagnostic parser (file, position, severity, message, notes)
          |
          v
Ordered explanation rules
          |
          v
Source context + reason + possible correction + learning question
          |
          v
Edit and check again / compare counts / export report
```

Separate lab:

```text
.src input -> Flex tokens -> Yacc grammar -> AST
           -> symbol table and semantic checks -> TAC -> optimized TAC
```

`codemind/engine.py` contains the compiler adapter, parser, and explanation rules. `codemind/gui.py` contains the interface and session comparison. `codemind/__main__.py` provides terminal commands. `mini_compiler/` contains the adapted C project. Analysis runs in a worker thread so the editor stays responsive. If the source changes during analysis, the editor rejects the stale result.

## Changes to the supplied mini compiler

- Fixed the lexer header order so `ASTNode` is defined before the Yacc union is included. The supplied project failed to compile without this fix.
- Added a macOS Makefile route to the installed Command Line Tools Flex/Bison binaries. The grammar remains traditional Yacc compatible; no Bison-only grammar features were added.
- Sequenced Yacc header generation for parallel builds.
- Retitled the executable output as the CodeMind learning lab.
- Checked declarations in source order, so a later declaration no longer validates an earlier use.
- Rejected floating-point modulo operands and removed unsafe integer casts from modulo evaluation.
- Used `$t` temporary names so compiler-generated temporaries cannot clash with identifiers accepted by the lexer.

Original arithmetic parsing, text AST, Graphviz export, symbol table, semantic checks, TAC generation, and the optimizer are retained. AST identifier, declaration, control, and literal nodes now retain token-based source lines; syntax-error recovery still uses approximate lookahead lines. The mini language has a simplified numeric model. It is suitable for teaching compiler phases, not for compiling C.

## Five-minute demonstration

1. Launch the editor and select **Load slide demo**. Point out the unclosed condition in `if (marks >= 50 {`.
2. Click **Analyze C**. Select the first diagnostic. Show the original compiler wording, source highlight, explanation, and possible correction.
3. Add `)` after `50`. Analyze again. Open **Fix & check** to discuss the changed diagnostic counts and why one mistake may cause multiple messages.
4. Open `examples/undeclared_name.c`, then `examples/format_warning.c`. Explain semantic feedback and the difference between an error and a warning.
5. Export a report. Show that the underlying compiler output remains visible.
6. Run the Flex/Yacc lab's `example.src` and discuss the AST, symbol table, and TAC. Explain why the lab accepts a small teaching language while the main tool checks C.

## Viva notes

- **Where is compiler design involved?** The lab demonstrates lexical analysis, grammar parsing, AST construction, semantic checks, and intermediate-code optimization. The main tool demonstrates diagnostic processing and feedback around a real compiler.
- **Is this an AI model?** No. It uses deterministic explanation rules. The prototype's word “intelligent” describes contextual feedback, not a trained model.
- **Why use GCC/Clang?** Implementing full C in the original arithmetic grammar would exceed the small project's scope. A real compiler supplies authoritative syntax and type diagnostics.
- **Why keep original messages?** They make the explanation traceable and cover messages that the rule set does not yet support.
- **Does it automatically repair code?** It can preview selected compiler edits or a rule suggestion, but the student checks and explicitly applies the proposal. It does not claim to repair arbitrary programs.
- **Does zero errors mean a correct program?** No. Syntax and compiler checks do not test linking, runtime inputs, memory safety, or intended behavior.
- **Is the feature set unique research?** No novelty claim is made. The project's contribution is its combination of explainable feedback, learning prompts, a fix-check loop, and an inspectable compiler lab for this class.

## Boundaries and next steps

The tool checks one translation unit with standard warnings. It does not execute programs, resolve build systems, diagnose arbitrary compiler families, or repair arbitrary source automatically. Some compile-time warnings depend on optimization and compiler version. Diagnostic explanations are heuristic and can be influenced by preceding errors. Header diagnostics retain their own locations rather than showing an unrelated main-source line.

Possible later extensions include instructor-authored rules, configurable include paths, controlled runtime test cases, and a carefully implemented full C subset in Flex/Yacc. These are proposals, not features included in this submission.

## Control-flow and scope extension

The traditional Yacc grammar now supports `if/else`, `while`, and scoped blocks, along with relational/equality and logical operators. It resolves dangling `else` by attaching it to the nearest unmatched `if`, without unresolved parser conflicts. Declarations are block items, so a declaration directly after `if` or `while` requires braces. Initializers and empty statements are supported.

The AST has dedicated If, While, and Block nodes. If stores condition, then, and optional else children. While stores condition and body. Semantic traversal pushes a scope on block entry, resolves identifiers from the innermost scope outward, and restores the outer scope on block exit. All declarations remain in the displayed history table even after their visibility ends. Each declaration has a distinct TAC storage identity; inner `x` might become `x@S1`.

TAC uses labels, conditional branches, unconditional jumps, and short-circuit control flow for `&&`, `||`, and `!`. The CFG is derived from this actual TAC, identifying leaders, basic blocks, fallthrough paths, conditional outcomes, and loop backedges. It is a view of execution paths, not a runtime trace or a termination proof. `codemind/cfg.py` also exports the graph as DOT.

The previous straight-line optimizer was replaced with conservative propagation inside basic blocks only. Every label and branch discards constant facts. This preserves changing loop variables and branch joins, at the cost of missing some possible global optimizations. A bounded TAC evaluator exists only in the test suite to compare original and optimized execution results. The application itself does not execute user programs.

Demo: load **Loop + if/else example**, inspect the While and If AST nodes, select **Scopes** for `bonus@S3`, and select **Flow graph** for true/false and loop-back edges. Open `mini_compiler/examples/block_scope.src` to show two different `x` declarations. Open `mini_compiler/tests/invalid_scope.src` to show a variable used after its scope ends.

Not yet supported by the lab: functions/main, headers, for/do loops, break/continue, arrays, pointers, ++/--, compound assignments, or full C numeric semantics.

# Flex + traditional Yacc Mini Compiler

This is the retained **CodeMind learning lab**. For the C error explainer and desktop editor, see `../README.md`. This lab accepts the smaller `.src` language below, not full C. Division uses a simplified real-number model. Generated temporaries use `$t` names, and declarations must precede their use.

This version uses **Flex and traditional Yacc** (not Bison-specific grammar features). It constructs an AST, performs basic semantic checks, generates three-address code, optimizes TAC, and exports a Graphviz AST diagram.

## Requirements

On Ubuntu/Debian/WSL:

```bash
sudo apt update
sudo apt install flex byacc gcc make graphviz
```

`byacc` provides a traditional Yacc-compatible executable named `yacc`. Some systems also provide `yacc` through another compatible implementation.

## Build and run

```bash
make
./mini_compiler example.src
```

If your system's `yacc` command is not installed, install `byacc`. This Makefile invokes `yacc -d parser.y`, producing `y.tab.c` and `y.tab.h`.

To visualize the AST:

```bash
dot -Tpng ast.dot -o ast.png
```

## Features

- Flex lexer for identifiers, integer/float literals, arithmetic operators, parentheses, assignments, semicolons, and comments.
- Yacc grammar for arithmetic precedence, unary signs, declarations, and assignments.
- AST construction and text output.
- Graphviz `.dot` AST export.
- Symbol table and basic semantic validation.
- Three-address code generation.
- TAC optimization: constant folding, basic constant propagation, and selected algebraic simplifications.
- Error examples in `tests/`.

## Example language

```c
int a;
int b;
float result;

a = 10;
b = 5 + 2 * 3;
result = (a + b) / 2.0;
```

Every assignment must end in a semicolon. Variables must be declared.

## Test invalid input

```bash
./mini_compiler tests/invalid_syntax.src
./mini_compiler tests/invalid_semantic.src
```

## Important implementation note

Traditional Yacc does not standardize Bison's `%locations` and `%define parse.error verbose` extensions. This version therefore uses `yylineno` for approximate line-based parser diagnostics instead of Bison location objects. The parser's grammar uses classic Yacc syntax.

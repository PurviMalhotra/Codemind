# Validation

Verified on the provided macOS machine with Apple Clang, Python 3.13, and Apple's Python 3.9 with Tk 8.5.

- 24 automated compiler-adapter, explanation, parser, command-line, and failure-handling tests pass under both installed Python versions.
- The slide's missing-parenthesis program fails as expected and its corrected version passes.
- Tests cover quoted local headers, report locations, compiler notes, warning-only success, duplicate diagnostic removal, unknown-message fallback, missing compilers, and compiler timeout handling.
- A test C program containing a file write is checked without executing that write.
- 7 retained-lab checks pass: the original example, valid input, syntax errors, semantic errors, declaration order, floating-point modulo rejection, and generated temporary names.
- The desktop editor opens and completes a real compiler analysis in a Tk event loop.
- The desktop edit-and-recheck workflow passes: the slide example first produces errors, adding the missing parenthesis produces zero errors, and the comparison tab shows the updated counts.

The actual compiler integration tests use Apple Clang. GCC-style diagnostic parsing also has a fixture test. A separate GCC installation, Windows, and Linux have not been exercised on this machine.

Commands:

```sh
make test
make test-lab
/usr/bin/python3 -m unittest discover -s tests -q
```

Flex-generated C emits warnings with the old Flex version bundled by Apple, but the lab builds and all its checks pass. No executable, generated parser sources, or debug artifacts are required in the source ZIP; `make lab` recreates the lab executable locally.

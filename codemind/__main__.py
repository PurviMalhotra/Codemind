from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .engine import AnalysisError, analyze, format_text


def main() -> int:
    parser = argparse.ArgumentParser(description="CodeMind: beginner-friendly C compiler feedback")
    parser.add_argument("file", nargs="?", type=Path, help="UTF-8 C source file")
    parser.add_argument("--gui", action="store_true", help="open the desktop editor")
    parser.add_argument("--compiler", help="GCC/Clang executable name or path")
    parser.add_argument("--std", choices=("c99", "c11", "c17"), default="c11")
    parser.add_argument("--json", action="store_true", help="print a structured report")
    parser.add_argument("--output", type=Path, help="also save the report to a file")
    args = parser.parse_args()
    if args.gui:
        try:
            from .gui import launch
            launch(args.file, args.compiler, args.std)
            return 0
        except ImportError:
            print("The desktop editor needs Tkinter. Use the command-line interface or install Python with Tk support.", file=sys.stderr)
            return 2
    if args.file is None:
        parser.error("provide a C file or use --gui")
    try:
        source = args.file.read_text(encoding="utf-8")
        report = analyze(source, str(args.file), args.compiler, args.std, str(args.file.resolve().parent))
        rendered = report.to_json() if args.json else format_text(report)
        if args.output:
            if args.output.resolve() == args.file.resolve():
                raise AnalysisError("The report output must not overwrite the input source file.")
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0 if report.success else 1
    except (OSError, UnicodeError, AnalysisError) as error:
        print(f"CodeMind: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

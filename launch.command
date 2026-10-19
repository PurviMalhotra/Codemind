#!/bin/sh
cd "$(dirname "$0")" || exit 1
# Prefer a modern Tk runtime. Apple's system Tk 8.5 can show blank windows.
for codemind_python in python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if "$codemind_python" -c 'import tkinter; raise SystemExit(0 if tkinter.TkVersion >= 8.6 else 1)' >/dev/null 2>&1; then
        exec "$codemind_python" -m codemind --gui
    fi
done
printf '%s\n' 'CodeMind needs Python with Tk 8.6 or newer. Install the macOS Python package from python.org and try again.'
printf '%s' 'Press Enter to close: '
read codemind_reply
exit 2

"""Optional desktop integration check: python3 tests/gui_smoke.py [--capture]."""
from pathlib import Path
import subprocess
import sys
import time
import tkinter as tk
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codemind.gui import Editor
from codemind.lab_gui import LabWindow
from codemind.preview import CorrectionPreview

root = tk.Tk()
app = Editor(root)
root.geometry('1280x820+25+35')
errors = []
deadline = time.monotonic() + 60


def fail(kind, value, tb):
    errors.append(str(value))
    traceback.print_exception(kind,value,tb)
    root.destroy()


root.report_callback_exception = fail


def capture(window,name):
    if '--capture' not in sys.argv:
        return
    window.update_idletasks()
    rect = f'{window.winfo_rootx()},{window.winfo_rooty()},{window.winfo_width()},{window.winfo_height()}'
    result = subprocess.run(['/usr/sbin/screencapture','-x','-R',rect,f'/private/tmp/codemind-{name}.png'],capture_output=True,text=True,timeout=8)
    print('Screenshot:',name,result.returncode,result.stderr,flush=True)


def wait_for(condition, then):
    if time.monotonic() > deadline:
        raise AssertionError('Desktop workflow timed out')
    if condition():
        then()
    else:
        root.after(100,lambda:wait_for(condition,then))


def finish():
    assert lab.result is not None
    assert all(x=='passed' for x in lab.result.stages.values())
    assert lab.tokens.get_children()
    assert lab.symbols.get_children()
    assert lab.canvas.find_all()
    lab.show('ast')
    lab.fit_tree()
    assert 0.4 <= lab.scale <= 1.0
    lab.inspect(next(iter(lab.result.nodes)))
    assert 'Node ' in lab.node_info.get()
    lab.window.lift()
    root.after(700,done)


def done():
    capture(lab.window,'lab')
    print('PASS: highlighted editor, line-number gutter, diff preview, compiler check, apply, real pipeline and AST.',flush=True)
    root.destroy()


def preview_checked():
    assert preview.verified is not None
    assert '→ 0 error(s)' in preview.status.get()
    preview.window.lift()
    root.after(700,apply_and_lab)


def apply_and_lab():
    global lab
    capture(preview.window,'preview')
    preview.apply()
    assert 'marks >= 50)' in app.text()
    assert app.dirty
    lab = LabWindow(root)
    lab.window.geometry('1280x840+35+35')
    lab.run()
    wait_for(lambda:not lab.busy,finish)


def analyzed():
    global preview
    assert app.report is not None and app.report.errors > 0
    assert app.code.tag_ranges('keyword')
    assert app.code_view.gutter.find_all()
    root.lift()
    root.focus_force()
    root.after(700,open_preview)


def open_preview():
    global preview
    capture(root,'editor')
    preview = CorrectionPreview(app)
    preview.window.geometry('1180x760+45+45')
    assert preview.after.text.tag_ranges('added')
    preview.check()
    wait_for(lambda:not preview.busy,preview_checked)


root.after(500,app.start)
root.after(700,lambda:wait_for(lambda:not app.busy,analyzed))
root.mainloop()
if errors:
    raise SystemExit(1)

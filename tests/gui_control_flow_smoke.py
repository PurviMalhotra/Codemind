"""Optional desktop check: python3 tests/gui_control_flow_smoke.py [--capture]."""
from pathlib import Path
import subprocess
import sys
import time
import tkinter as tk
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codemind.lab import CONTROL_DEMO
from codemind.lab_gui import LabWindow

root = tk.Tk()
root.withdraw()
lab = LabWindow(root)
lab.window.geometry('1280x840+30+35')
lab.demo(CONTROL_DEMO)
errors = []
deadline = time.monotonic()+60


def fail(kind,value,tb):
    errors.append(str(value))
    traceback.print_exception(kind,value,tb)
    root.destroy()


root.report_callback_exception = fail


def wait_for(then):
    if time.monotonic()>deadline:
        raise AssertionError('Control-flow UI timed out')
    if lab.busy:
        root.after(100,lambda:wait_for(then))
    else:
        then()


def capture(name):
    if '--capture' in sys.argv:
        window = lab.window
        rect = f'{window.winfo_rootx()},{window.winfo_rooty()},{window.winfo_width()},{window.winfo_height()}'
        result = subprocess.run(['/usr/sbin/screencapture','-x','-R',rect,f'/private/tmp/codemind-{name}.png'],capture_output=True,text=True,timeout=8)
        print('Screenshot:',name,result.returncode,result.stderr,flush=True)


def compiled():
    assert lab.result and all(x=='passed' for x in lab.result.stages.values())
    assert any(lab.symbols.item(key,'values')[4]=='bonus@S3' for key in lab.symbols.get_children())
    key = next(key for key,label in lab.result.nodes.items() if label=='While')
    lab.inspect(key)
    assert str(lab.source.text.tag_ranges('selectednode')[0])=='4.0'
    lab.show('ast')
    lab.fit_tree()
    lab.window.lift()
    lab.window.focus_force()
    root.after(700,show_flow)


def show_flow():
    capture('loop-ast')
    lab.show('cfg')
    root.after(200,fit_flow)


def fit_flow():
    lab.flow.fit()
    lab.flow.inspect('B2')
    assert 'ifFalse' in lab.flow.info.get()
    assert any(lab.flow.canvas.type(item)=='text' and lab.flow.canvas.itemcget(item,'text')=='loop back'
               for item in lab.flow.canvas.find_all())
    root.after(700,invalid_source)


def invalid_source():
    capture('control-flow')
    lab.source.set('int x=0; {int hidden=1;} x=hidden;',readonly=False)
    lab.run()
    wait_for(invalid_done)


def invalid_done():
    assert lab.result.stages['ast']=='passed'
    assert lab.result.stages['symbols']=='failed'
    assert lab.result.stages['cfg']=='skipped'
    assert lab.flow.graph is None
    assert not lab.flow.canvas.find_all()
    print('PASS: loop AST, source highlight, scope table, CFG with loop backedge, and clearing stale graphs after semantic failure.',flush=True)
    root.destroy()


root.after(300,lab.run)
root.after(500,lambda:wait_for(compiled))
root.mainloop()
if errors:
    raise SystemExit(1)

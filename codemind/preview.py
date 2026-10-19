"""Side-by-side correction preview with independent compiler checks."""
import difflib
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .corrections import suggestions
from .engine import AnalysisError, analyze
from .widgets import CodeView


class CorrectionPreview:
    def __init__(self, editor):
        self.editor = editor
        self.original = editor.text()
        self.path = editor.path
        self.base = editor.report
        self.standard = self.base.standard
        self.results = queue.Queue()
        self.verified = None
        self.busy = False
        self.window = tk.Toplevel(editor.root)
        self.window.title('CodeMind · Correction comparison')
        self.window.geometry('1180x760')
        self.window.minsize(860, 600)
        frame = ttk.Frame(self.window, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Compare a possible correction', font=('Helvetica', 20, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Red = original lines changed or removed. Green = proposed lines added or changed. The right side is editable.').pack(anchor='w', pady=8)
        self.options = suggestions(self.original, self.base)
        names = ['Manual correction · edit the right-hand view'] + [x.title for x in self.options]
        self.choice = ttk.Combobox(frame, values=names, state='readonly')
        self.choice.pack(fill='x', pady=(0, 10))
        self.choice.current(1 if self.options else 0)
        selection = editor.tree.selection()
        if selection:
            line = self.base.diagnostics[int(selection[0])].line
            for i, item in enumerate(self.options, 1):
                if item.line == line:
                    self.choice.current(i)
                    break
        self.choice.bind('<<ComboboxSelected>>', self.choose)
        views = ttk.Panedwindow(frame, orient='horizontal')
        views.pack(fill='both', expand=True)
        a, b = ttk.Frame(views), ttk.Frame(views)
        views.add(a, weight=1)
        views.add(b, weight=1)
        ttk.Label(a, text='BEFORE · current source').pack(anchor='w', pady=5)
        ttk.Label(b, text='AFTER · proposed source').pack(anchor='w', pady=5)
        self.before, self.after = CodeView(a, readonly=True), CodeView(b)
        self.before.pack(fill='both', expand=True, padx=(0, 6))
        self.after.pack(fill='both', expand=True, padx=(6, 0))
        self.before.set(self.original)
        self.after.text.bind('<<Modified>>', self.changed)
        actions = ttk.Frame(frame)
        actions.pack(fill='x', pady=10)
        self.check_button = ttk.Button(actions, text='Check proposed code', command=self.check)
        self.check_button.pack(side='left')
        self.apply_button = ttk.Button(actions, text='Apply to editor', command=self.apply, state='disabled')
        self.apply_button.pack(side='left', padx=8)
        ttk.Button(actions, text='Close', command=self.window.destroy).pack(side='right')
        self.status = tk.StringVar()
        ttk.Label(frame, textvariable=self.status, wraplength=1080).pack(anchor='w')
        self.choose()
        self.window.after(100, self.poll)

    def proposed(self):
        return self.after.text.get('1.0', 'end-1c')

    def choose(self, event=None):
        index = self.choice.current()
        source = self.original if index <= 0 else self.options[index - 1].source
        self.after.set(source, readonly=False)
        self.invalidate()
        self.colour_changes()

    def invalidate(self):
        self.verified = None
        self.apply_button.configure(state='disabled')
        self.status.set('Preview only. Check the proposed code to see what the compiler reports. No source file has been changed.')

    def changed(self, event=None):
        if self.after.text.edit_modified():
            self.after.text.edit_modified(False)
            self.invalidate()
            self.after.schedule()
            self.colour_changes()

    def colour_changes(self):
        for view in (self.before, self.after):
            for tag in ('removed', 'added'):
                view.text.tag_remove(tag, '1.0', 'end')
        a, b = self.original.splitlines(), self.proposed().splitlines()
        for action, i, j, k, l in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if action in ('replace', 'delete'):
                self.before.text.tag_add('removed', f'{i+1}.0', f'{j+1}.0')
            if action in ('replace', 'insert'):
                self.after.text.tag_add('added', f'{k+1}.0', f'{l+1}.0')

    def check(self):
        if self.busy:
            return
        self.busy = True
        self.check_button.configure(state='disabled')
        self.apply_button.configure(state='disabled')
        self.status.set('Checking the proposed source on a temporary copy…')
        source = self.proposed()
        def worker():
            try:
                report = analyze(source, self.base.filename, self.editor.compiler, self.standard,
                                 str(self.path.parent) if self.path else None)
                self.results.put((source, report, None))
            except (AnalysisError, OSError) as error:
                self.results.put((source, None, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            source, report, error = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.check_button.configure(state='normal')
            if source != self.proposed():
                self.status.set('The preview changed during checking. Check it again.')
            elif error:
                self.status.set(error)
            else:
                self.verified = source
                self.apply_button.configure(state='normal' if source != self.original else 'disabled')
                self.status.set(f'Compiler check: {self.base.errors} → {report.errors} error(s), {self.base.warnings} → {report.warnings} warning(s). '
                                'This checks compilation only. You can apply this edit even if other errors remain; runtime correctness is not verified.')
        self.window.after(100, self.poll)

    def apply(self):
        source = self.proposed()
        if source != self.verified:
            return
        if (self.editor.text() != self.original or self.editor.path != self.path
                or self.editor.standard.get() != self.standard):
            messagebox.showinfo('Source changed', 'The main editor changed. Open a fresh comparison to avoid replacing newer edits.', parent=self.window)
            return
        code = self.editor.code
        code.edit_separator()
        code.delete('1.0', 'end')
        code.insert('1.0', source)
        code.edit_separator()
        code.edit_modified(True)
        self.editor.changed()
        self.editor.status.set('Correction applied to editor. Save source when ready; analyze again for updated feedback.')
        self.window.destroy()

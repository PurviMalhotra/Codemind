"""Local Tkinter editor. Analysis runs off the UI thread; C code is never run."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .engine import AnalysisError, analyze, compare_reports, format_text, learning_question
from .widgets import CodeView


DEMO = """#include <stdio.h>

int main(void) {
    int marks = 70;
    if (marks >= 50 {
        printf("Passed\\n");
    }
    return 0;
}
"""


class Editor:
    def __init__(self, root, file=None, compiler=None, standard="c11"):
        self.root, self.path, self.compiler = root, None, compiler
        self.report = None
        self.previous_report = None
        self.dirty = False
        self.busy = False
        self.results = queue.Queue()
        root.title("CodeMind · C error explainer")
        root.geometry("1280x820")
        root.minsize(900, 650)
        root.configure(background="#eef3f5")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#eef3f5")
        style.configure("TLabel", background="#eef3f5", foreground="#173744", font=("Helvetica", 11))
        style.configure("TButton", font=("Helvetica", 11), padding=7)
        style.configure("Title.TLabel", font=("Helvetica", 25, "bold"))
        outer = ttk.Frame(root, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="CodeMind", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Understand the error. Learn the reason. Try a correction.").pack(anchor="w", pady=(3, 15))
        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(0, 12))
        for label, command in (("Open C file", self.open_file), ("Save source", self.save),
                               ("Load slide demo", self.demo)):
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=(0, 6))
        self.standard = tk.StringVar(value=standard)
        self.standard_box = ttk.Combobox(toolbar, textvariable=self.standard, values=("c99", "c11", "c17"), state="readonly", width=6)
        self.standard_box.pack(side="left", padx=6)
        self.standard_box.bind('<<ComboboxSelected>>', self.change_standard)
        self.analyze_button = ttk.Button(toolbar, text="Analyze C  ⌘↵", command=self.start)
        self.analyze_button.pack(side="left", padx=6)
        self.preview_button = ttk.Button(toolbar, text="Compare correction", command=self.preview, state="disabled")
        self.preview_button.pack(side="left", padx=6)
        ttk.Button(toolbar, text="Compiler lab", command=self.lab).pack(side="left", padx=6)
        self.export_button = ttk.Button(toolbar, text="Export report", command=self.export, state="disabled")
        self.export_button.pack(side="right")
        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=1)
        self.filename = tk.StringVar(value="Untitled C program")
        ttk.Label(left, textvariable=self.filename).pack(anchor="w", pady=(0, 6))
        self.code_view = CodeView(left, font_size=13)
        self.code_view.pack(fill="both", expand=True, padx=(0, 12))
        self.code = self.code_view.text
        self.code.tag_configure("errorline", background="#663d40")
        self.position = tk.StringVar(value="Line 1, column 1")
        ttk.Label(left, textvariable=self.position).pack(anchor="w", pady=6)
        self.code.bind("<KeyRelease>", self.cursor)
        self.code.bind("<ButtonRelease-1>", self.cursor)
        self.code.bind("<<Modified>>", self.changed)
        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)
        feedback, raw, progress = ttk.Frame(notebook), ttk.Frame(notebook), ttk.Frame(notebook)
        notebook.add(feedback, text="Explanations")
        notebook.add(raw, text="Original compiler output")
        notebook.add(progress, text="Fix & check")
        self.progress = ScrolledText(progress, wrap="word", font=("Helvetica", 12), width=42, state="disabled", padx=12, pady=12)
        self.progress.pack(fill="both", expand=True)
        self.put(self.progress, "Analyze the program, edit it, and analyze again to compare compiler feedback.")
        self.summary = tk.StringVar(value="Load a C file or try the slide example.")
        ttk.Label(feedback, textvariable=self.summary, wraplength=430).pack(anchor="w", pady=10)
        self.tree = ttk.Treeview(feedback, columns=("line", "kind", "message"), show="headings", height=6, selectmode="browse")
        for key, label, width in (("line", "Line", 45), ("kind", "Category", 85), ("message", "Compiler message", 290)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=35)
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.details = ScrolledText(feedback, wrap="word", font=("Helvetica", 12), padx=12, pady=12, width=42, state="disabled")
        self.details.pack(fill="both", expand=True, pady=(8, 0))
        self.raw = ScrolledText(raw, wrap="none", font=("Menlo", 11), width=42, state="disabled")
        self.raw.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Ready · C code is checked without running it")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(12, 0))
        root.bind("<Command-Return>", lambda event: self.start())
        root.bind("<Control-Return>", lambda event: self.start())
        root.bind("<Command-s>", lambda event: self.save())
        root.bind("<Control-s>", lambda event: self.save())
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.set_source(DEMO)
        if file:
            self.load(Path(file))
        root.after(100, self.poll)

    @staticmethod
    def put(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def text(self):
        return self.code.get("1.0", "end-1c")

    def invalidate(self):
        self.report = None
        self.export_button.configure(state="disabled")
        self.preview_button.configure(state="disabled")
        self.code.tag_remove("errorline", "1.0", "end")
        self.tree.delete(*self.tree.get_children())
        self.summary.set("Source changed. Analyze to refresh feedback.")
        self.put(self.details, "")
        self.put(self.raw, "")

    def changed(self, event=None):
        if self.code.edit_modified():
            self.dirty = True
            self.invalidate()
            self.code.edit_modified(False)
            self.code_view.schedule()

    def cursor(self, event=None):
        line, col = self.code.index("insert").split(".")
        self.position.set(f"Line {line}, column {int(col) + 1}")

    def change_standard(self, event=None):
        self.invalidate()
        self.previous_report = None
        self.summary.set('C standard changed. Analyze to refresh feedback.')
        self.put(self.progress, 'C standard changed. Analyze again to start a new comparison.')

    def set_source(self, text):
        self.code.delete("1.0", "end")
        self.code.insert("1.0", text)
        self.code.edit_reset()
        self.code.edit_modified(False)
        self.code_view.highlight()
        self.dirty = False
        self.previous_report = None
        self.invalidate()
        self.put(self.progress, "Analyze this program, edit it, and analyze again to compare compiler feedback.")
        self.cursor()

    def can_replace(self):
        return not self.dirty or messagebox.askyesno("Unsaved source", "Discard the unsaved source edits?", parent=self.root)

    def load(self, path):
        try:
            text = path.read_text(encoding="utf-8")
            self.set_source(text)
            self.path = path.resolve()
            self.filename.set(str(self.path))
        except (OSError, UnicodeError) as error:
            messagebox.showerror("Cannot open source", str(error), parent=self.root)

    def open_file(self):
        if self.can_replace():
            path = filedialog.askopenfilename(filetypes=[("C source", "*.c"), ("All files", "*")])
            if path:
                self.load(Path(path))

    def save(self):
        path = self.path
        if path is None:
            selected = filedialog.asksaveasfilename(defaultextension=".c", filetypes=[("C source", "*.c")])
            if not selected:
                return
            path = Path(selected)
        try:
            path.write_text(self.text(), encoding="utf-8")
            self.path = path.resolve()
            self.filename.set(str(self.path))
            self.dirty = False
            self.status.set("Source saved")
        except OSError as error:
            messagebox.showerror("Cannot save source", str(error), parent=self.root)

    def demo(self):
        if self.can_replace():
            self.path = None
            self.filename.set("Slide example · missing closing parenthesis")
            self.set_source(DEMO)

    def start(self):
        if self.busy:
            return
        self.invalidate()
        self.busy = True
        self.analyze_button.configure(state="disabled")
        self.standard_box.configure(state='disabled')
        self.status.set("Reading compiler diagnostics…")
        source, path, standard = self.text(), self.path, self.standard.get()
        def worker():
            try:
                report = analyze(source, str(path) if path else "program.c", self.compiler,
                                 standard, str(path.parent) if path else None)
                self.results.put((source, path, report, None))
            except (AnalysisError, OSError) as error:
                self.results.put((source, path, None, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            source, path, report, error = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.analyze_button.configure(state="normal")
            self.standard_box.configure(state='readonly')
            if source != self.text() or path != self.path:
                self.status.set("Source changed during analysis. Analyze again for current feedback.")
            elif error:
                self.summary.set("Analysis could not complete")
                self.put(self.details, error)
                self.status.set("Compiler setup or input error")
            else:
                self.report = report
                self.export_button.configure(state="normal")
                self.preview_button.configure(state="normal" if report.diagnostics else "disabled")
                tip = "Fix the first error, then analyze again." if report.errors else "Compiler checks passed. Review any warnings below."
                self.summary.set(f"{report.errors} error(s) · {report.warnings} warning(s)\n{tip}")
                if self.previous_report is not None:
                    self.put(self.progress, compare_reports(self.previous_report, report))
                else:
                    self.put(self.progress, "First check recorded. Edit this program and analyze again to compare diagnostic counts.")
                self.previous_report = report
                self.put(self.raw, report.raw_output or "No compiler diagnostics.")
                for index, item in enumerate(report.diagnostics):
                    self.tree.insert("", "end", iid=str(index), values=(item.line or "—", item.category, item.message))
                if report.diagnostics:
                    self.tree.selection_set("0")
                else:
                    self.put(self.details, "Compiler checks passed.\n\nNo errors or warnings were reported. These checks do not prove that the program links or behaves correctly at runtime.")
                self.status.set("Analysis complete · Suggested corrections are guidance; edits require another check")
        self.root.after(100, self.poll)

    def select(self, event=None):
        selection = self.tree.selection()
        if not selection or self.report is None:
            return
        item = self.report.diagnostics[int(selection[0])]
        text = (f"{item.severity.upper()} · {item.category}\n{item.file}:{item.line}:{item.column}\n\n"
                f"ORIGINAL MESSAGE\n{item.message}\n\nSOURCE\n{item.source or '(See compiler output for this location)'}\n\n"
                f"WHY IT HAPPENS\n{item.explanation}\n\nPOSSIBLE CORRECTION\n{item.suggestion}")
        if item.notes:
            text += "\n\nRELATED NOTES\n" + "\n".join(item.notes)
        text += "\n\nCHECK YOUR UNDERSTANDING\n" + learning_question(item.rule)
        self.put(self.details, text)
        self.code.tag_remove("errorline", "1.0", "end")
        if item.source and item.line > 0 and item.file == self.report.filename:
            self.code.tag_add("errorline", f"{item.line}.0", f"{item.line}.end")
            self.code.see(f"{item.line}.0")

    def export(self):
        if not self.report:
            return
        selected = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text report", "*.txt"), ("JSON report", "*.json")])
        if not selected:
            return
        path = Path(selected)
        if self.path and path.resolve() == self.path.resolve():
            messagebox.showerror("Choose another file", "A report cannot overwrite the C source.", parent=self.root)
            return
        try:
            path.write_text(self.report.to_json() if path.suffix.lower() == ".json" else format_text(self.report), encoding="utf-8")
            self.status.set(f"Report saved to {path}")
        except OSError as error:
            messagebox.showerror("Cannot export report", str(error), parent=self.root)

    def preview(self):
        if self.report is not None:
            from .preview import CorrectionPreview
            CorrectionPreview(self)

    def lab(self):
        from .lab_gui import LabWindow
        LabWindow(self.root)

    def close(self):
        if self.can_replace():
            self.root.destroy()


def launch(file=None, compiler=None, standard="c11"):
    root = tk.Tk()
    Editor(root, file, compiler, standard)
    root.mainloop()

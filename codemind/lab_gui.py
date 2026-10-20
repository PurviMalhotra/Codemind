"""Interactive pipeline and AST viewer driven by real Flex/Yacc artifacts."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import textwrap

from .lab import DEMO, CONTROL_DEMO, LabError, layout_graph, run_lab
from .flow_view import FlowView
from .widgets import CodeView


STAGES = [('tokens','1 · Tokens','Flex turns source characters into tokens. The table shows the actual lexer output.'),
          ('ast','2 · Parse / AST','Yacc checks the mini-language grammar and builds an AST. Solid edges are operands/types; dashed edges link successive statements.'),
          ('symbols','3 · Scopes','Scope 0 is global. Each block has its own scope. Inner declarations can shadow outer names; Storage is the unique TAC identity.'),
          ('tac','4 · TAC','The lab converts expressions to three-address code, using temporary names for intermediate results.'),
          ('cfg','5 · Flow graph','Basic blocks come from actual TAC. Edges show execution paths; loop backedges return to the condition.'),
          ('optimized','6 · Optimize','Constants are propagated only within a basic block. Labels and branches discard facts so loops and joins remain safe.')]


class LabWindow:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title('CodeMind · Flex/Yacc visual learning lab')
        self.window.geometry('1280x840')
        self.window.minsize(950, 650)
        self.results = queue.Queue()
        self.result = None
        self.busy = False
        self.dirty = False
        self.scale = 1.0
        frame = ttk.Frame(self.window, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Inside the compiler', font=('Helvetica', 23, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Flex/Yacc C-like subset · arithmetic, if/else, while, and block scope · full C functions, for loops, and arrays are not supported.').pack(anchor='w', pady=(5, 12))
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x')
        ttk.Button(toolbar, text='Open .src', command=self.open).pack(side='left')
        ttk.Button(toolbar, text='Arithmetic example', command=self.demo).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Loop + if/else example', command=lambda:self.demo(CONTROL_DEMO)).pack(side='left', padx=(0,6))
        ttk.Button(toolbar, text='Save .src as…', command=self.save).pack(side='left')
        self.run_button = ttk.Button(toolbar, text='Build & inspect', command=self.run)
        self.run_button.pack(side='left', padx=12)
        self.status = tk.StringVar(value='Ready. Build & inspect to generate real compiler artifacts.')
        ttk.Label(frame, textvariable=self.status, wraplength=1160).pack(anchor='w', pady=10)
        stages = ttk.Frame(frame)
        stages.pack(fill='x', pady=(0, 10))
        self.stage_labels = {}
        for key, title, _ in STAGES:
            group = ttk.Frame(stages)
            group.pack(side='left', fill='x', expand=True, padx=3)
            ttk.Button(group, text=title, command=lambda k=key:self.show(k)).pack(fill='x')
            label = ttk.Label(group, text='Not run', anchor='center')
            label.pack(fill='x', pady=4)
            self.stage_labels[key] = label
        panes = ttk.Panedwindow(frame, orient='horizontal')
        panes.pack(fill='both', expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=2)
        ttk.Label(left, text='MINI-LANGUAGE SOURCE · independent of your C editor').pack(anchor='w', pady=5)
        self.source = CodeView(left)
        self.source.pack(fill='both', expand=True, padx=(0, 10))
        self.source.text.bind('<<Modified>>', self.changed)
        self.source.text.tag_configure('selectednode',background='#315765')
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill='both', expand=True)
        self.pages = {}
        for key, title, explanation in STAGES:
            page = ttk.Frame(self.notebook, padding=8)
            self.notebook.add(page, text=title.split(' · ')[1])
            self.pages[key] = page
            ttk.Label(page, text=explanation, wraplength=630).pack(anchor='w', pady=(0, 8))
        self.tokens = self.table(self.pages['tokens'], ('Line','Token','Lexeme'))
        self.symbols = self.table(self.pages['symbols'], ('Name','Type','Scope','Depth','Storage','Line'))
        self.flow = FlowView(self.pages['cfg'])
        self.flow.pack(fill='both',expand=True)
        ast = self.pages['ast']
        tools = ttk.Frame(ast)
        tools.pack(fill='x')
        ttk.Button(tools, text='−', width=3, command=lambda:self.zoom(0.8)).pack(side='left')
        ttk.Button(tools, text='+', width=3, command=lambda:self.zoom(1.25)).pack(side='left', padx=5)
        ttk.Button(tools, text='Reset view', command=self.reset_view).pack(side='left')
        ttk.Button(tools, text='Fit tree', command=self.fit_tree).pack(side='left', padx=5)
        self.node_info = tk.StringVar(value='Click a node to inspect it. Scroll to explore the tree.')
        ttk.Label(ast, textvariable=self.node_info, wraplength=630).pack(anchor='w', pady=8)
        graph = ttk.Frame(ast)
        graph.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(graph, bg='#f8fbfc', highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(graph, orient='vertical', command=self.canvas.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(graph, orient='horizontal', command=self.canvas.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        graph.rowconfigure(0, weight=1)
        graph.columnconfigure(0, weight=1)
        self.views = {}
        for key in ('tac', 'optimized'):
            widget = ScrolledText(self.pages[key], wrap='none', font=('Menlo',12), state='disabled')
            widget.pack(fill='both', expand=True)
            self.views[key] = widget
        output_page = ttk.Frame(self.notebook)
        self.notebook.add(output_page, text='Compiler log')
        self.log = ScrolledText(output_page, wrap='word', font=('Menlo',11), state='disabled')
        self.log.pack(fill='both', expand=True)
        self.source.set(DEMO, readonly=False)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.after(100, self.poll)

    @staticmethod
    def table(parent, columns):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True)
        widget = ttk.Treeview(frame, columns=columns, show='headings')
        for name in columns:
            widget.heading(name, text=name)
            widget.column(name, width=110, minwidth=50)
        widget.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=widget.yview)
        scroll.pack(side='right', fill='y')
        widget.configure(yscrollcommand=scroll.set)
        return widget

    @staticmethod
    def put(widget, text):
        widget.configure(state='normal')
        widget.delete('1.0','end')
        widget.insert('1.0',text)
        widget.configure(state='disabled')

    def clear(self):
        self.result = None
        for table in (self.tokens, self.symbols):
            table.delete(*table.get_children())
        self.canvas.delete('all')
        self.flow.set_graph(None)
        self.source.text.tag_remove('selectednode','1.0','end')
        for view in (*self.views.values(), self.log):
            self.put(view,'')
        for label in self.stage_labels.values():
            label.configure(text='Not run', foreground='#536b75')
        self.node_info.set('Build & inspect to generate the AST.')

    def changed(self, event=None):
        if self.source.text.edit_modified():
            self.source.text.edit_modified(False)
            self.source.schedule()
            self.dirty = True
            self.clear()
            self.status.set('Lab source changed. Build & inspect again for current artifacts.')

    def can_replace(self):
        return not self.dirty or messagebox.askyesno('Unsaved lab source','Discard unsaved lab source edits?',parent=self.window)

    def demo(self,source=DEMO):
        if self.can_replace():
            self.source.set(source, readonly=False)
            self.clear()
            self.dirty = False
            self.status.set('Lab example loaded. Build & inspect to explore its compiler stages.')

    def open(self):
        if not self.can_replace():
            return
        path = filedialog.askopenfilename(parent=self.window, filetypes=[('Mini-language source','*.src')])
        if path:
            try:
                self.source.set(Path(path).read_text(encoding='utf-8'), readonly=False)
                self.clear()
                self.dirty = False
            except (OSError, UnicodeError) as error:
                messagebox.showerror('Cannot open source', str(error), parent=self.window)

    def save(self):
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension='.src', filetypes=[('Mini-language source','*.src')])
        if path:
            try:
                Path(path).write_text(self.source.text.get('1.0','end-1c'), encoding='utf-8')
                self.dirty = False
            except OSError as error:
                messagebox.showerror('Cannot save source', str(error), parent=self.window)

    def run(self):
        if self.busy:
            return
        self.clear()
        self.busy = True
        self.run_button.configure(state='disabled')
        self.status.set('Building the real Flex/Yacc compiler and collecting artifacts in a temporary directory…')
        source = self.source.text.get('1.0','end-1c')
        def worker():
            try:
                self.results.put((source,run_lab(source),None))
            except LabError as error:
                self.results.put((source,None,str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            source,result,error = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.run_button.configure(state='normal')
            if source != self.source.text.get('1.0','end-1c'):
                self.status.set('Lab source changed during compilation. Build & inspect again.')
            elif error:
                self.status.set('Lab could not run. See Compiler log for setup details.')
                self.put(self.log,error)
                self.notebook.select(len(STAGES))
            else:
                self.result = result
                for key, state in result.stages.items():
                    self.stage_labels[key].configure(text={'passed':'✓ Completed','failed':'✕ Failed','skipped':'— Skipped'}[state],
                                                     foreground={'passed':'#087f6a','failed':'#b33a46','skipped':'#536b75'}[state])
                for token in result.tokens:
                    self.tokens.insert('','end',values=token)
                for symbol in result.scope_symbols:
                    self.symbols.insert('','end',values=symbol)
                for key in self.views:
                    self.put(self.views[key],getattr(result,key) or 'This stage produced no code. Check the pipeline status and compiler log.')
                self.put(self.log,result.output + '\n\nBUILD LOG\n' + result.build_output)
                self.flow.set_graph(result.cfg)
                self.scale = 1.0
                self.draw()
                self.node_info.set(f'{len(result.nodes)} AST nodes. Click a node to inspect it; use Fit tree or zoom and scroll to explore.')
                self.status.set('Artifacts ready. Click AST nodes to highlight their source lines; explore Scopes and Flow graph for name visibility and execution paths.'
                                if all(x=='passed' for x in result.stages.values()) else 'Compilation stopped at the first failed stage. Later stages are skipped; details are in Compiler log.')
                self.show('ast' if result.nodes else 'tokens')
        self.window.after(100,self.poll)

    def show(self,key):
        self.notebook.select(self.pages[key])

    def draw(self):
        self.canvas.delete('all')
        if not self.result or not self.result.nodes:
            self.canvas.create_text(20,25,anchor='nw',text='No AST generated. Check syntax and the compiler log.',fill='#536b75')
            return
        positions = layout_graph(self.result.nodes,self.result.edges)
        scale = self.scale
        for parent,child,next_statement in self.result.edges:
            x,y=positions[parent]
            xx,yy=positions[child]
            options = {'dash':(5,3)} if next_statement else {}
            self.canvas.create_line(x*scale,(y+28)*scale,xx*scale,(yy-28)*scale,
                                    arrow='last',fill='#91a8b1',width=2,**options)
            label = self.result.ast_edge_labels.get((parent,child),'')
            if label in ('condition','then','else','body'):
                self.canvas.create_text((x+xx)/2*scale,(y+yy)/2*scale,text=label,
                                        fill='#486b7a',font=('Helvetica',max(6,int(9*scale))))
        for key,label in self.result.nodes.items():
            x,y=positions[key]
            colour = '#ffe0cb' if label in ('If','While') else '#eee4f7' if label.startswith('Block') else '#ddd7fa' if label.startswith('Declaration') else '#d4eee8' if label.startswith(('Identifier','Assignment')) else '#fff0d7' if label.startswith(('Integer','Float')) else '#e0edf5'
            tag = f'node-{key}'
            self.canvas.create_rectangle((x-82)*scale,(y-28)*scale,(x+82)*scale,(y+28)*scale,
                                         fill=colour,outline='#8aa3af',width=1,tags=(tag,))
            font_size = max(3,int(11*scale))
            chars = max(8,min(22,int(150*scale/(font_size*0.6))))
            shown = textwrap.fill(textwrap.shorten(label,width=chars*2,placeholder='…'),chars)
            self.canvas.create_text(x*scale,y*scale,text=shown,
                                    font=('Helvetica',font_size),fill='#173744',tags=(tag,))
            self.canvas.tag_bind(tag,'<Button-1>',lambda event,k=key:self.inspect(k))
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def inspect(self,key):
        label=self.result.nodes[key]
        kind, _, value = label.partition(': ')
        reasons = {
            'If': 'The condition selects the then branch or the optional else branch.',
            'While': 'The condition is checked before every iteration; the body repeats while it is nonzero.',
            'Block': 'This block creates a scope. Its local names are hidden after the block ends.',
            'Empty statement': 'A semicolon by itself performs no operation.',
            'Program': 'The root links the statements that make up this program.',
            'Declaration': f'Declares {value}; its child records the declared type.',
            'Assignment': f'Stores the value of its child expression in {value}.',
            'Operator': f'Combines its two operand children using {value}.',
            'Unary': f'Applies the sign {value} to one operand.',
            'Identifier': 'Names a variable or records a declaration type in this teaching AST.',
            'Integer': 'An integer literal written in the source.',
            'Float': 'A floating-point literal written in the source.',
        }
        line = self.result.node_lines.get(key)
        suffix = f' Source line {line}.' if line else ''
        self.node_info.set(f'Node {key}: {label}. ' + reasons.get(kind,'Solid edges connect child nodes.') + suffix)
        self.source.text.tag_remove('selectednode','1.0','end')
        if line:
            self.source.text.tag_add('selectednode',f'{line}.0',f'{line}.end')
            self.source.text.see(f'{line}.0')

    def zoom(self,factor):
        self.scale=max(0.18,min(2.0,self.scale*factor))
        self.draw()

    def reset_view(self):
        self.scale=1.0
        self.draw()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def fit_tree(self):
        if self.result and self.result.nodes:
            positions = layout_graph(self.result.nodes,self.result.edges)
            xs, ys = zip(*positions.values())
            self.scale = max(0.18,min(1.0,(self.canvas.winfo_width()-20)/(max(xs)-min(xs)+180),
                                      (self.canvas.winfo_height()-20)/(max(ys)-min(ys)+75)))
            self.draw()
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)

    def close(self):
        if self.can_replace():
            self.window.destroy()

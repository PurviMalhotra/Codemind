"""Reusable Tk source view with scroll-synchronised line numbers."""
import tkinter as tk
from tkinter import ttk

from .syntax import spans


class CodeView(ttk.Frame):
    def __init__(self, parent, readonly=False, font_size=12, **kwargs):
        super().__init__(parent, **kwargs)
        self.pending = None
        self.gutter = tk.Canvas(self, width=48, bg='#173642', highlightthickness=0)
        self.gutter.grid(row=0, column=0, sticky='ns')
        self.text = tk.Text(self, wrap='none', undo=not readonly, width=35,
                            font=('Menlo', font_size), bg='#102a36', fg='#e5f2f4',
                            insertbackground='#7ee0ce', selectbackground='#315765',
                            padx=10, pady=10, borderwidth=0, highlightthickness=0)
        self.text.grid(row=0, column=1, sticky='nsew')
        self.vscroll = ttk.Scrollbar(self, orient='vertical', command=self.text.yview)
        self.vscroll.grid(row=0, column=2, sticky='ns')
        self.hscroll = ttk.Scrollbar(self, orient='horizontal', command=self.text.xview)
        self.hscroll.grid(row=1, column=1, sticky='ew')
        self.text.configure(yscrollcommand=self.scrolled, xscrollcommand=self.hscroll.set)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        for tag, colour in {'keyword':'#b7a5ff', 'string':'#a8d999', 'comment':'#8ca7ae',
                            'number':'#ffc980', 'directive':'#81cdeb'}.items():
            self.text.tag_configure(tag, foreground=colour)
        self.text.tag_configure('removed', background='#663d40')
        self.text.tag_configure('added', background='#21564c')
        self.text.bind('<Configure>', lambda e: self.redraw())
        self.gutter.bind('<Configure>', lambda e: self.redraw())
        self.text.bind('<KeyRelease>', lambda e: self.schedule(), add='+')
        if readonly:
            self.text.configure(state='disabled')

    def scrolled(self, first, last):
        self.vscroll.set(first, last)
        self.redraw()

    def redraw(self):
        self.gutter.delete('all')
        index = self.text.index('@0,0')
        while True:
            box = self.text.dlineinfo(index)
            if box is None:
                break
            line = index.split('.')[0]
            self.gutter.create_text(39, box[1] + box[3] / 2, text=line, anchor='e',
                                    fill='#9bb5bf', font=self.text.cget('font'))
            index = self.text.index(f'{index}+1line')

    def schedule(self):
        if self.pending is not None:
            self.after_cancel(self.pending)
        self.pending = self.after(160, self.highlight)

    def highlight(self):
        self.pending = None
        source = self.text.get('1.0', 'end-1c')
        for tag in ('keyword', 'string', 'comment', 'number', 'directive'):
            self.text.tag_remove(tag, '1.0', 'end')
        for tag, start, end in spans(source):
            self.text.tag_add(tag, f'1.0+{start}c', f'1.0+{end}c')
        self.redraw()

    def set(self, source, readonly=True):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', source)
        self.text.edit_modified(False)
        self.text.configure(state='disabled' if readonly else 'normal')
        self.highlight()

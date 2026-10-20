"""Scrollable, clickable basic-block CFG, including labelled branch/back edges."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from .cfg import layout_cfg


class FlowView(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent)
        self.graph = None
        self.scale = 1.0
        tools = ttk.Frame(self)
        tools.pack(fill='x')
        for text,command in (('−',lambda:self.zoom(0.8)),('+',lambda:self.zoom(1.25)),
                             ('Fit graph',self.fit),('Reset view',self.reset),('Export .dot',self.export)):
            ttk.Button(tools,text=text,command=command).pack(side='left',padx=(0,5))
        self.info = tk.StringVar(value='Build & inspect a valid lab program to view its control flow.')
        ttk.Label(self,textvariable=self.info,wraplength=630).pack(anchor='w',pady=8)
        frame = ttk.Frame(self)
        frame.pack(fill='both',expand=True)
        self.canvas = tk.Canvas(frame,bg='#f8fbfc',highlightthickness=0)
        self.canvas.grid(row=0,column=0,sticky='nsew')
        v = ttk.Scrollbar(frame,orient='vertical',command=self.canvas.yview)
        h = ttk.Scrollbar(frame,orient='horizontal',command=self.canvas.xview)
        v.grid(row=0,column=1,sticky='ns')
        h.grid(row=1,column=0,sticky='ew')
        self.canvas.configure(xscrollcommand=h.set,yscrollcommand=v.set)
        frame.rowconfigure(0,weight=1)
        frame.columnconfigure(0,weight=1)

    def set_graph(self,graph):
        self.graph = graph
        self.scale = 1.0
        self.info.set('True/false edges show branches. Purple loop-back edges repeat a condition. Click a block for its full TAC.'
                      if graph else 'No CFG yet. Syntax and semantic checks must pass before TAC and control flow are generated.')
        self.draw()

    def draw(self):
        self.canvas.delete('all')
        if not self.graph:
            return
        positions,heights = layout_cfg(self.graph)
        s = self.scale
        for index,(a,b,label) in enumerate(self.graph.edges):
            x,y = positions[a]
            xx,yy = positions[b]
            back = a.startswith('B') and b.startswith('B') and int(b[1:]) <= int(a[1:])
            colour = '#8651ad' if back else '#b34b48' if label=='false' else '#198170' if label=='true' else '#8aa3af'
            if back:
                lane = min(x,xx)-180-(index%3)*20
                bottom = y+heights[a]/2+30
                coords = (x,y+heights[a]/2,x,bottom,lane,bottom,lane,yy,xx-140,yy)
                tx,ty = lane, (y+yy)/2
                shown = 'loop back'
            else:
                start,end = y+heights[a]/2,yy-heights[b]/2
                mid = (start+end)/2
                coords = (x,start,x,mid,xx,mid,xx,end)
                tx,ty = (x+xx)/2,mid
                shown = label
            self.canvas.create_line(*(v*s for v in coords),arrow='last',fill=colour,width=2,
                                    dash=(6,3) if back else (),joinstyle='round')
            if shown not in ('next','jump'):
                self.canvas.create_text(tx*s+5,ty*s-8,text=shown,fill=colour,
                                        font=('Helvetica',max(7,int(10*s))),anchor='w')
        for key,label in self.graph.nodes.items():
            x,y = positions[key]
            h = heights[key]/2
            colour = '#d4eee8' if key in ('entry','exit') else '#fff0d7' if 'ifFalse ' in label else '#e0edf5'
            tag = 'block-'+key
            self.canvas.create_rectangle((x-140)*s,(y-h)*s,(x+140)*s,(y+h)*s,fill=colour,outline='#8aa3af',tags=(tag,))
            font_size = max(3,int(10*s))
            chars = max(8,int(260*s/(font_size*0.65)))
            shown = '\n'.join(line if len(line)<=chars else line[:chars-1]+'…' for line in label.splitlines())
            self.canvas.create_text(x*s,y*s,text=shown,font=('Menlo',font_size),fill='#173744',tags=(tag,))
            self.canvas.tag_bind(tag,'<Button-1>',lambda event,k=key:self.inspect(k))
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def inspect(self,key):
        self.info.set(self.graph.nodes[key].replace('\n',' · '))

    def zoom(self,factor):
        self.scale = max(0.15,min(2.0,self.scale*factor))
        self.draw()

    def fit(self):
        if not self.graph:
            return
        self.scale = 1.0
        self.draw()
        left,top,right,bottom = self.canvas.bbox('all')
        self.scale = max(0.15,min(1.0,(self.canvas.winfo_width()-30)/max(1,right-left),
                                    (self.canvas.winfo_height()-30)/max(1,bottom-top)))
        self.draw()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def reset(self):
        self.scale = 1.0
        self.draw()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def export(self):
        if not self.graph:
            return
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(),defaultextension='.dot',filetypes=[('Graphviz graph','*.dot')])
        if path:
            try:
                Path(path).write_text(self.graph.to_dot(),encoding='utf-8')
            except OSError as error:
                messagebox.showerror('Cannot export graph',str(error),parent=self.winfo_toplevel())

"""Basic-block control-flow graph derived from the lab's actual TAC instructions."""
from dataclasses import dataclass
import json
import re


@dataclass
class FlowGraph:
    nodes: dict
    edges: list

    def to_dot(self):
        lines = ['digraph CFG {', '  node [shape=box];']
        for key, label in self.nodes.items():
            lines.append(f'  {key} [label={json.dumps(label)}];')
        for parent, child, label in self.edges:
            lines.append(f'  {parent} -> {child} [label={json.dumps(label)}];')
        return '\n'.join(lines + ['}']) + '\n'


def build_cfg(tac):
    instructions = [line.strip() for line in tac.splitlines() if line.strip()]
    if not instructions:
        return FlowGraph({'entry':'Entry', 'exit':'Exit'}, [('entry','exit','next')])
    labels = {line[:-1]:i for i,line in enumerate(instructions) if re.fullmatch(r'L\d+:',line)}
    leaders = {0}
    for i,line in enumerate(instructions):
        if line.endswith(':'):
            leaders.add(i)
        if line.startswith(('goto ', 'ifFalse ')) and i + 1 < len(instructions):
            leaders.add(i+1)
    starts = sorted(leaders)
    blocks = [instructions[start:starts[i+1] if i+1 < len(starts) else len(instructions)]
              for i,start in enumerate(starts)]
    membership = {}
    for block,start in enumerate(starts):
        stop = starts[block+1] if block+1<len(starts) else len(instructions)
        membership.update({i:f'B{block+1}' for i in range(start,stop)})
    nodes = {'entry':'Entry'}
    nodes.update({f'B{i+1}':f'B{i+1}\n'+'\n'.join(block) for i,block in enumerate(blocks)})
    nodes['exit'] = 'Exit'
    edges = [('entry','B1','next')]
    def target(label):
        if label not in labels:
            raise ValueError(f'Undefined TAC label: {label}')
        return membership[labels[label]]
    for i,block in enumerate(blocks):
        key = f'B{i+1}'
        following = f'B{i+2}' if i+1 < len(blocks) else 'exit'
        last = block[-1]
        if last.startswith('ifFalse '):
            edges.append((key,target(last.rsplit(' ',1)[1]),'false'))
            edges.append((key,following,'true'))
        elif last.startswith('goto '):
            label = last.split()[1]
            edges.append((key,target(label),'jump'))
        else:
            edges.append((key,following,'next'))
    return FlowGraph(nodes,edges)


def layout_cfg(graph):
    """Forward-edge layers put joins below both arms, ignoring loop backedges."""
    children = {key:[] for key in graph.nodes}
    for parent,child,_ in graph.edges:
        children[parent].append(child)
    depths = {'entry':0}
    # build_cfg creates B1..Bn in instruction order. All non-loop edges point
    # forward in this ordering, so a single forward pass computes join depths.
    for parent in graph.nodes:
        depths.setdefault(parent,0)
        for child in children[parent]:
            back = parent.startswith('B') and child.startswith('B') and int(child[1:]) <= int(parent[1:])
            if not back:
                depths[child] = max(depths.get(child,0),depths[parent]+1)
    rows = {}
    for key in graph.nodes:
        rows.setdefault(depths[key],[]).append(key)
    positions = {}
    heights = {}
    y = 65
    for depth,keys in sorted(rows.items()):
        height = max(65, max(35+len(graph.nodes[key].splitlines())*17 for key in keys))
        for i,key in enumerate(keys):
            positions[key] = (150+i*330,y+height/2)
            heights[key] = height
        y += height+90
    return positions,heights

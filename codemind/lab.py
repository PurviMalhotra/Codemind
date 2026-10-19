"""Run the real Flex/Yacc lab in an isolated directory and collect its artifacts."""
from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


DEMO = '''int a;
int b;
float result;

a = 10;
b = 5 + 2 * 3;
result = (a + b) / 2.0;
'''


class LabError(Exception):
    pass


@dataclass
class LabResult:
    stages: dict = field(default_factory=dict)
    tokens: list = field(default_factory=list)
    nodes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)
    symbols: list = field(default_factory=list)
    ast_text: str = ''
    tac: str = ''
    optimized: str = ''
    output: str = ''
    build_output: str = ''


def graph_from_dot(text):
    nodes, edges = {}, []
    for line in text.splitlines():
        node = re.search(r'\bn(\d+) \[label="([^"]*)"\]', line)
        edge = re.search(r'\bn(\d+) -> n(\d+)', line)
        if node:
            nodes[node[1]] = node[2]
        if edge:
            edges.append((edge[1], edge[2], 'next statement' in line))
    return nodes, edges


def section(output, start, end):
    if start not in output:
        return ''
    return output.split(start, 1)[1].split(end, 1)[0].strip()


def run_lab(source, lab_dir=None):
    if len(source.encode('utf-8')) > 50_000:
        raise LabError('Use a lab program smaller than 50 KB so its AST stays readable.')
    lab_dir = Path(lab_dir) if lab_dir else Path(__file__).resolve().parent.parent / 'mini_compiler'
    if not shutil.which('make'):
        raise LabError('The lab needs make, Flex, a Yacc-compatible parser generator, and a C compiler. Install these tools to build the lab.')
    result = LabResult(stages={name:'skipped' for name in ('tokens', 'ast', 'symbols', 'tac', 'optimized')})
    def run(command, cwd, timeout=30):
        try:
            return subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise LabError('The lab exceeded its time limit. Try a smaller program or check the build tools.') from error
        except OSError as error:
            raise LabError(str(error)) from error
    with tempfile.TemporaryDirectory(prefix='codemind-lab-') as directory:
        work = Path(directory)
        build = work / 'build'
        build.mkdir()
        try:
            for path in lab_dir.iterdir():
                if path.suffix in ('.c', '.h', '.l', '.y') or path.name == 'Makefile':
                    if path.name not in ('y.tab.c', 'y.tab.h', 'lex.yy.c'):
                        shutil.copy2(path, build / path.name)
        except OSError as error:
            raise LabError(f'Cannot read the lab source: {error}') from error
        built = run(['make'], build)
        result.build_output = built.stdout + built.stderr
        if built.returncode:
            raise LabError('The Flex/Yacc lab could not build. Check that Flex, Yacc/Bison, make, and a C compiler are installed.\n\n' + result.build_output)
        source_path = work / 'program.src'
        source_path.write_text(source, encoding='utf-8')
        binary = str(build / 'mini_compiler')
        lexed = run([binary, '--tokens', str(source_path)], work, 10)
        result.tokens = [line.split('\t', 2) for line in lexed.stdout.splitlines() if line.count('\t') >= 2]
        result.stages['tokens'] = 'passed' if lexed.returncode == 0 else 'failed'
        if lexed.returncode:
            result.output = lexed.stderr
            return result
        compiled = run([binary, str(source_path)], work, 10)
        result.output = compiled.stdout + compiled.stderr
        ast_path = work / 'ast.dot'
        if not ast_path.exists():
            result.stages['ast'] = 'failed'
            return result
        result.nodes, result.edges = graph_from_dot(ast_path.read_text())
        if len(result.nodes) > 300:
            raise LabError('This AST has more than 300 nodes. Use a smaller lab example to keep the interactive diagram readable.')
        result.ast_text = section(compiled.stdout, '=== AST / PARSE STRUCTURE ===', 'Wrote ast.dot.')
        result.stages['ast'] = 'passed'
        result.stages['symbols'] = 'passed' if compiled.returncode == 0 else 'failed'
        table = section(compiled.stdout, 'Symbol table:', 'Semantic analysis')
        for line in table.splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[1] in ('int', 'float'):
                result.symbols.append(tuple(fields))
        for key, name in (('tac','tac.txt'), ('optimized','optimized_tac.txt')):
            path = work / name
            if path.exists() and compiled.returncode == 0:
                setattr(result, key, path.read_text())
                result.stages[key] = 'passed'
        return result


def layout_graph(nodes, edges):
    """Lay out the exported AST tree without requiring Graphviz or an image library."""
    children = {key:[] for key in nodes}
    incoming = set()
    for parent, child, _ in edges:
        if parent in nodes and child in nodes:
            children[parent].append(child)
            incoming.add(child)
    positions = {}
    cursor = [0]
    def visit(key, depth):
        if key in positions:
            return positions[key][0]
        positions[key] = (0, depth * 105 + 55)
        xs = [visit(child, depth + 1) for child in children[key] if child not in positions]
        if xs:
            x = (min(xs) + max(xs)) / 2
        else:
            x = cursor[0] * 185 + 100
            cursor[0] += 1
        positions[key] = (x, depth * 105 + 55)
        return x
    for key in nodes:
        if key not in incoming:
            visit(key, 0)
    for key in nodes:
        if key not in positions:
            visit(key, 0)
    return positions

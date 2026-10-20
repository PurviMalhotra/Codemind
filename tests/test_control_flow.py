"""Execute generated TAC in tests to verify control flow and optimizer preservation.

The product itself still never executes user programs. This bounded evaluator is a
test oracle for the lab's documented double-based numeric model.
"""
from pathlib import Path
import math
import shutil
import subprocess
import tempfile
import unittest

from codemind.cfg import build_cfg, layout_cfg
from codemind.lab import CONTROL_DEMO, run_lab


def execute(tac, limit=10000):
    lines = [x.strip() for x in tac.splitlines() if x.strip()]
    labels = {x[:-1]:i for i,x in enumerate(lines) if x.endswith(':')}
    values = {}
    def value(token):
        try:
            return float(token)
        except ValueError:
            if token not in values:
                raise AssertionError('Uninitialized TAC read: '+token)
            return values[token]
    pc = 0
    steps = 0
    while pc < len(lines):
        steps += 1
        if steps > limit:
            raise AssertionError('TAC exceeded execution limit')
        line = lines[pc]
        if line.endswith(':'):
            pc += 1
            continue
        parts = line.split()
        if parts[0]=='goto':
            pc = labels[parts[1]]
            continue
        if parts[0]=='ifFalse':
            pc = labels[parts[3]] if not value(parts[1]) else pc+1
            continue
        name,equals,*rhs = parts
        if equals!='=':
            raise AssertionError(line)
        if len(rhs)==1:
            result = value(rhs[0])
        elif len(rhs)==2:
            result = -value(rhs[1]) if rhs[0]=='-' else value(rhs[1])
        else:
            a,op,b = rhs
            a,b = value(a),value(b)
            # Lambdas avoid evaluating division in branches that do not divide.
            result = {'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b,
                      '%':lambda:math.fmod(a,b),'<':lambda:float(a<b),'<=':lambda:float(a<=b),
                      '>':lambda:float(a>b),'>=':lambda:float(a>=b),'==':lambda:float(a==b),
                      '!=':lambda:float(a!=b)}[op]()
        values[name] = result
        pc += 1
    return values


class ControlCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='codemind-test-build-')
        cls.addClassCleanup(cls.temp.cleanup)
        build = Path(cls.temp.name)
        source = Path(__file__).resolve().parent.parent/'mini_compiler'
        for path in source.iterdir():
            if path.name not in ('lex.yy.c','y.tab.c','y.tab.h') and (path.suffix in ('.c','.h','.l','.y') or path.name=='Makefile'):
                shutil.copy2(path,build/path.name)
        result = subprocess.run(['make'],cwd=build,capture_output=True,text=True,timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout+result.stderr)
        if 'conflict' in result.stderr:
            raise AssertionError('Unexpected Yacc conflict: '+result.stderr)
        cls.binary = build/'mini_compiler'

    def compile(self,source,status=0):
        with tempfile.TemporaryDirectory(prefix='codemind-test-run-') as directory:
            path = Path(directory)/'program.src'
            path.write_text(source)
            result = subprocess.run([str(self.binary),str(path)],cwd=directory,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,status,result.stdout+result.stderr)
            files = {p.name:p.read_text() for p in Path(directory).iterdir() if p.suffix in ('.txt','.dot','.tsv')}
            if status:
                self.assertNotIn('tac.txt',files)
            return result,files

    def check_values(self,source,expected):
        _,files = self.compile(source)
        original = execute(files['tac.txt'])
        optimized = execute(files['optimized_tac.txt'])
        self.assertEqual(original,optimized,'Optimizer changed execution results')
        for key,value in expected.items():
            self.assertAlmostEqual(original[key],value,msg=key)
        return files

    def test_while_if_else_and_block_local(self):
        files = self.check_values(CONTROL_DEMO,{'i':5,'total':8,'bonus@S3':1})
        self.assertIn('label="While"',files['ast.dot'])
        self.assertIn('label="If"',files['ast.dot'])
        self.assertIn('label="else"',files['ast.dot'])

    def test_nested_loops(self):
        self.check_values('int i=0; int j=0; int total=0; while(i<3) { j=0; while(j<2) { total=total+1; j=j+1; } i=i+1; }',{'total':6,'i':3,'j':2})

    def test_while_zero_iterations(self):
        self.check_values('int x=4; while(0) { x=99; } int y=x+1;',{'x':4,'y':5})

    def test_if_else_both_outcomes_and_join(self):
        for flag,expected in ((0,9),(1,4)):
            with self.subTest(flag=flag):
                self.check_values(f'int flag={flag}; int x=0; if(flag) {{ x=3; }} else {{ x=8; }} int y=x+1;',{'y':expected})

    def test_nearest_if_owns_else(self):
        self.check_values('int x=0; if(1) if(0) x=2; else x=3;',{'x':3})

    def test_if_without_else_and_empty_body(self):
        self.check_values('int x=0; if(0) x=8; if(1) ; while(0); x=x+1;',{'x':1})

    def test_shadowing_has_separate_storage(self):
        files = self.check_values('int x=10; { int x=3; x=x+1; } int y=x;',{'x':10,'x@S1':4,'y':10})
        self.assertIn('x\tint\t1\t1\tx@S1',files['symbols.tsv'])

    def test_shadowing_begins_at_declaration(self):
        self.check_values('int x=1; { x=2; int x=3; x=x+1; } int y=x;',{'x':2,'x@S1':4,'y':2})

    def test_sibling_scopes_can_reuse_names(self):
        self.check_values('{int x=1;} {int x=2;}',{'x@S1':1,'x@S2':2})

    def test_out_of_scope_and_duplicate_rejected(self):
        for source in ('{int x=1;} x=2;','if(1) {int x=1;} else {x=2;}','int x; int x;'):
            with self.subTest(source=source):
                result,_ = self.compile(source,1)
                self.assertIn('Semantic error',result.stderr)

    def test_declaration_after_use_rejected_in_inner_scope(self):
        result,_ = self.compile('{x=2; int x;}',1)
        self.assertIn('line 1',result.stderr)

    def test_boolean_assignment_and_precedence(self):
        self.check_values('int a=0; int b=2; int x=(a || b) && !a; int y=1+2*3>=7 && 2!=3; int z=!(1<2);',{'x':1,'y':1,'z':0})

    def test_and_or_short_circuit(self):
        self.check_values('int zero=0; int x=0; if(0 && 10/zero) {x=5;} else {x=1;} if(1 || 10/zero) {x=x+1;} int y=0 && 10/zero;',{'x':2,'y':0})

    def test_comparisons(self):
        self.check_values('int a=1<2; int b=2<=2; int c=3>2; int d=3>=3; int e=2==2; int f=2!=2;',{'a':1,'b':1,'c':1,'d':1,'e':1,'f':0})

    def test_unary_long_operand_and_float_loop(self):
        self.check_values('int longvariablename=12; int x=-longvariablename; int y=-123456789; float z=.5; while(z<2.0){z=z+.5;}',{'x':-12,'y':-123456789,'z':2})

    def test_errors_in_loop_body_and_syntax(self):
        for source in ('int i=0; while(i<2){i=missing;}','int i=0; while(i<){i=i+1;}','int x; if(1) int y;'):
            with self.subTest(source=source):
                self.compile(source,1)

    def test_optimizer_does_not_propagate_preloop_value_past_loop(self):
        files = self.check_values('int i=0; while(i<3){i=i+1;} int result=i;',{'i':3,'result':3})
        self.assertIn('result = i',files['optimized_tac.txt'])

    def test_algebraic_simplifications_remain_available(self):
        files = self.check_values('int x=0; while(x<2){x=x+1;} int y=x+0; int z=y*1;',{'x':2,'y':2,'z':2})
        self.assertNotIn(' + 0',files['optimized_tac.txt'])
        self.assertNotIn(' * 1',files['optimized_tac.txt'])

    def test_constant_folding_stays_available_in_blocks(self):
        files = self.check_values('int x=0; if(1){x=2+3*4;}',{'x':14})
        self.assertIn('x = 14',files['optimized_tac.txt'])


class FlowGraphTests(unittest.TestCase):
    def test_true_false_edges_and_cycle(self):
        graph = build_cfg('x = 1\nL1:\nifFalse x goto L2\ngoto L1\nL2:\n')
        self.assertIn(('B2','B4','false'),graph.edges)
        self.assertIn(('B2','B3','true'),graph.edges)
        self.assertIn(('B3','B2','jump'),graph.edges)
        positions,heights = layout_cfg(graph)
        self.assertEqual(set(positions),set(graph.nodes))
        self.assertEqual(len(set(positions.values())),len(positions))
        self.assertIn('label="false"',graph.to_dot())

    def test_empty_code_and_undefined_label(self):
        self.assertEqual(build_cfg('').edges,[('entry','exit','next')])
        with self.assertRaises(ValueError):
            build_cfg('goto L99')

    def test_pipeline_scope_records_and_source_mapping(self):
        result = run_lab(CONTROL_DEMO)
        self.assertTrue(all(x=='passed' for x in result.stages.values()))
        self.assertTrue(result.cfg)
        self.assertIn(['4','WHILE','while'],result.tokens)
        self.assertIn(('bonus','int','3','2','bonus@S3','8'),result.scope_symbols)
        while_node = next(key for key,label in result.nodes.items() if label=='While')
        self.assertEqual(result.node_lines[while_node],4)
        self.assertIn('condition',result.ast_edge_labels.values())
        self.assertIn('Declaration: i',result.nodes.values())
        self.assertIn('Operator: <',result.nodes.values())
        self.assertIn('Integer: 5',result.nodes.values())
        self.assertNotIn('left/type',result.nodes.values())
        self.assertTrue(any(a.startswith('B') and b.startswith('B') and int(b[1:])<int(a[1:]) for a,b,_ in result.cfg.edges))


if __name__=='__main__':
    unittest.main()

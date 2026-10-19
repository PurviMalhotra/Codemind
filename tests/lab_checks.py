"""Run with `make test-lab`; each test uses a separate artifact directory."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
lab = root / 'mini_compiler'
binary = lab / 'mini_compiler'
cases = [
    ('original example', (lab / 'example.src').read_text(), 0),
    ('valid test', (lab / 'tests/valid.src').read_text(), 0),
    ('syntax error', (lab / 'tests/invalid_syntax.src').read_text(), 1),
    ('semantic error', (lab / 'tests/invalid_semantic.src').read_text(), 1),
    ('declaration order', 'x = 1;\nint x;\n', 1),
    ('floating modulo', 'float x;\nx = 1 % 0.5;\n', 1),
    ('temporary name collision', 'int t1;\nint result;\nt1 = 3;\nresult = (2 + 1) * t1;\n', 0),
]
for name, source, expected in cases:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'input.src'
        path.write_text(source)
        result = subprocess.run([str(binary), str(path)], cwd=directory,
                                capture_output=True, text=True, timeout=10)
        if result.returncode != expected:
            raise AssertionError(f'{name}: {result.stdout}\n{result.stderr}')
        if expected == 0:
            for artifact in ('ast.dot', 'tac.txt', 'optimized_tac.txt'):
                if not (Path(directory) / artifact).exists():
                    raise AssertionError(f'{name}: missing {artifact}')
        if name == 'temporary name collision':
            if 'result = 9' not in (Path(directory) / 'optimized_tac.txt').read_text():
                raise AssertionError('Generated temporaries changed a user variable')
        print(f'PASS: {name}')
print(f'{len(cases)} lab checks passed')

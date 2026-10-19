import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codemind.engine import (AnalysisError, analyze, compare_reports, explain,
                             format_text, parse_diagnostics)


class CompilerIntegrationTests(unittest.TestCase):
    def check_rule(self, source, rule):
        report = analyze(source)
        self.assertIn(rule, [d.rule for d in report.diagnostics], report.raw_output)
        return report

    def test_slide_example_and_fixed_version(self):
        broken = 'int main(void) { int marks = 70; if (marks >= 50 { return 1; } return 0; }'
        report = self.check_rule(broken, 'missing-delimiter')
        fixed = analyze(broken.replace('50 {', '50) {'))
        self.assertFalse(report.success)
        self.assertTrue(fixed.success)
        self.assertIn('Current check: 0 error(s)', compare_reports(report, fixed))

    def test_main_return_type_and_screenshot_example(self):
        broken = '#include <stdio.h>\n\nvoid main(void) {\n int marks = 70;\n if (marks >= 50 {\n printf("Passed\\n");\n }\n return 0;\n}\n'
        report = self.check_rule(broken, 'main-return-type')
        item = next(d for d in report.diagnostics if d.rule == 'main-return-type')
        self.assertEqual(item.category, 'Semantic')
        self.assertEqual(item.line, 3)
        self.assertIn('int main(void)', item.suggestion)
        self.assertIn('missing-delimiter', [d.rule for d in report.diagnostics])
        fixed = broken.replace('void main(void)', 'int main(void)').replace('50 {', '50) {')
        self.assertTrue(analyze(fixed).success)

    def test_missing_semicolon(self):
        self.check_rule('int main(void) {\n int x = 2\n return x;\n}', 'missing-semicolon')

    def test_undeclared_name(self):
        self.check_rule('int main(void) { return score; }', 'undeclared-name')

    def test_function_header(self):
        self.check_rule('int main(void) { printf("hello"); return 0; }', 'missing-function-declaration')

    def test_unterminated_string(self):
        self.check_rule('int main(void) { char *s = "hello;\nreturn 0; }', 'unterminated-literal')

    def test_unterminated_comment(self):
        self.check_rule('int main(void) { /* no closing comment', 'unterminated-comment')

    def test_invalid_token(self):
        self.check_rule('int main(void) { return 12abc; }', 'invalid-token')

    def test_duplicate(self):
        report = self.check_rule('int main(void) { int x = 1; int x = 2; return x; }', 'duplicate-declaration')
        self.assertTrue(any(d.notes for d in report.diagnostics))

    def test_unknown_type(self):
        self.check_rule('int twice(integer x) { return x * 2; }', 'unknown-type')

    def test_zero_divisor(self):
        self.check_rule('int main(void) { return 4 / 0; }', 'zero-divisor')

    def test_format(self):
        self.check_rule('#include <stdio.h>\nint main(void) { printf("%d", 1.5); return 0; }', 'format-mismatch')

    def test_uninitialized(self):
        self.check_rule('int main(void) { int x; return x; }', 'uninitialized-value')

    def test_unused_warning_is_not_failure(self):
        report = self.check_rule('int main(void) { int x = 1; return 0; }', 'unused-name')
        self.assertTrue(report.success)
        self.assertGreater(report.warnings, 0)

    def test_argument_count(self):
        self.check_rule('int add(int x, int y); int main(void) { return add(1); }', 'argument-count')

    def test_type_mismatch(self):
        self.check_rule('int main(void) { int *p = 7; return *p; }', 'type-mismatch')

    def test_missing_header(self):
        self.check_rule('#include "codemind_nonexistent.h"\n', 'missing-header')

    def test_quoted_local_header(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'values.h').write_text('#define VALUE 7\n')
            report = analyze('#include "values.h"\nint main(void) { return VALUE; }', include_dir=directory)
            self.assertTrue(report.success, report.raw_output)

    def test_never_executes_c_program(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'executed.txt'
            source = '#include <stdio.h>\nint main(void) { fopen("' + str(marker) + '", "w"); return 0; }'
            self.assertTrue(analyze(source).success)
            self.assertFalse(marker.exists())

    def test_cli_json_and_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.c'
            path.write_text('int main(void) { return missing; }')
            result = subprocess.run([sys.executable, '-m', 'codemind', str(path), '--json'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            data = json.loads(result.stdout)
            self.assertFalse(data['success'])
            self.assertEqual(data['diagnostics'][0]['file'], str(path))
            self.assertNotIn('codemind-', data['raw_output'])


class ParserTests(unittest.TestCase):
    def test_gcc_quotes_optional_column_and_deduplication(self):
        text = '/tmp/input.c:2: error: expected ‘;’ before ‘return’\n' * 2
        result = parse_diagnostics(text, 'int x\nreturn 0;', '/tmp/input.c', 'student.c')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rule, 'missing-semicolon')
        self.assertEqual(result[0].column, 0)

    def test_header_location_does_not_show_wrong_source(self):
        text = '/tmp/header.h:1:3: error: unknown type name foo\n'
        result = parse_diagnostics(text, 'int main(void) {}', '/tmp/input.c', 'student.c')
        self.assertEqual(result[0].source, '')
        self.assertEqual(result[0].file, '/tmp/header.h')

    def test_global_fatal_diagnostic(self):
        result = parse_diagnostics('cc1: fatal error: compiler setup failed', '', '/tmp/input.c', 'student.c')
        self.assertEqual(result[0].severity, 'fatal error')

    def test_main_return_type_compiler_wording(self):
        for message in ("'main' must return 'int'", "return type of ‘main’ is not ‘int’ [-Wmain]", "return type of 'main' is not int"):
            with self.subTest(message=message):
                self.assertEqual(explain(message)[1], 'main-return-type')
        self.assertEqual(explain("unused variable 'main'")[1], 'unused-name')

    def test_unknown_message_stays_honest(self):
        self.assertEqual(explain('some new compiler message')[1], 'compiler-message')

    def test_input_and_infrastructure_errors(self):
        with self.assertRaises(AnalysisError):
            analyze('int x;', compiler='codemind_missing_compiler_1234')
        with self.assertRaises(AnalysisError):
            analyze('\x00')
        with self.assertRaises(AnalysisError):
            analyze('int x;', standard='c90')
        with patch('codemind.engine.subprocess.run', side_effect=subprocess.TimeoutExpired('cc', 15)):
            with self.assertRaises(AnalysisError):
                analyze('int x;')


if __name__ == '__main__':
    unittest.main()

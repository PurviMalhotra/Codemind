import unittest
from unittest.mock import patch

from codemind.corrections import apply_fixit, suggestions
from codemind.engine import FixIt, analyze, parse_fixits
from codemind.lab import DEMO, LabError, graph_from_dot, layout_graph, run_lab
from codemind.syntax import spans


class CorrectionTests(unittest.TestCase):
    def test_compiler_edit_for_missing_semicolon(self):
        source = 'int main(void) {\n int age = 18\n return age;\n}\n'
        report = analyze(source)
        choices = suggestions(source, report)
        self.assertTrue(any(analyze(choice.source).success for choice in choices), report.raw_output)
        self.assertEqual(source.splitlines()[1], ' int age = 18')

    def test_missing_parenthesis_rule_and_check(self):
        source = 'int main(void) { int marks=70; if (marks >= 50 { return 1; } return 0; }'
        choices = suggestions(source, analyze(source))
        self.assertTrue(any(analyze(choice.source).success for choice in choices))

    def test_main_edit_and_remaining_error(self):
        source = 'void main(void) { int marks=70; if (marks >= 50 { return 1; } return 0; }'
        report = analyze(source)
        main_edits = [choice for choice in suggestions(source, report) if choice.source.startswith('int main')]
        self.assertTrue(main_edits)
        checked = analyze(main_edits[0].source)
        self.assertNotIn('main-return-type', [d.rule for d in checked.diagnostics])
        self.assertIn('missing-delimiter', [d.rule for d in checked.diagnostics])

    def test_byte_columns_after_unicode(self):
        source = '/* é */ int x\n'
        col = len('/* é */ int x'.encode('utf-8')) + 1
        edit = FixIt('program.c', 1, col, 1, col, ';')
        self.assertEqual(apply_fixit(source, edit), '/* é */ int x;\n')
        with self.assertRaises(ValueError):
            apply_fixit(source, FixIt('program.c', 99, 1, 99, 1, ';'))

    def test_fixits_skip_other_files_and_decode_escaped_replacement(self):
        raw = 'fix-it:"/tmp/input.c":{1:1-1:1}:"\\\"hello\\\""\nfix-it:"/tmp/header.h":{1:1-1:1}:";"'
        fixes = parse_fixits(raw, '/tmp/input.c', 'student.c')
        self.assertEqual(len(fixes), 1)
        self.assertEqual(fixes[0].replacement, '"hello"')

    def test_fallback_to_manual_for_undeclared_name(self):
        source = 'int main(void) { return unknown; }'
        self.assertEqual(suggestions(source, analyze(source)), [])


class ColourTests(unittest.TestCase):
    def test_strings_and_comments_do_not_colour_keywords(self):
        source = 'int n = 12; // return 3\nchar *s = "float 4";\n'
        tokens = [(kind, source[a:b]) for kind,a,b in spans(source)]
        self.assertIn(('keyword','int'), tokens)
        self.assertIn(('number','12'), tokens)
        self.assertIn(('comment','// return 3'), tokens)
        self.assertIn(('string','"float 4"'), tokens)
        self.assertNotIn(('keyword','float'), tokens)

    def test_multiline_comments_and_escaped_quote(self):
        source = '/* int\n return */ const char *s="a\\\"b";'
        tokens = [(kind, source[a:b]) for kind,a,b in spans(source)]
        self.assertIn(('comment','/* int\n return */'), tokens)
        self.assertIn(('keyword','const'), tokens)
        self.assertIn(('string','"a\\\"b"'), tokens)


class PipelineTests(unittest.TestCase):
    def test_real_artifacts(self):
        result = run_lab(DEMO)
        self.assertTrue(all(s == 'passed' for s in result.stages.values()))
        self.assertIn(['1','INT','int'], result.tokens)
        self.assertIn(('result','float'), result.symbols)
        self.assertIn('Program',result.nodes.values())
        self.assertIn('$t', result.tac)
        self.assertIn('result = 10.5', result.optimized)
        positions = layout_graph(result.nodes,result.edges)
        self.assertEqual(set(positions),set(result.nodes))
        self.assertEqual(len(set(positions.values())),len(positions))

    def test_syntax_failure_skips_later_stages(self):
        result = run_lab('int a;\na = 3 + ;\n')
        self.assertEqual(result.stages['tokens'],'passed')
        self.assertEqual(result.stages['ast'],'failed')
        self.assertEqual(result.stages['symbols'],'skipped')
        self.assertFalse(result.nodes)
        self.assertFalse(result.tac)

    def test_lexical_failure(self):
        result = run_lab('int a;\na = @;\n')
        self.assertEqual(result.stages['tokens'],'failed')
        self.assertEqual(result.stages['ast'],'skipped')

    def test_semantic_failure_keeps_ast_but_skips_code(self):
        result = run_lab('int a;\na = missing + 2;\n')
        self.assertEqual(result.stages['ast'],'passed')
        self.assertEqual(result.stages['symbols'],'failed')
        self.assertEqual(result.stages['tac'],'skipped')
        self.assertTrue(result.nodes)
        self.assertFalse(result.optimized)

    def test_missing_tools_are_actionable(self):
        with patch('codemind.lab.shutil.which',return_value=None):
            with self.assertRaisesRegex(LabError,'needs make'):
                run_lab(DEMO)


if __name__ == '__main__':
    unittest.main()

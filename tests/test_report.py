import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from what_changed.cli import main
from what_changed.compare import compare
from what_changed.render import render, word_diff


class ReportTests(unittest.TestCase):
    def test_untrusted_html_escaped(self):
        report = compare('## Rent\nOld text.', '## Rent\n<script>alert(1)</script> @@EDITS@@')
        html = render(report)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('@@EDITS@@', html)

    def test_word_diff_marks_only_edits(self):
        old, new = word_diff('Pay 30 days.', 'Pay 60 days.')
        self.assertIn('<del>30</del>', old)
        self.assertIn('<ins>60</ins>', new)

    def test_report_does_not_load_remote_resources(self):
        html = render(compare('Old.', 'New.'))
        self.assertNotIn('<script src=', html)
        self.assertNotIn('<link ', html)
        self.assertIn("connect-src 'none'", html)

    def test_cli_writes_both_reports_and_hashes(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['samples/before.md','samples/after.md','--out',folder]), 0)
            report = json.loads((Path(folder)/'report.json').read_text())
            self.assertEqual(len(report['documents']['old']['sha256']), 64)
            self.assertTrue((Path(folder)/'index.html').is_file())

    @patch.dict(os.environ, {}, clear=True)
    def test_live_failure_preserves_local_report_and_sets_exit_code(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['samples/before.md','samples/after.md','--out',folder,'--live']), 2)
            report = json.loads((Path(folder)/'report.json').read_text())
            self.assertEqual(report['review']['mode'], 'failed')
            self.assertGreater(len(report['changes']), 0)

    def test_input_cannot_be_overwritten_by_report(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            source = Path(folder)/'index.html'
            source.write_text('Original text.')
            with self.assertRaises(SystemExit):
                main([str(source),'samples/after.md','--out',folder])
            self.assertEqual(source.read_text(), 'Original text.')


if __name__ == '__main__':
    unittest.main()

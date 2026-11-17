import json
import os
import unittest
from unittest.mock import patch, MagicMock

from what_changed.compare import compare
from what_changed.review import review, validate_notes


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.changes = compare('## Rent\nMonthly $100.', '## Rent\nMonthly $125.')['changes']
        self.note = {'change_id':'change-1', 'old_quote':'Monthly $100.', 'new_quote':'Monthly $125.',
                     'explanation':'The monthly amount increased.', 'question':'When would this start?'}

    def test_exact_quotes_accepted(self):
        self.assertEqual(len(validate_notes({'notes':[self.note]}, self.changes)['notes']), 1)

    def test_hallucinated_quote_rejected(self):
        self.note['new_quote'] = 'Monthly $150.'
        result = validate_notes({'notes':[self.note]}, self.changes)
        self.assertEqual(len(result['rejected']), 1)
        self.assertEqual(result['notes'], [])

    def test_whitespace_quote_rejected(self):
        self.note['new_quote'] = ' '
        self.assertEqual(validate_notes({'notes':[self.note]}, self.changes)['notes'], [])

    def test_wrong_clause_id_and_bad_type_rejected(self):
        for value in ('unknown', ['change-1']):
            self.note['change_id'] = value
            self.assertEqual(len(validate_notes({'notes':[self.note]}, self.changes)['rejected']), 1)

    def test_duplicate_note_rejected(self):
        result = validate_notes({'notes':[self.note, self.note]}, self.changes)
        self.assertEqual((len(result['notes']),len(result['rejected'])), (1,1))

    def test_added_clause_missing_side_requires_empty_quote(self):
        changes = compare('## Rent\nMonthly $100.', '## Rent\nMonthly $100.\n## Fee\nMonthly $12.')['changes']
        self.note.update(change_id='change-2', old_quote='', new_quote='Monthly $12.')
        self.assertEqual(len(validate_notes({'notes':[self.note]}, changes)['notes']), 1)

    def test_wrong_shape(self):
        for payload in ([], {}, {'notes':None}):
            with self.assertRaises(ValueError):
                validate_notes(payload, self.changes)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_explicit(self):
        with self.assertRaises(RuntimeError):
            review(self.changes)

    @patch('what_changed.review.urllib.request.urlopen')
    @patch.dict(os.environ, {'OPENAI_API_KEY':'test-not-a-key', 'OPENAI_MODEL':'test-model'})
    def test_live_adapter_passes_through_quote_validator(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({'choices':[{'message':{'content':json.dumps({'notes':[self.note]})}}], 'usage':{'total_tokens':120}}).encode()
        urlopen.return_value.__enter__.return_value = response
        result = review(self.changes)
        self.assertEqual(result['usage']['total_tokens'], 120)
        self.assertEqual(len(result['notes']), 1)
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(json.loads(request.data)['max_completion_tokens'], 4000)

    @patch('what_changed.review.urllib.request.urlopen')
    def test_unchanged_input_does_not_call_provider(self, urlopen):
        result = review(compare('Same text.', 'Same text.')['changes'])
        self.assertEqual(result['requested'], 0)
        urlopen.assert_not_called()


if __name__ == '__main__':
    unittest.main()

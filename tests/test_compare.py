from pathlib import Path
import unittest

from what_changed.compare import compare, money_fact, parse, price_change


class ClauseTests(unittest.TestCase):
    def test_heading_line_numbers_point_to_original_text(self):
        clauses = parse('# Title\n\nIntro.\n\n## Rent\nMonthly $100.\n', 'old')
        self.assertEqual((clauses[1].title, clauses[1].start_line, clauses[1].end_line), ('Rent', 5, 6))

    def test_numbered_headings(self):
        self.assertEqual(parse('1. Rent\nPay monthly.\n2. Pets\nOne cat.', 'old')[1].title, 'Pets')

    def test_plain_paragraphs(self):
        self.assertEqual(len(parse('First clause.\n\nSecond clause.', 'old')), 2)

    def test_empty_binary_large_inputs(self):
        for text in (' ', 'abc\x00', 'a' * 250001, '# Empty heading'):
            with self.subTest(text=text[:20]), self.assertRaises(ValueError):
                parse(text, 'old')

    def test_identical_input(self):
        result = compare('## Rent\nMonthly $100.', '## Rent\nMonthly $100.')
        self.assertEqual(result['counts'], {'unchanged': 1})

    def test_whitespace_only_edit_ignored(self):
        result = compare('## Rent\nPay  monthly.', '## Rent\nPay monthly.')
        self.assertEqual(result['counts'], {'unchanged': 1})

    def test_insertion_does_not_mark_later_clauses_as_moved(self):
        result = compare('## A\nApple.\n## B\nBanana.', '## New\nCherry.\n## A\nApple.\n## B\nBanana.')
        self.assertEqual(result['counts'], {'added': 1, 'unchanged': 2})

    def test_reorder_is_distinct_from_wording_change(self):
        result = compare('## A\nApple.\n## B\nBanana.', '## B\nBanana.\n## A\nApple.')
        self.assertEqual(result['counts'], {'moved': 1, 'unchanged': 1})

    def test_renamed_heading_keeps_same_clause(self):
        result = compare('## Parking\nOne space.', '## Vehicle space\nOne space.')
        self.assertTrue(result['changes'][0]['renamed'])
        self.assertEqual(result['changes'][0]['match'], 'exact text')

    def test_duplicate_titles_do_not_overwrite_clauses(self):
        result = compare('## Fee\nMonthly $10.\n## Fee\nMonthly $20.',
                         '## Fee\nMonthly $20.\n## Fee\nMonthly $10.')
        self.assertEqual(len(result['changes']), 2)
        self.assertEqual(len({c['old']['id'] for c in result['changes']}), 2)

    def test_unmatched_text_is_added_and_removed(self):
        result = compare('## Storage\nUse the locker.', '## Swimming\nPool hours vary.')
        self.assertEqual(result['counts'], {'added': 1, 'removed': 1})

    def test_sample_expected_changes(self):
        result = compare(Path('samples/before.md').read_text(), Path('samples/after.md').read_text())
        self.assertEqual(result['counts'], {'unchanged':1, 'changed':5, 'moved':1, 'added':1, 'removed':1})
        rent = next(c for c in result['changes'] if c['title'] == 'Rent')
        self.assertEqual(rent['price']['delta'], '125.00')
        self.assertEqual(rent['price']['annualized_delta'], '1500.00')
        parking = next(c for c in result['changes'] if c['title'] == 'Parking')
        self.assertIsNone(parking['price'])


class ArithmeticTests(unittest.TestCase):
    def test_comma_after_amount_is_punctuation(self):
        self.assertEqual(str(money_fact('Monthly $1,450.00, due first.')['amount']), '1450.00')

    def test_decimal_arithmetic(self):
        self.assertEqual(price_change('Monthly $0.10.', 'Monthly $0.30.')['delta'], '0.20')

    def test_reject_ambiguous_prices_or_periods(self):
        for text in ('Monthly $100 plus $5.', 'Monthly $100 or annual $900.', '$100.', 'Monthly $1,20.', 'Monthly $10.5.'):
            with self.subTest(text=text):
                self.assertIsNone(money_fact(text))

    def test_do_not_compare_different_frequencies(self):
        self.assertIsNone(price_change('Monthly $10.', 'Annual $120.'))

    def test_added_and_removed_prices(self):
        self.assertEqual(price_change('', 'Monthly $12.')['annualized_delta'], '144.00')
        self.assertEqual(price_change('Monthly $12.', '')['delta'], '-12.00')

    def test_once_does_not_annualize(self):
        self.assertIsNone(price_change('One-time $25.', 'One-time $50.')['annualized_delta'])

    def test_do_not_guess_zero_when_price_missing(self):
        self.assertIsNone(price_change('Parking is included.', 'Monthly $65.'))

    def test_equal_price_no_delta(self):
        self.assertIsNone(price_change('Monthly $20.', 'Monthly $20 due first.'))

    def test_day_changes_are_literal(self):
        change = compare('## Notice\nGive 30 days notice.', '## Notice\nGive 60 days notice.')['changes'][0]
        self.assertEqual(change['day_values'], {'before':['30 days'],'after':['60 days']})


if __name__ == '__main__':
    unittest.main()

"""Clause alignment and small, deliberately conservative arithmetic checks."""
from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal
from difflib import SequenceMatcher
import re

HEADING = re.compile(r"^\s*(?:#{1,6}\s+(.+?)\s*#*|\d+[.)]\s+(.+))\s*$")
MONEY = re.compile(r"(?:\$\s*|\bUSD\s+)(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?)(?!\d|\.\d|,\d)", re.I)


def normalize(text):
    return ' '.join(text.casefold().split())


@dataclass
class Clause:
    id: str
    title: str
    text: str
    start_line: int
    end_line: int


def parse(text, version):
    if not text.strip():
        raise ValueError(f'{version} document is empty')
    if len(text) > 250_000:
        raise ValueError('Documents must be at most 250,000 characters each')
    if '\x00' in text:
        raise ValueError('Expected UTF-8 text, not a binary document')
    clauses = []
    title, body, start = 'Preamble', [], 1

    def append(end):
        value = '\n'.join(body).strip()
        if value:
            clauses.append(Clause(f'{version}-{len(clauses)+1}', title, value, start, end))

    lines = text.splitlines()
    has_headings = any(HEADING.match(line) for line in lines)
    for i, line in enumerate(lines, 1):
        heading = HEADING.match(line)
        if heading:
            append(i-1)
            title = (heading.group(1) or heading.group(2)).strip()
            body, start = [], i
        elif not has_headings and not line.strip():
            append(i-1)
            title, body, start = f'Paragraph {len(clauses)+1}', [], i+1
        else:
            body.append(line)
    append(len(lines))
    if not clauses:
        raise ValueError('No clause text found under the headings')
    if len(clauses) > 200:
        raise ValueError('At most 200 clauses per document are supported')
    return clauses


def similarity(a, b):
    left, right = set(re.findall(r'\w+', normalize(a))), set(re.findall(r'\w+', normalize(b)))
    return len(left & right) / len(left | right) if left | right else 0


def align(old, new):
    """Unique headings first, then exact bodies, then conservative token overlap."""
    pairs = {}
    used = set()
    old_titles = Counter(normalize(c.title) for c in old)
    new_titles = Counter(normalize(c.title) for c in new)
    for j, clause in enumerate(new):
        key = normalize(clause.title)
        # Paragraph labels are positions, not stable identities.
        if key.startswith('paragraph ') or key == 'preamble':
            continue
        if old_titles[key] == new_titles[key] == 1:
            i = next(i for i, c in enumerate(old) if normalize(c.title) == key)
            pairs[j] = (i, 'heading')
            used.add(i)
    for j, clause in enumerate(new):
        if j in pairs:
            continue
        matches = [i for i, c in enumerate(old) if i not in used and normalize(c.text) == normalize(clause.text)]
        if matches:
            i = min(matches, key=lambda i: abs(i-j))
            pairs[j] = (i, 'exact text')
            used.add(i)
    candidates = []
    for j, right in enumerate(new):
        if j not in pairs:
            for i, left in enumerate(old):
                if i not in used:
                    score = similarity(left.text, right.text)
                    if score >= .65:
                        candidates.append((score, -abs(i-j), i, j))
    for score, _, i, j in sorted(candidates, reverse=True):
        if j not in pairs and i not in used:
            pairs[j] = (i, f'text overlap {score:.0%}; check this match')
            used.add(i)
    return pairs


def money_fact(text):
    amounts = list(MONEY.finditer(text))
    if len(amounts) != 1:
        return None
    monthly = bool(re.search(r'\b(?:monthly|per month|each month)\b', text, re.I))
    annual = bool(re.search(r'\b(?:annual|annually|yearly|per year|each year)\b', text, re.I))
    once = bool(re.search(r'\bone[- ]time\b', text, re.I))
    if sum((monthly, annual, once)) != 1:
        return None
    amount = Decimal(amounts[0].group(1).replace(',', ''))
    if amount >= Decimal('1000000000000'):
        return None
    return {'amount': amount,
            'basis': 'month' if monthly else 'year' if annual else 'one-time'}


def price_change(before, after):
    left, right = money_fact(before) if before else None, money_fact(after) if after else None
    if before and not left or after and not right:
        return None
    if not left and not right:
        return None
    if left and right and left['basis'] != right['basis']:
        return None
    basis = (right or left)['basis']
    delta = (right['amount'] if right else Decimal(0)) - (left['amount'] if left else Decimal(0))
    if delta == 0:
        return None
    return {'before': str(left['amount']) if left else None,
            'after': str(right['amount']) if right else None,
            'delta': f'{delta:.2f}', 'basis': basis,
            'annualized_delta': f'{delta * 12:.2f}' if basis == 'month' else None,
            'assumption': 'Treats the single dollar amount as the clause price; check the quoted clause. Monthly annualization assumes 12 payments.'}


def compare(old_text, new_text):
    old, new = parse(old_text, 'old'), parse(new_text, 'new')
    pairs = align(old, new)
    ordered = [pairs[j][0] for j in sorted(pairs)]
    stable = set()
    for block in SequenceMatcher(None, sorted(ordered), ordered, autojunk=False).get_matching_blocks():
        stable.update(ordered[block.b:block.b+block.size])
    changes = []
    used = set()
    for j, right in enumerate(new):
        if j in pairs:
            i, method = pairs[j]
            used.add(i)
            left = old[i]
            text_changed = normalize(left.text) != normalize(right.text)
            renamed = normalize(left.title) != normalize(right.title)
            moved = i not in stable
            status = 'changed' if text_changed or renamed else 'moved' if moved else 'unchanged'
        else:
            left, method, moved, renamed, status = None, 'new clause', False, False, 'added'
        changes.append(make_change(left, right, status, method, moved, renamed))
    for i, left in enumerate(old):
        if i not in used:
            changes.append(make_change(left, None, 'removed', 'unmatched old clause', False, False))
    for index, change in enumerate(changes, 1):
        change['id'] = f'change-{index}'
    return {'schema_version': 1, 'changes': changes,
            'counts': dict(Counter(c['status'] for c in changes)),
            'review': {'mode': 'off', 'notes': [], 'rejected': []}}


def make_change(left, right, status, method, moved, renamed):
    before, after = left.text if left else '', right.text if right else ''
    old_days = re.findall(r'\b\d+\s+days?\b', before, re.I)
    new_days = re.findall(r'\b\d+\s+days?\b', after, re.I)
    return {'id': '', 'title': (right or left).title, 'status': status,
            'old': asdict(left) if left else None, 'new': asdict(right) if right else None,
            'match': method, 'moved': moved, 'renamed': renamed,
            'price': price_change(before, after) if status in {'added','removed','changed'} else None,
            'day_values': {'before': old_days, 'after': new_days} if old_days != new_days else None}

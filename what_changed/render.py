"""Portable HTML report. Document text is always escaped before insertion."""
from difflib import SequenceMatcher
from html import escape
from importlib.resources import files
import re


def word_diff(before, after):
    left, right = re.split(r'(\s+)', before), re.split(r'(\s+)', after)
    old, new = [], []
    for op, a, b, c, d in SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        old_text, new_text = escape(''.join(left[a:b])), escape(''.join(right[c:d]))
        old.append(f'<del>{old_text}</del>' if op in {'delete','replace'} else old_text)
        new.append(f'<ins>{new_text}</ins>' if op in {'insert','replace'} else new_text)
    return ''.join(old), ''.join(new)


def side(clause, text, label):
    if clause is None:
        return f'<section class="version empty"><h3>{label}</h3><p>This clause is absent.</p></section>'
    location = f"Lines {clause['start_line']}–{clause['end_line']}"
    return f'<section class="version"><h3>{label} <span>{location}</span></h3><p class="clause">{text}</p></section>'


def render(report):
    changes = report['changes']
    review = report['review']
    notes = {n['change_id']: n for n in review.get('notes', [])}
    cards = []
    for change in changes:
        before = change['old']['text'] if change['old'] else ''
        after = change['new']['text'] if change['new'] else ''
        old_html, new_html = word_diff(before, after)
        badges = []
        price = change.get('price')
        if price:
            delta = float(price['delta'])
            badges.append(f'<span class="fact">{"+" if delta > 0 else "−"}${abs(delta):,.2f} / {escape(price["basis"])}</span>')
            if price['annualized_delta']:
                value = float(price['annualized_delta'])
                badges.append(f'<span class="fact quiet">{"+" if value > 0 else "−"}${abs(value):,.2f} over 12 payments</span>')
        days = change.get('day_values')
        if days:
            label = f'{", ".join(days["before"]) or "none"} → {", ".join(days["after"]) or "none"}'
            badges.append(f'<span class="fact">{escape(label)}</span>')
        if change['moved']:
            badges.append('<span class="fact quiet">Position changed</span>')
        note_html = ''
        if change['id'] in notes:
            note = notes[change['id']]
            note_html = f'''<aside class="note"><h3>Model explanation · source quotes checked</h3>
                <p>{escape(note['explanation'])}</p><p class="question">Ask: {escape(note['question'])}</p>
                <details><summary>Quotes supplied by the model</summary><blockquote>{escape(note['old_quote'])}</blockquote><blockquote>{escape(note['new_quote'])}</blockquote></details></aside>'''
        assumption = f'<p class="assumption">{escape(price["assumption"])}</p>' if price else ''
        hidden = ' hidden' if change['status'] == 'unchanged' else ''
        cards.append(f'''<article class="change" data-status="{change['status']}" id="{change['id']}"{hidden}>
          <div class="card-heading"><div><span class="status {change['status']}">{change['status']}</span>
          <h2>{escape(change['title'])}</h2></div><label class="reviewed"><input type="checkbox"> Reviewed</label></div>
          <div class="facts">{''.join(badges)}</div>
          <div class="versions">{side(change['old'], old_html, 'Before')}{side(change['new'], new_html, 'After')}</div>
          {assumption}{note_html}
          <details class="match"><summary>How these clauses were matched</summary><p>{escape(change['match'])}</p></details>
        </article>''')
    counts = report['counts']
    edits = sum(n for status, n in counts.items() if status != 'unchanged')
    price_count = sum(c['price'] is not None for c in changes)
    documents = report.get('documents', {})
    old_name = escape(documents.get('old', {}).get('name', 'Before'))
    new_name = escape(documents.get('new', {}).get('name', 'After'))
    if review['mode'] == 'off':
        mode = 'Local comparison. Model explanations are off; no documents were sent.'
    elif review['mode'] == 'failed':
        mode = 'Model review failed. This report still contains the local comparison.'
    else:
        mode = f"Model review: {len(notes)} explanations kept; {len(review.get('rejected', []))} rejected. Quote checks do not verify the explanation itself."
    template = files('what_changed').joinpath('report.html').read_text(encoding='utf-8')
    replacements = {'MODE':escape(mode), 'OLD':old_name, 'NEW':new_name, 'EDITS':str(edits),
                    'PRICES':str(price_count), 'UNCHANGED':str(counts.get('unchanged', 0)), 'CARDS':''.join(cards)}
    # Single-pass substitution prevents user content that resembles a placeholder from being evaluated.
    return re.sub(r'@@([A-Z]+)@@', lambda match: replacements[match.group(1)], template)

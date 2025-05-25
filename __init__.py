from aqt import mw, gui_hooks
from aqt.qt import QAction
from aqt.utils import tooltip
from .data import (
	get_word_data,
	get_frequency_weight,
	get_total_frequency_mass,
)
import math

_last_retrievabilities = {}

def on_update_all():
	cnt = 0
	col = mw.col
	for nid in col.find_notes("note:chinese-word"):
		note = col.get_note(nid)
		word = note['word']
		hsk, defs, pinyin, freq_rank, freq_weight = get_word_data(word)
		freq_weight = freq_weight or 0.0000000001
		hsk_str = str(hsk or '')
		defs_str = defs or ''
		pin_str = pinyin or ''
		if not defs_str or not pin_str:
			continue
		freq_rank_str = str(freq_rank or '')
		freq_weight_str = f'1 / {readable_number(1 / freq_weight)}'
		if not (
			note['hsk'] == hsk_str and
			note['definition'] == defs_str and
			note['freq-rank'] == freq_rank_str and
			note['freq-weight'] == freq_weight_str and
			note['pinyin'] == pin_str
		):
			note['pinyin'] = pin_str
			note['freq-rank'] = freq_rank_str
			note['freq-weight'] = freq_weight_str
			note['definition'] = defs_str
			note['hsk'] = hsk_str
			col.update_note(note)
			cnt += 1
			if cnt % 100 == 0:
				print(f'updated {cnt} chinese notes')
	tooltip(f"Updated {cnt} notes")

def on_info():
	col = mw.col
	known = {}
	for cid in col.find_cards("note:chinese-word card:hanzi-define -is:suspended (is:learn OR is:review)"):
		card = col.get_card(cid)
		note = card.note()
		stats = mw.col.card_stats_data(card.id)
		r = stats.fsrs_retrievability
		known[note['word']] = r

	total_mass     = get_total_frequency_mass()
	basic_mass     = sum(get_frequency_weight(w) or 0 for w in known)
	retrieval_mass = sum((get_frequency_weight(w) or 0) * r for w, r in known.items())

	basic_perc     = (basic_mass     / total_mass * 100) if total_mass else 0
	retrieval_perc = (retrieval_mass / total_mass * 100) if total_mass else 0

	tooltip(
		f"Basic estimated comprehension: {basic_perc:.4f}%<br>Retrievability-weighted: {retrieval_perc:.4f}%<br>Based on {len(known)} words"
	)

def on_card_will_show(card):
	if card.note_type()['name'] != "chinese-word":
		return
	stats = mw.col.card_stats_data(card.id)
	r_before = getattr(stats, 'fsrs_retrievability', 0.0)
	_last_retrievabilities[card.id] = r_before


def on_card_reviewed(reviewer, card, ease):
	if card.note_type()['name'] != "chinese-word":
		return
	note = card.note()
	word = note['word']
	freq_weight = get_frequency_weight(word) or 0
	stats = mw.col.card_stats_data(card.id)
	r_after = getattr(stats, 'fsrs_retrievability', 0.0)

	global _last_retrievabilities
	r_before = _last_retrievabilities.get(card.id, 0.0)
	_last_retrievabilities[card.id] = r_after

	if r_before == 0:
		return

	delta = freq_weight * (r_after - r_before)
	total_mass = get_total_frequency_mass()
	if total_mass:
		comprehension_change = delta / total_mass
		comprehension_change = max(comprehension_change, 0.0000000001)
		tooltip(f"Comprehension change: 1 / {readable_number(1 / comprehension_change)}")

def readable_number(x):
	if x > 1_000_000_000:
		return f'{round(x / 1_000_000)}bil'
	if x > 1_000_000:
		return f'{round(x / 1_000_000)}mil'
	if x > 1_000:
		return f'{round(x / 1_000)}k'
	return round(x)

def add_tools_menu():
	menu = mw.form.menuTools
	act1 = QAction("Update all Chinese words", mw)
	act1.triggered.connect(on_update_all)
	menu.addAction(act1)
	act2 = QAction("Chinese words info", mw)
	act2.triggered.connect(on_info)
	menu.addAction(act2)

gui_hooks.main_window_did_init.append(add_tools_menu)
gui_hooks.reviewer_did_show_question.append(on_card_will_show)
gui_hooks.reviewer_did_answer_card.append(on_card_reviewed)

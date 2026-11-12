"""Warn before introducing a word already studied in a different note."""
from html import unescape

from anki.consts import CARD_TYPE_NEW
from anki.utils import strip_html
from aqt import dialogs, gui_hooks, mw

_introduced_words = None
_SHOW_DUPLICATES = "cvm-show-introduced-duplicates"
_BANNER = """
<style>
#cvm-duplicate-warning {
    box-sizing: border-box; width: fit-content; max-width: 100%;
    padding: 12px 14px; margin: 0 auto 20px;
    border: 1px solid #e7b9b9; border-radius: 4px;
    background: #fff0f0; color: #9b2525;
    text-align: center; font: large/1.4 Arial, sans-serif;
}
#cvm-duplicate-warning strong { font-weight: 500; }
#cvm-duplicate-warning button {
    display: inline-block; margin-top: 6px; padding: 6px 12px;
    border: 1px solid #e7b9b9; border-radius: 4px;
    background: #a52c2c; color: #ffffff; font: inherit; cursor: pointer;
}
.nightMode #cvm-duplicate-warning, .night-mode #cvm-duplicate-warning {
    border-color: #704040; background: #392626; color: #f3b0b0;
}
.nightMode #cvm-duplicate-warning button, .night-mode #cvm-duplicate-warning button {
    border-color: #e28b8b; background: #b94f4f; color: #ffffff;
}
</style>
<div id="cvm-duplicate-warning" role="status">
    <div><span aria-hidden="true">&#9888;&#65038;</span> <strong>Already studied this word</strong></div>
    <button type="button" onclick="pycmd('cvm-show-introduced-duplicates');">View existing note</button>
</div>
"""


def _normalize_word(value):
    return unescape(strip_html(value)).strip()


def _word(note):
    return _normalize_word(note["word"]) if "word" in note else ""


def _clear_cache(*args):
    global _introduced_words
    _introduced_words = None


def _matching_notes(card):
    global _introduced_words
    if card.type != CARD_TYPE_NEW or not mw.col:
        return []
    note = card.note()
    word = _word(note)
    if not word:
        return []
    if _introduced_words is None:
        _introduced_words = {}
        word_fields = {}
        # Only real answers count as introductions; manual rescheduling does not.
        rows = mw.col.db.all(
            "SELECT id, mid, flds FROM notes WHERE id IN ("
            "SELECT nid FROM cards WHERE id IN ("
            "SELECT cid FROM revlog WHERE ease > 0 AND NOT (type = 3 AND factor = 0)))"
        )
        for nid, mid, fields in rows:
            if mid not in word_fields:
                model = mw.col.models.get(mid)
                word_fields[mid] = next((f["ord"] for f in model["flds"] if f["name"] == "word"), None)
            index = word_fields[mid]
            if index is not None:
                introduced_word = _normalize_word(fields.split("\x1f")[index])
                if introduced_word:
                    _introduced_words.setdefault(introduced_word, set()).add(nid)
    return sorted(_introduced_words.get(word, set()) - {note.id})


def _add_warning(text, card, kind):
    if kind in ("reviewQuestion", "reviewAnswer") and _matching_notes(card):
        return _BANNER + text
    return text


def _on_answer(reviewer, card, ease):
    if _introduced_words is not None:
        note = card.note()
        word = _word(note)
        if word:
            _introduced_words.setdefault(word, set()).add(note.id)


def _on_operation(changes, initiator):
    if changes.note or changes.notetype or (changes.card and initiator is not mw.reviewer):
        _clear_cache()


def _on_message(handled, message, context):
    if handled[0] or message != _SHOW_DUPLICATES or context is not mw.reviewer:
        return handled
    if context.card and (notes := _matching_notes(context.card)):
        dialogs.open("Browser", mw, search=("nid:" + ",".join(map(str, notes)),))
    return True, None


def setup_duplicate_warning():
    gui_hooks.card_will_show.append(_add_warning)
    gui_hooks.webview_did_receive_js_message.append(_on_message)
    gui_hooks.reviewer_did_answer_card.append(_on_answer)
    gui_hooks.operation_did_execute.append(_on_operation)
    gui_hooks.profile_did_open.append(_clear_cache)
    gui_hooks.reviewer_will_end.append(_clear_cache)

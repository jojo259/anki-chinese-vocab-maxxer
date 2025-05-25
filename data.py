from pathlib import Path
from functools import lru_cache
import csv
from collections import defaultdict

BASE_PATH = Path(__file__).resolve().parent
ASSETS_PATH = BASE_PATH / 'assets'
HSK_PATH = ASSETS_PATH / 'hsk'
CEDICT_PATH = ASSETS_PATH / 'cedict_ts.u8'
FREQ_PATH = ASSETS_PATH / 'word-freq.csv'

@lru_cache(maxsize=None)
def _build_hsk_map():
	hsk = {}
	for level in range(1, 7):
		fp = HSK_PATH / f'hsk{level}.csv'
		if not fp.exists():
			continue
		with fp.open(encoding='utf-8') as f:
			for line in f:
				word = line.split('|', 1)[0].strip()
				if word:
					hsk[word] = level
	return hsk

@lru_cache(maxsize=None)
def get_hsk_level(word: str):
	return _HSK_MAP.get(word)

@lru_cache(maxsize=None)
def cedict_to_diacritic(pinyin: str) -> str:
	vowel_tones = {
		'a': 'āáǎà', 'e': 'ēéěè', 'i': 'īíǐì',
		'o': 'ōóǒò', 'u': 'ūúǔù', 'ü': 'ǖǘǚǜ'
	}
	result = []
	for syl in pinyin.split():
		tone = int(syl[-1]) if syl[-1].isdigit() else 5
		base = syl[:-1] if syl[-1].isdigit() else syl
		base = base.replace('u:', 'ü').replace('v', 'ü')
		target = None
		if tone != 5:
			for v in ('a','o','e'):
				if v in base:
					target = v
					break
			if target is None:
				if 'iu' in base:
					target = 'u'
				elif 'ui' in base:
					target = 'i'
				else:
					for ch in reversed(base):
						if ch in 'aeiouü':
							target = ch
							break
		if tone == 5 or target is None:
			result.append(base)
		else:
			acc = vowel_tones[target][tone-1]
			result.append(base.replace(target, acc, 1))
	return ''.join(result)

@lru_cache(maxsize=None)
def _build_cedict_maps():
	pmap = defaultdict(list)
	dmap = defaultdict(list)
	with CEDICT_PATH.open(encoding='utf-8') as f:
		for ln in f:
			if ln.startswith('#'):
				continue
			ln = ln.strip()
			if not ln:
				continue
			parts = ln.split(' ', 2)
			if len(parts) < 3:
				continue
			trad, simp, rest = parts
			pin = cedict_to_diacritic(rest.split(']')[0][1:])
			defs = rest.split(']', 1)[1][2:-1].replace('/', '; ')
			pmap[simp].append(pin.lower())
			dmap[simp].append(defs)
	return pmap, dmap

_PINYIN_MAP, _DEF_MAP = _build_cedict_maps()

@lru_cache(maxsize=None)
def get_definitions(word: str):
	defs = _DEF_MAP.get(word)
	if defs:
		return ' / '.join(defs)
	return None

@lru_cache(maxsize=None)
def get_pinyin(word: str):
	pins = _PINYIN_MAP.get(word)
	if pins:
		return ' / '.join(pins)
	return None

@lru_cache(maxsize=None)
def _build_freq_maps():
	rank_map = {}
	weight_map = {}
	with FREQ_PATH.open(encoding='utf-8') as f:
		reader = csv.DictReader(f, delimiter='|')
		for idx,row in enumerate(reader,start=1):
			wd = row['Word']
			try:
				w = float(row['W/million']) / 1_000_000
			except:
				w = 0.0
			rank_map[wd] = idx
			weight_map[wd] = w
	return rank_map, weight_map

@lru_cache(maxsize=None)
def get_frequency_rank(word: str):
	return _RANK_MAP.get(word)

@lru_cache(maxsize=None)
def get_frequency_weight(word: str):
	return _WEIGHT_MAP.get(word)

def get_total_frequency_mass():
	return sum(_WEIGHT_MAP.values())

@lru_cache(maxsize=None)
def get_word_data(word: str):
	hsk = get_hsk_level(word)
	defs = get_definitions(word)
	freq_rank, freq_weight = get_frequency_rank(word), get_frequency_weight(word)
	pinyin = get_pinyin(word)
	return hsk, defs, pinyin, freq_rank, freq_weight

_HSK_MAP = _build_hsk_map()
_RANK_MAP, _WEIGHT_MAP = _build_freq_maps()

from aqt import mw, gui_hooks
from aqt.qt import QAction, QDialog, QVBoxLayout, QLabel, QPushButton
from aqt.utils import tooltip
from .data import (
	get_word_data,
	get_frequency_weight,
	get_total_frequency_mass,
	get_frequency_rank,
	get_hsk_counts,
	get_hsk_level,
	get_all_words,
)
import math

_last_retrievabilities = {}

def on_update_all():
	cnt = 0
	col = mw.col
	for nid in col.find_notes("note:chinese-word"):
		note = col.get_note(nid)
		word = note['word']
		hsk, defs, pinyin, freq_rank, freq_weight, freq_level = get_word_data(word)
		freq_weight = freq_weight or 0.0000000001
		hsk_str = str(hsk or '')
		defs_str = defs or ''
		pin_str = pinyin or ''
		if not defs_str or not pin_str:
			continue
		freq_rank_str = str(freq_rank or '')
		freq_weight_str = f'1 / {readable_number(1 / freq_weight)}'
		freq_level_str = str(freq_level or '')
		if not (
			note['hsk'] == hsk_str and
			note['definition'] == defs_str and
			note['freq-rank'] == freq_rank_str and
			note['freq-weight'] == freq_weight_str and
			note['freq-level'] == freq_level_str and
			note['pinyin'] == pin_str
		):
			note['pinyin'] = pin_str
			note['freq-rank'] = freq_rank_str
			note['freq-weight'] = freq_weight_str
			note['freq-level'] = freq_level_str
			note['definition'] = defs_str
			note['hsk'] = hsk_str
			col.update_note(note)
			cnt += 1
			if cnt % 100 == 0:
				print(f'updated {cnt} chinese notes')
	tooltip(f"Updated {cnt} notes")

from aqt.qt import (
	QAction, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QSpinBox,
	QWidget, QPainter, QColor, Qt, QBrush, QPen, QRectF, QTimer, QTableWidget, QTableWidgetItem, QHeaderView, QToolTip
)

class FrequencyGraph(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setMouseTracking(True)
		self.bucket_counts = []
		self.unreviewed_counts = []
		self.bucket_stats_list = []
		self.bucket_size = 100
		self.max_rank = 10000
		self.hsk_mode = False
		self.hsk_totals = {}
		self.bar_rects = [] # (rect, bucket_index)
		self.setMinimumHeight(200)

	def set_config(self, bucket_size, max_rank):
		self.bucket_size = bucket_size
		self.max_rank = max_rank

	def set_hsk_mode(self, enabled, totals=None):
		self.hsk_mode = enabled
		self.hsk_totals = totals or {}

	def set_data(self, bucket_counts, unreviewed_counts=None, bucket_stats_list=None):
		self.bucket_counts = bucket_counts
		self.unreviewed_counts = unreviewed_counts if unreviewed_counts else []
		self.bucket_stats_list = bucket_stats_list if bucket_stats_list else []
		self.update()

	def mouseMoveEvent(self, event):
		p = event.position()
		px, py = p.x(), p.y()
		tooltip_text = ""
		
		# Find if mouse is over any bar rect
		for rect, idx in self.bar_rects:
			if rect.left() <= px <= rect.right() and rect.top() <= py <= rect.bottom():
				# Calculate stats for this bucket
				count = self.bucket_counts[idx] if idx < len(self.bucket_counts) else 0
				unrev_count = 0
				if idx < len(self.unreviewed_counts):
					unrev_count = self.unreviewed_counts[idx]
				
				if self.hsk_mode:
					label = f"HSK {idx + 1}"
					total_in_bucket = self.hsk_totals.get(idx + 1, 1)
				else:
					start_rank = idx * self.bucket_size + 1
					end_rank = (idx + 1) * self.bucket_size
					label = f"Freq Rank: {start_rank} - {end_rank}"
					total_in_bucket = self.bucket_size
				
				total_in_bucket = max(1, total_in_bucket)
				
				pct_known = (count / total_in_bucket) * 100.0
				pct_total = ((count + unrev_count) / total_in_bucket) * 100.0
				
				stats = self.bucket_stats_list[idx] if idx < len(self.bucket_stats_list) else {}
				avg_r = stats.get('avg_retrievability', 0)
				avg_s = stats.get('avg_stability', 0)
				
				cov_k = stats.get('coverage_known', 0)
				cov_t = stats.get('coverage_total', 0)
				
				tooltip_text = (
					f"<b>{label}</b><br>"
					f"Known: {count} ({pct_known:.1f}%)<br>"
					f"Including Unreviewed: {count + unrev_count} ({pct_total:.1f}%)<br>"
					f"Avg Retrievability: {avg_r:.1f}%<br>"
					f"Avg Stability: {avg_s:.1f} days<br>"
					f"Coverage (Known): +{cov_k:.6f}%<br>"
					f"Coverage (Known + New): +{cov_t:.6f}%"
				)
				break
		
		if tooltip_text:
			QToolTip.showText(event.globalPosition().toPoint(), tooltip_text, self)
		else:
			QToolTip.hideText()

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)
		
		w = self.width()
		h = self.height()
		
		margin_left = 60
		margin_bottom = 40
		graph_w = w - margin_left
		graph_h = h - margin_bottom

		painter.fillRect(0, 0, w, h, QColor("#f0f0f0"))
		
		self.bar_rects = [] # Clear previous rects

		if not self.bucket_counts:
			return

		max_y_val = 100.0

		num_buckets = len(self.bucket_counts)
		
		if num_buckets == 0:
			return

		bar_width = graph_w / num_buckets

		pen = QPen(Qt.GlobalColor.black, 1)
		painter.setPen(pen)
		painter.drawLine(margin_left, 0, margin_left, int(h - margin_bottom))
		painter.drawLine(margin_left, int(h - margin_bottom), w, int(h - margin_bottom))

		painter.setPen(Qt.PenStyle.NoPen)
		
		has_unreviewed = len(self.unreviewed_counts) == len(self.bucket_counts)

		for i, count in enumerate(self.bucket_counts):
			if self.hsk_mode:
				total_in_bucket = self.hsk_totals.get(i + 1, 1)
			else:
				total_in_bucket = self.bucket_size

			total_in_bucket = max(1, total_in_bucket)

			pct_known = (count / total_in_bucket) * 100.0
			
			pct_unreviewed = 0.0
			if has_unreviewed:
				pct_unreviewed = (self.unreviewed_counts[i] / total_in_bucket) * 100.0
			
			total_pct = min(pct_known + pct_unreviewed, 100.0)
			
			x = margin_left + i * bar_width
			
			h_known = (pct_known / max_y_val) * graph_h
			y_known = h - margin_bottom - h_known
			
			h_unrev = (pct_unreviewed / max_y_val) * graph_h
			y_unrev = y_known - h_unrev
			
			painter.setBrush(QBrush(QColor("#5c9eff")))
			rect_known = QRectF(x, y_known, bar_width, h_known)
			painter.drawRect(rect_known)
			
			# Store rect for tooltip (full bar height from bottom)
			full_height = h_known + h_unrev
			full_y = y_known - h_unrev
			self.bar_rects.append((QRectF(x, full_y, bar_width, full_height), i))
			
			if h_unrev > 0:
				painter.setBrush(QBrush(QColor("#f2c94c")))
				rect_unrev = QRectF(x, y_unrev, bar_width, h_unrev)
				painter.drawRect(rect_unrev)

		painter.setPen(Qt.GlobalColor.black)
		
		if self.hsk_mode:
			label_text = "HSK Levels"
			painter.drawText(margin_left + graph_w // 2 - 50, h - 5, label_text)
			
			for i in range(num_buckets):
				x = margin_left + i * bar_width
				label_x = x + bar_width / 2 - 15
				painter.drawText(int(label_x), int(h - 20), f"HSK{i+1}")
		
		else:
			label_text = f"Frequency Rank (buckets of {self.bucket_size})"
			painter.drawText(margin_left + graph_w // 2 - 100, h - 5, label_text)
			
			target_labels = 10
			step = max(1, num_buckets // target_labels)
			
			for i in range(0, num_buckets, step):
				x = margin_left + i * bar_width
				rank_val = i * self.bucket_size + 1
				painter.drawText(int(x), int(h - 20), str(rank_val))
			
			painter.drawText(int(w - 40), int(h - 20), str(num_buckets * self.bucket_size))

		painter.drawText(5, int(h - margin_bottom), "0%")
		painter.drawText(5, int(h - margin_bottom - graph_h/2), "50%")
		painter.drawText(5, 15, "100%")

		painter.save()
		painter.translate(15, h / 2)
		painter.rotate(-90)
		painter.drawText(0, 0, "Known %")
		painter.restore()

class NewWordsDialog(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Top New Words")
		self.resize(800, 600)
		self.layout = QVBoxLayout()
		self.setLayout(self.layout)

		self.table = QTableWidget()
		self.table.setColumnCount(5)
		self.table.setHorizontalHeaderLabels(["Rank", "Word", "Pinyin", "Meaning", "Status"])
		header = self.table.horizontalHeader()
		header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) 
		self.layout.addWidget(self.table)

		self.btn_load = QPushButton("Load 100 More")
		self.btn_load.clicked.connect(self.load_more)
		self.layout.addWidget(self.btn_load)

		self.close_btn = QPushButton("Close")
		self.close_btn.clicked.connect(self.accept)
		self.layout.addWidget(self.close_btn)
		
		self.all_words = get_all_words()
		self.offset = 0
		self.batch_size = 100
		
		self._init_anki_state()
		
		self.load_more()

	def _init_anki_state(self):
		col = mw.col
		self.studied_words = set()
		self.suspended_words = set()
		
		query_studied = "note:chinese-word (is:learn OR is:review)"
		for cid in col.find_cards(query_studied):
			note = col.get_note(col.get_card(cid).nid)
			self.studied_words.add(note['word'])

		query_suspended = "note:chinese-word is:suspended"
		for cid in col.find_cards(query_suspended):
			note = col.get_note(col.get_card(cid).nid)
			self.suspended_words.add(note['word'])
		
		self.present_words = {} 
		for nid in col.find_notes("note:chinese-word"):
			note = col.get_note(nid)
			w = note['word']
			if w not in self.present_words:
				cards = note.cards()
				if cards:
					c = cards[0]
					d_name = col.decks.name(c.did)
					self.present_words[w] = d_name
				else:
					self.present_words[w] = "No Cards"

	def load_more(self):
		col = mw.col
		count = 0
		row_start = self.table.rowCount()
		
		while count < self.batch_size and self.offset < len(self.all_words):
			word = self.all_words[self.offset]
			self.offset += 1
			
			if word in self.studied_words or word in self.suspended_words:
				continue
				
			status = self.present_words.get(word, "Not in Collection")
			hsk, defs, pinyin, rank, freq_weight, freq_level = get_word_data(word)
			
			row = row_start + count
			self.table.insertRow(row)
			
			self.table.setItem(row, 0, QTableWidgetItem(str(rank)))
			self.table.setItem(row, 1, QTableWidgetItem(word))
			self.table.setItem(row, 2, QTableWidgetItem(pinyin or ""))
			self.table.setItem(row, 3, QTableWidgetItem(defs or ""))
			self.table.setItem(row, 4, QTableWidgetItem(status))
			
			count += 1

		if self.offset >= len(self.all_words):
			self.btn_load.setEnabled(False)
			self.btn_load.setText("No More Words")

class ChineseInfoDialog(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Chinese Words Info")
		self.resize(1000, 600)
		
		config = mw.addonManager.getConfig(__name__) or {}
		init_bucket_size = config.get('graph_bucket_size', 100)
		init_max_rank = config.get('graph_max_rank', 10000)

		layout = QVBoxLayout()
		self.setLayout(layout)

		controls_layout = QHBoxLayout()
		
		self.check_pronounce = QCheckBox("Switch to 'Pronounce' cards (default: 'Define')")
		self.check_pronounce.stateChanged.connect(self.refresh_stats)
		controls_layout.addWidget(self.check_pronounce)
		
		self.check_unreviewed = QCheckBox("Show unreviewed added cards")
		self.check_unreviewed.stateChanged.connect(self.refresh_stats)
		controls_layout.addWidget(self.check_unreviewed)

		self.check_hsk = QCheckBox("Group by HSK Levels")
		self.check_hsk.stateChanged.connect(self.refresh_stats)
		controls_layout.addWidget(self.check_hsk)
		
		controls_layout.addStretch()
		
		btn_new = QPushButton("View Top New Words")
		btn_new.clicked.connect(self.open_new_words)
		controls_layout.addWidget(btn_new)

		self.lbl_bucket = QLabel("Bucket Size:")
		controls_layout.addWidget(self.lbl_bucket)
		self.spin_bucket = QSpinBox()
		self.spin_bucket.setRange(10, 5000)
		self.spin_bucket.setSingleStep(10)
		self.spin_bucket.setValue(init_bucket_size)
		self.spin_bucket.valueChanged.connect(self.schedule_refresh)
		controls_layout.addWidget(self.spin_bucket)

		self.lbl_rank = QLabel("Max Rank:")
		controls_layout.addWidget(self.lbl_rank)
		self.spin_max_rank = QSpinBox()
		self.spin_max_rank.setRange(100, 1000000)
		self.spin_max_rank.setSingleStep(1000)
		self.spin_max_rank.setValue(init_max_rank)
		self.spin_max_rank.valueChanged.connect(self.schedule_refresh)
		controls_layout.addWidget(self.spin_max_rank)

		layout.addLayout(controls_layout)

		self.stats_label = QLabel("Calculating...")
		self.stats_label.setTextFormat(Qt.TextFormat.RichText)
		layout.addWidget(self.stats_label)

		self.graph = FrequencyGraph()
		layout.addWidget(self.graph)

		close_btn = QPushButton("Close")
		close_btn.clicked.connect(self.accept)
		layout.addWidget(close_btn)
		
		self.debounce_timer = QTimer()
		self.debounce_timer.setSingleShot(True)
		self.debounce_timer.setInterval(400) 
		self.debounce_timer.timeout.connect(self.refresh_stats)

		self.refresh_stats()

	def open_new_words(self):
		dlg = NewWordsDialog(self)
		dlg.exec()

	def schedule_refresh(self):
		self.debounce_timer.start()

	def refresh_stats(self):
		self.debounce_timer.stop()
		col = mw.col
		use_pronounce = self.check_pronounce.isChecked()
		show_unreviewed = self.check_unreviewed.isChecked()
		show_hsk = self.check_hsk.isChecked()
		bucket_size = self.spin_bucket.value()
		max_rank_cutoff = self.spin_max_rank.value()

		self.spin_bucket.setVisible(not show_hsk)
		self.spin_max_rank.setVisible(not show_hsk)
		self.lbl_bucket.setVisible(not show_hsk)
		self.lbl_rank.setVisible(not show_hsk)

		hsk_totals = {}
		if show_hsk:
			hsk_totals = get_hsk_counts()
			self.graph.set_hsk_mode(True, hsk_totals)
		else:
			self.graph.set_hsk_mode(False)
			self.graph.set_config(bucket_size, max_rank_cutoff)

		card_type = "hanzi-pronounce" if use_pronounce else "hanzi-define"
		query_base = f"note:chinese-word card:{card_type} -is:suspended"
		query_known = f"{query_base} (is:learn OR is:review)"
		
		# Gather known words stats
		known = {} # word -> {'r': retrievability, 's': stability}
		for cid in col.find_cards(query_known):
			card = col.get_card(cid)
			note = card.note()
			stats = mw.col.card_stats_data(card.id)
			r = stats.fsrs_retrievability or 0.0
			s = 0.0
			if getattr(card, 'memory_state', None):
				s = card.memory_state.stability
			known[note['word']] = {'r': r, 's': s}

		# Gather unreviewed words if needed
		unreviewed_words = set()
		if show_unreviewed:
			# Get all words from base query
			for cid in col.find_cards(query_base):
				card = col.get_card(cid)
				note = card.note()
				w = note['word']
				if w not in known:
					unreviewed_words.add(w)

		def get_mass(w):
			val = get_frequency_weight(w)
			if val is None: return 0.0
			# Enforce minimum weight to ensure visibility in UI
			return max(val, 1e-9)

		total_mass = get_total_frequency_mass()
		basic_mass = sum(get_mass(w) for w in known)
		retrieval_mass = sum(get_mass(w) * (d['r'] or 0) for w, d in known.items())

		basic_perc = (basic_mass / total_mass * 100) if total_mass else 0
		retrieval_perc = (retrieval_mass / total_mass * 100) if total_mass else 0

		max_rank_found = 0
		
		bucket_counts = {}
		unreviewed_bucket_counts = {}
		
		# bucket stats: idx -> {stats}
		bucket_stats = {} 
		
		def get_bucket_stats(idx):
			if idx not in bucket_stats:
				bucket_stats[idx] = {'sum_r': 0.0, 'sum_s': 0.0, 'count_known': 0, 'mass_known': 0.0, 'mass_total': 0.0}
			return bucket_stats[idx]

		if show_hsk:
			# HSK Mode
			for word, d in known.items():
				lvl = get_hsk_level(word)
				if lvl and 1 <= lvl <= 6:
					b_idx = lvl - 1
					s = get_bucket_stats(b_idx)
					bucket_counts[b_idx] = bucket_counts.get(b_idx, 0) + 1
					
					s['sum_r'] += (d['r'] or 0) * 100
					s['sum_s'] += d['s'] or 0
					s['count_known'] += 1
					
					w_mass = get_mass(word)
					s['mass_known'] += w_mass
					s['mass_total'] += w_mass

			if show_unreviewed:
				for word in unreviewed_words:
					lvl = get_hsk_level(word)
					if lvl and 1 <= lvl <= 6:
						b_idx = lvl - 1
						s = get_bucket_stats(b_idx)
						unreviewed_bucket_counts[b_idx] = unreviewed_bucket_counts.get(b_idx, 0) + 1
						
						w_mass = get_mass(word)
						s['mass_total'] += w_mass
			
			total_buckets_needed = 6
			
		else:
			# Freq Rank Mode
			for word, d in known.items():
				rank = get_frequency_rank(word)
				if rank:
					max_rank_found = max(max_rank_found, rank)
					if rank <= max_rank_cutoff:
						b_idx = (rank - 1) // bucket_size
						s = get_bucket_stats(b_idx)
						bucket_counts[b_idx] = bucket_counts.get(b_idx, 0) + 1
						
						s['sum_r'] += (d['r'] or 0) * 100
						s['sum_s'] += d['s'] or 0
						s['count_known'] += 1
						
						w_mass = get_mass(word)
						s['mass_known'] += w_mass
						s['mass_total'] += w_mass

			if show_unreviewed:
				for word in unreviewed_words:
					rank = get_frequency_rank(word)
					if rank:
						max_rank_found = max(max_rank_found, rank)
						if rank <= max_rank_cutoff:
							b_idx = (rank - 1) // bucket_size
							s = get_bucket_stats(b_idx)
							unreviewed_bucket_counts[b_idx] = unreviewed_bucket_counts.get(b_idx, 0) + 1
							
							w_mass = get_mass(word)
							s['mass_total'] += w_mass
			
			total_buckets_needed = max_rank_cutoff // bucket_size
		
		data_list = [0] * total_buckets_needed
		unrev_list = [0] * total_buckets_needed
		stats_list = []

		for idx in range(total_buckets_needed):
			count = bucket_counts.get(idx, 0)
			data_list[idx] = count
			
			unrev = unreviewed_bucket_counts.get(idx, 0)
			if show_unreviewed:
				unrev_list[idx] = unrev
			
			s = bucket_stats.get(idx, {'sum_r':0, 'sum_s':0, 'count_known':0, 'mass_known':0, 'mass_total':0})
			c_known = s['count_known']
			avg_r = (s['sum_r'] / c_known) if c_known else 0
			avg_s = (s['sum_s'] / c_known) if c_known else 0
			cov_k = (s['mass_known'] / total_mass * 100) if total_mass else 0
			cov_t = (s['mass_total'] / total_mass * 100) if total_mass else 0
			
			stats_list.append({
				'avg_retrievability': avg_r, 
				'avg_stability': avg_s,
				'coverage_known': cov_k,
				'coverage_total': cov_t
			})
		
		self.graph.set_data(data_list, unrev_list if show_unreviewed else None, stats_list)
		
		info_text = (
			f"<h3>Stats for '{card_type}'</h3>"
			f"Basic estimated comprehension: <b>{basic_perc:.4f}%</b><br>"
			f"Retrievability-weighted: <b>{retrieval_perc:.4f}%</b><br>"
			f"Based on <b>{len(known)}</b> words<br>"
		)
		
		if not show_hsk:
			info_text += f"Highest Rank Found: {max_rank_found} (Graph limited to {max_rank_cutoff})"
			
		self.stats_label.setText(info_text)

def on_info():
	mw.chinese_info_dialog = ChineseInfoDialog(mw)
	mw.chinese_info_dialog.exec()

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

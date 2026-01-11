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

_pre_review_ivl = {}
_session_gain = 0.0
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

import datetime
import time
from aqt.qt import (
	QAction, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QSpinBox,
	QWidget, QPainter, QColor, Qt, QBrush, QPen, QRectF, QTimer, QTableWidget, QTableWidgetItem, QHeaderView, QToolTip,
	QPainterPath, QPointF, QLinearGradient
)

class FrequencyGraph(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setMouseTracking(True)
		self.bucket_counts = []
		self.unreviewed_counts = []
		self.simulated_counts = []
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

	def set_data(self, bucket_counts, unreviewed_counts=None, simulated_counts=None, bucket_stats_list=None):
		self.bucket_counts = bucket_counts
		self.unreviewed_counts = unreviewed_counts if unreviewed_counts else []
		self.simulated_counts = simulated_counts if simulated_counts else []
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
					f"Coverage (Known + New): +{cov_t:.6f}%<br>"
					f"Simulated Gain: +{stats.get('coverage_sim', 0):.6f}%"
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
			
			pct_sim = 0.0
			h_sim = 0.0
			if i < len(self.simulated_counts):
				pct_sim = (self.simulated_counts[i] / total_in_bucket) * 100.0
				h_sim = (pct_sim / max_y_val) * graph_h
				full_height += h_sim
				
			full_y = y_known - h_unrev - h_sim
			self.bar_rects.append((QRectF(x, full_y, bar_width, full_height), i))
			
			if h_unrev > 0:
				painter.setBrush(QBrush(QColor("#f2c94c")))
				rect_unrev = QRectF(x, y_unrev, bar_width, h_unrev)
				painter.drawRect(rect_unrev)

			if h_sim > 0:
				y_sim = y_unrev - h_sim
				painter.setBrush(QBrush(QColor("#9c27b0"))) # Purple for simulated
				rect_sim = QRectF(x, y_sim, bar_width, h_sim)
				painter.drawRect(rect_sim)

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

class HistoryGraph(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setMouseTracking(True)
		self.data_history = [] # list of (timestamp_sec, basic_pct, weighted_pct)
		self.setMinimumHeight(300)
		self.hover_idx = -1

	def set_data(self, history):
		self.data_history = history
		self.update()

	def mouseMoveEvent(self, event):
		if not self.data_history:
			return
		
		p = event.position()
		x = p.x()
		w = self.width()
		margin_left = 60
		margin_right = 20
		graph_w = w - margin_left - margin_right
		
		if x < margin_left or x > w - margin_right:
			if self.hover_idx != -1:
				self.hover_idx = -1
				QToolTip.hideText()
				self.update()
			return

		ratio = (x - margin_left) / graph_w
		idx = int(ratio * (len(self.data_history) - 1))
		idx = max(0, min(idx, len(self.data_history) - 1))
		
		if idx != self.hover_idx:
			self.hover_idx = idx
			self.update()
			
			ts, basic, weighted, weighted_all = self.data_history[idx]
			date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
			
			tooltip_text = (
				f"<b>{date_str}</b><br>"
				f"Basic (Active): {basic:.2f}%<br>"
				f"Weighted (Active): {weighted:.2f}%<br>"
				f"<span style='color:#f0ad4e'>Weighted (Inc. Suspended): {weighted_all:.2f}%</span>"
			)
			QToolTip.showText(event.globalPosition().toPoint(), tooltip_text, self)

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)
		
		w = self.width()
		h = self.height()
		margin_left = 60
		margin_bottom = 30
		margin_right = 20
		margin_top = 20
		
		graph_w = w - margin_left - margin_right
		graph_h = h - margin_bottom - margin_top
		
		painter.fillRect(0, 0, w, h, QColor("#ffffff"))
		
		# Draw axes
		painter.setPen(QPen(QColor("#cccccc"), 1))
		painter.drawLine(margin_left, margin_top, margin_left, int(h - margin_bottom)) # Y axis
		painter.drawLine(margin_left, int(h - margin_bottom), int(w - margin_right), int(h - margin_bottom)) # X axis
		
		# Y axis labels
		painter.setPen(Qt.GlobalColor.black)
		for i in range(0, 101, 20):
			y = h - margin_bottom - (i / 100.0) * graph_h
			painter.drawText(5, int(y + 5), 50, 20, Qt.AlignmentFlag.AlignRight, f"{i}%")
			painter.setPen(QPen(QColor("#eeeeee"), 1))
			painter.drawLine(margin_left, int(y), int(w - margin_right), int(y))
			painter.setPen(Qt.GlobalColor.black)

		if not self.data_history:
			return

		# Create paths
		path_basic = QPainterPath()
		path_weighted = QPainterPath()
		path_all = QPainterPath()
		
		start_ts = self.data_history[0][0]
		end_ts = self.data_history[-1][0]
		duration = end_ts - start_ts or 1
		
		def get_pt(i, val):
			ts = self.data_history[i][0]
			x = margin_left + ((ts - start_ts) / duration) * graph_w
			y = h - margin_bottom - (val / 100.0) * graph_h
			return QPointF(x, y)

		path_basic.moveTo(get_pt(0, self.data_history[0][1]))
		path_weighted.moveTo(get_pt(0, self.data_history[0][2]))
		path_all.moveTo(get_pt(0, self.data_history[0][3]))
		
		for i in range(1, len(self.data_history)):
			path_basic.lineTo(get_pt(i, self.data_history[i][1]))
			path_weighted.lineTo(get_pt(i, self.data_history[i][2]))
			path_all.lineTo(get_pt(i, self.data_history[i][3]))
			
		# Draw All (Yellow) first so it is behind
		pen_all = QPen(QColor("#f2c94c"), 2)
		painter.setPen(pen_all)
		painter.drawPath(path_all)

		# Draw Basic (Blue)
		pen_basic = QPen(QColor("#5c9eff"), 2)
		painter.setPen(pen_basic)
		painter.drawPath(path_basic)
		
		# Draw Weighted (Red)
		pen_weighted = QPen(QColor("#e91e63"), 2)
		painter.setPen(pen_weighted)
		painter.drawPath(path_weighted)

		# Legend
		painter.setPen(Qt.GlobalColor.black)
		
		# Basic
		painter.fillRect(margin_left + 10, margin_top + 10, 10, 10, QColor("#5c9eff"))
		painter.drawText(margin_left + 25, margin_top + 20, "Basic (Active)")
		
		# Weighted
		painter.fillRect(margin_left + 10, margin_top + 30, 10, 10, QColor("#e91e63"))
		painter.drawText(margin_left + 25, margin_top + 40, "Weighted (Active)")

		# All
		painter.fillRect(margin_left + 150, margin_top + 30, 10, 10, QColor("#f2c94c"))
		painter.drawText(margin_left + 165, margin_top + 40, "Weighted (Inc. Suspended)")


		# Hover line
		if self.hover_idx >= 0:
			ts, basic, weighted, w_all = self.data_history[self.hover_idx]
			x = margin_left + ((ts - start_ts) / duration) * graph_w
			painter.setPen(QPen(QColor("#000000"), 1, Qt.PenStyle.DashLine))
			painter.drawLine(int(x), margin_top, int(x), int(h - margin_bottom))
			
			# Draw dots
			y_b = h - margin_bottom - (basic / 100.0) * graph_h
			y_w = h - margin_bottom - (weighted / 100.0) * graph_h
			y_a = h - margin_bottom - (w_all / 100.0) * graph_h
			
			painter.setBrush(QBrush(QColor("#f2c94c")))
			painter.drawEllipse(QPointF(x, y_a), 4, 4)
			
			painter.setBrush(QBrush(QColor("#5c9eff")))
			painter.drawEllipse(QPointF(x, y_b), 4, 4)
			
			painter.setBrush(QBrush(QColor("#e91e63")))
			painter.drawEllipse(QPointF(x, y_w), 4, 4)


class HistoryDialog(QDialog):
	def __init__(self, parent=None, card_type_mode="hanzi-define"):
		super().__init__(parent)
		self.setWindowTitle("Comprehension History")
		self.resize(1000, 600)
		self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
		
		self.card_type_mode = card_type_mode
		
		layout = QVBoxLayout()
		self.setLayout(layout)
		
		self.lbl_status = QLabel("Loading history... (this may take a moment)")
		self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
		layout.addWidget(self.lbl_status)
		
		self.graph = HistoryGraph()
		self.graph.setVisible(False)
		layout.addWidget(self.graph)
		
		self.close_btn = QPushButton("Close")
		self.close_btn.clicked.connect(self.accept)
		layout.addWidget(self.close_btn)
		
		QTimer.singleShot(100, self.calculate_history)

	def calculate_history(self):
		col = mw.col
		
		# Build mappings: CID -> Word, Word -> Weight
		cid_to_word = {}
		word_weights = {} # word -> weight
		active_cids = set() # currently active (not suspended)
		
		note_ids = col.find_notes("note:chinese-word")
		
		# Get card ord for the requested type
		# hanzi-define is usually ord 0 or 1 depending on template
		# But searching by card:hanzi-define is safer if we want CIDs
		# However, here we iterate notes. Let's find the correct ordinal.
		model = col.models.by_name("Chinese Words") 
		if not model:
			# Fallback if model name different, try query approach
			# This is slower but safer
			pass
			
		target_ords = []
		if model:
			for tmpl in model['tmpls']:
				if tmpl['name'] == self.card_type_mode:
					target_ords.append(tmpl['ord'])
		
		target_ord = target_ords[0] if target_ords else 0

		for nid in note_ids:
			note = col.get_note(nid)
			w = note['word']
			weight = get_frequency_weight(w)
			if weight:
				word_weights[w] = weight
				for card in note.cards():
					if card.ord == target_ord:
						cid_to_word[card.id] = w
						if card.queue != -1:
							active_cids.add(card.id)
					
		total_mass = get_total_frequency_mass()
		if not total_mass:
			self.lbl_status.setText("No frequency data available.")
			return

		# Fetch simplified review log: id, cid, ivl
		raw_reviews = col.db.all("SELECT id, cid, ivl FROM revlog ORDER BY id")
		
		# Filter for relevant reviews and determine start date
		relevant_reviews = []
		for r in raw_reviews:
			if r[1] in cid_to_word:
				relevant_reviews.append(r)
				
		if not relevant_reviews:
			self.lbl_status.setText("No Chinese reviews found.")
			return

		first_ts = relevant_reviews[0][0]
		start_day_idx = first_ts // 86400000
		
		# Simulation State
		# word_states: word -> { cid -> { 'ivl': int, 'last_seen': day_idx } }
		word_states = {}
		
		history_points = []
		
		rev_cursor = 0
		num_reviews = len(relevant_reviews)
		
		now_ts = int(time.time() * 1000)
		end_day_idx = now_ts // 86400000
		
		# Iterate days
		for day_idx in range(start_day_idx, end_day_idx + 1):
			day_limit_ms = (day_idx + 1) * 86400000
			
			# Process reviews for this day
			while rev_cursor < num_reviews:
				rid, cid, ivl = relevant_reviews[rev_cursor]
				if rid >= day_limit_ms:
					break
				
				rev_cursor += 1
				
				w = cid_to_word[cid]
				if w not in word_states:
					word_states[w] = {}
				
				# Logic:
				# ivl >= 1: Card is known/reviewing
				# ivl < 1: Card is in learning or re-learning (lapse)
				
				if ivl >= 1:
					word_states[w][cid] = {'ivl': ivl, 'last_seen': day_idx}
				else:
					# Card lapsed or is learning.
					if cid in word_states[w]:
						del word_states[w][cid]
						if not word_states[w]:
							del word_states[w]
			
			# Calculate Daily Stats
			day_basic_active_mass = 0.0
			day_weighted_active_mass = 0.0
			day_weighted_all_mass = 0.0
			
			# We only sum up words that have at least one valid card state
			for w, cards in word_states.items():
				if not cards: 
					continue
					
				w_mass = word_weights[w]
				
				# Check if active
				has_active = any(cid in active_cids for cid in cards)
				
				if has_active:
					day_basic_active_mass += w_mass
				
				# Retrievabilities
				max_r_active = 0.0
				max_r_all = 0.0
				
				for cid, c_state in cards.items():
					ivl = c_state['ivl']
					last_seen = c_state['last_seen']
					
					elapsed = day_idx - last_seen
					r_val = 0.0
					if ivl > 0:
						r_val = 0.9 ** (elapsed / float(ivl))
					
					if r_val > max_r_all:
						max_r_all = r_val
						
					if cid in active_cids:
						if r_val > max_r_active:
							max_r_active = r_val
				
				day_weighted_active_mass += w_mass * max_r_active
				day_weighted_all_mass += w_mass * max_r_all

			basic_pct = min(100.0, (day_basic_active_mass / total_mass) * 100)
			weighted_active_pct = min(100.0, (day_weighted_active_mass / total_mass) * 100)
			weighted_all_pct = min(100.0, (day_weighted_all_mass / total_mass) * 100)
			
			ts_display = day_idx * 86400 + 43200
			history_points.append((ts_display, basic_pct, weighted_active_pct, weighted_all_pct))
			
		self.graph.set_data(history_points)
		self.graph.setVisible(True)
		self.lbl_status.setVisible(False)


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

		btn_hist = QPushButton("View History")
		btn_hist.clicked.connect(self.open_history)
		controls_layout.addWidget(btn_hist)

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
		
		self.lbl_sim = QLabel("Simulate New:")
		controls_layout.addWidget(self.lbl_sim)
		self.spin_sim = QSpinBox()
		self.spin_sim.setRange(0, 5000)
		self.spin_sim.setSingleStep(50)
		self.spin_sim.setValue(0)
		self.spin_sim.valueChanged.connect(self.schedule_refresh)
		controls_layout.addWidget(self.spin_sim)

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

	def open_history(self):
		use_pronounce = self.check_pronounce.isChecked()
		card_type_mode = "hanzi-pronounce" if use_pronounce else "hanzi-define"
		dlg = HistoryDialog(self, card_type_mode)
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
		sim_new_count = self.spin_sim.value()

		self.spin_bucket.setVisible(not show_hsk)
		self.spin_max_rank.setVisible(not show_hsk)
		self.lbl_bucket.setVisible(not show_hsk)
		self.lbl_rank.setVisible(not show_hsk)
		# Simulation only makes sense in Frequency Rank mode usually, but can work for HSK too


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
			return max(val, 1e-9)

		# Simulate learning new words
		simulated_words = set()
		if sim_new_count > 0:
			all_sorted_words = get_all_words()
			count_added = 0
			for w_sim in all_sorted_words:
				if count_added >= sim_new_count:
					break
				if w_sim not in known and w_sim not in unreviewed_words:
					simulated_words.add(w_sim)
					count_added += 1

		total_mass = get_total_frequency_mass()
		basic_mass = sum(get_mass(w) for w in known)
		sim_mass = sum(get_mass(w) for w in simulated_words)
		
		# Assume simulated words are known with retrievability 0.9 (freshly learned)
		retrieval_mass = sum(get_mass(w) * (d['r'] or 0) for w, d in known.items())
		retrieval_mass_sim = retrieval_mass + (sim_mass * 0.9)

		basic_perc = (basic_mass / total_mass * 100) if total_mass else 0
		basic_perc_w_sim = ((basic_mass + sim_mass) / total_mass * 100) if total_mass else 0
		
		retrieval_perc = (retrieval_mass / total_mass * 100) if total_mass else 0
		retrieval_perc_sim = (retrieval_mass_sim / total_mass * 100) if total_mass else 0

		max_rank_found = 0
		
		bucket_counts = {}
		unreviewed_bucket_counts = {}
		simulated_bucket_counts = {}  
		
		# bucket stats: idx -> {stats}
		bucket_stats = {} 
		
		def get_bucket_stats(idx):
			if idx not in bucket_stats:
				bucket_stats[idx] = {'sum_r': 0.0, 'sum_s': 0.0, 'count_known': 0, 'mass_known': 0.0, 'mass_total': 0.0, 'mass_sim': 0.0}
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

			if simulated_words:
				for word in simulated_words:
					lvl = get_hsk_level(word)
					if lvl and 1 <= lvl <= 6:
						b_idx = lvl - 1
						s = get_bucket_stats(b_idx)
						simulated_bucket_counts[b_idx] = simulated_bucket_counts.get(b_idx, 0) + 1
						w_mass = get_mass(word)
						s['mass_sim'] += w_mass
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
			
			if simulated_words:
				for word in simulated_words:
					rank = get_frequency_rank(word)
					if rank:
						if rank <= max_rank_cutoff:
							b_idx = (rank - 1) // bucket_size
							s = get_bucket_stats(b_idx)
							simulated_bucket_counts[b_idx] = simulated_bucket_counts.get(b_idx, 0) + 1
							w_mass = get_mass(word)
							s['mass_sim'] += w_mass
							s['mass_total'] += w_mass

			total_buckets_needed = max_rank_cutoff // bucket_size
		
		data_list = [0] * total_buckets_needed
		unrev_list = [0] * total_buckets_needed
		sim_list = [0] * total_buckets_needed
		stats_list = []

		for idx in range(total_buckets_needed):
			count = bucket_counts.get(idx, 0)
			data_list[idx] = count
			
			unrev = unreviewed_bucket_counts.get(idx, 0)
			if show_unreviewed:
				unrev_list[idx] = unrev
				
			sim = simulated_bucket_counts.get(idx, 0)
			sim_list[idx] = sim
			
			s = bucket_stats.get(idx, {'sum_r':0, 'sum_s':0, 'count_known':0, 'mass_known':0, 'mass_total':0, 'mass_sim':0})
			c_known = s['count_known']
			avg_r = (s['sum_r'] / c_known) if c_known else 0
			avg_s = (s['sum_s'] / c_known) if c_known else 0
			cov_k = (s['mass_known'] / total_mass * 100) if total_mass else 0
			cov_t = (s['mass_total'] / total_mass * 100) if total_mass else 0
			cov_sim = (s['mass_sim'] / total_mass * 100) if total_mass else 0
			
			stats_list.append({
				'avg_retrievability': avg_r, 
				'avg_stability': avg_s,
				'coverage_known': cov_k,
				'coverage_total': cov_t,
				'coverage_sim': cov_sim
			})
		
		self.graph.set_data(data_list, unrev_list if show_unreviewed else None, sim_list, stats_list)
		
		info_text = (
			f"<h3>Stats for '{card_type}'</h3>"
			f"Basic estimated comprehension: <b>{basic_perc:.4f}%</b>"
		)
		
		if sim_new_count > 0:
			info_text += f" <span style='color:#9c27b0'>(+{basic_perc_w_sim - basic_perc:.4f}% -> {basic_perc_w_sim:.4f}%)</span>"
			
		info_text += f"<br>Retrievability-weighted: <b>{retrieval_perc:.4f}%</b>"
		
		if sim_new_count > 0:
			info_text += f" <span style='color:#9c27b0'>(+{retrieval_perc_sim - retrieval_perc:.4f}% -> {retrieval_perc_sim:.4f}%)</span>"
			
		info_text += f"<br>Based on <b>{len(known)}</b> words (+{len(simulated_words)} simulated)<br>"

		today_val = self._calc_todays_gain()
		
		info_text += f"Today's Net Interval Gain: <b>{today_val:+.0f} days</b><br>"
		
		if not show_hsk:
			info_text += f"Highest Rank Found: {max_rank_found} (Graph limited to {max_rank_cutoff})"
			
		self.stats_label.setText(info_text)

	def _calc_todays_gain(self):
		col = mw.col
		# Day cutoff in seconds * 1000 for ms
		day_start_ms = (col.sched.day_cutoff - 86400) * 1000
		
		chinese_cids = set(col.find_cards("note:chinese-word"))
		if not chinese_cids:
			return 0.0

		reviews = col.db.all(f"SELECT cid, ivl, lastIvl FROM revlog WHERE id > {day_start_ms}")
		
		total_gain = 0.0
		
		for (cid, ivl, last_ivl) in reviews:
			if cid not in chinese_cids:
				continue
			
			def to_days(val):
				if val < 0: return abs(val) / 86400.0
				return float(val)
				
			total_gain += (to_days(ivl) - to_days(last_ivl))
			
		return total_gain


def on_info():
	mw.chinese_info_dialog = ChineseInfoDialog(mw)
	mw.chinese_info_dialog.exec()

def on_card_will_show(card):
	if card.note_type()['name'] != "chinese-word":
		return
	_pre_review_ivl[card.id] = card.ivl


def on_card_reviewed(reviewer, card, ease):
	if card.note_type()['name'] != "chinese-word":
		return
	note = card.note()
	word = note['word']
	freq_weight = get_frequency_weight(word) or 0
	stats = mw.col.card_stats_data(card.id)
	r_after = getattr(stats, 'fsrs_retrievability', 0.0)

	global _pre_review_ivl
	ivl_before = _pre_review_ivl.get(card.id, 0)
	_pre_review_ivl[card.id] = card.ivl

	def to_days(val):
		if val < 0: return abs(val) / 86400.0
		return float(val)

	delta_days = to_days(card.ivl) - to_days(ivl_before)
	
	global _session_gain
	_session_gain += delta_days
	
	total_mass = get_total_frequency_mass()
	if total_mass:
		global _last_retrievabilities
		r_before = _last_retrievabilities.get(card.id, 0.0)
		_last_retrievabilities[card.id] = r_after
		
		delta = freq_weight * (r_after - r_before)
		comprehension_change = delta / total_mass
		comprehension_change = max(comprehension_change, 0.0000000001)
		
		tooltip(f"Comprehension change: 1 / {readable_number(1 / comprehension_change)}<br>Days Gained: {delta_days:+.0f} (Session: {_session_gain:+.0f})")

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

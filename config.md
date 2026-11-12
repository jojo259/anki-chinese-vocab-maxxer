# Chinese Vocab Maxxer

**Simulation spread** (`graph_simulation_spread`, 0–100, default `0`): 0% selects the next unknown words in frequency order. Higher values spread the selection across later ranks in the full frequency list. The setting is remembered when the info window closes.

**Group by** supports Frequency, HSK level, and Frequency level. Frequency level shows complete levels 1–6 (ranks 1–6,300), using 100, 200, 400, 800, 1,600, and 3,200 words as the respective level totals. The grouping is remembered when the info window closes.

**Auto square cells** (`graph_auto_square_cells`, default `false`): automatically adjusts bucket size using the plot dimensions so each word occupies an approximately square cell. Available in Frequency grouping; manual bucket editing is disabled while enabled. Resizing regroups cached data without extra collection queries. The setting is remembered when the info window closes.

**Introduced-word warning**: when reviewing a new card, a centered red banner appears if another note with the same `word` field has a recorded answer, across all decks and note types containing that field. Unintroduced copies and cards from the same note do not trigger it. HTML and surrounding whitespace are ignored when matching words. The link opens the matching introduced notes in Browse; it does not alter notes, cards, or scheduling. Introduction data is cached while reviewing, updated after answers, and invalidated after edits, undo, or profile changes.

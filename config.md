# Chinese Vocab Maxxer

**Simulation spread** (`graph_simulation_spread`, 0–100, default `0`): 0% selects the next unknown words in frequency order. Higher values spread the selection across later ranks in the full frequency list. The setting is remembered when the info window closes.

**Group by** supports Frequency, HSK level, and Frequency level. Frequency level shows complete levels 1–6 (ranks 1–6,300), using 100, 200, 400, 800, 1,600, and 3,200 words as the respective level totals. The grouping is remembered when the info window closes.

**Auto square cells** (`graph_auto_square_cells`, default `false`): automatically adjusts bucket size using the plot dimensions so each word occupies an approximately square cell. Available in Frequency grouping; manual bucket editing is disabled while enabled. Resizing regroups cached data without extra collection queries. The setting is remembered when the info window closes.

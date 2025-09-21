from typing import TYPE_CHECKING, Any
from translations import translate

if TYPE_CHECKING:
    from tksheet import Sheet
    sheet: 'Sheet'
    visible_columns: list[str]
    checkbox_states: dict[int, bool]
    delete_button: Any
    filter_button: Any
    row_to_path_map: dict[int, str]

class SelectionMixin:
    """Gestion des cases à cocher et opérations de sélection."""
    def _init_selection_state(self):
        self.checkbox_states = {}
        self.toggle_flac_state = True
        self.toggle_bitrate_state = True
        self.filter_mode = True

    # ---- Helpers internes ----
    def _set_checkbox(self, row, value):
        self.checkbox_states[row] = bool(value)
        try:
            col = self._select_column_index()
            self.sheet.set_cell_data(row, col, "✔" if value else "")
        except Exception:
            pass

    def _toggle_checkbox(self, row):
        self._set_checkbox(row, not self.checkbox_states.get(row, False))
        self.update_delete_button()

    def _set_row_checkbox(self, row, value):
        if row is None:
            return
        self._set_checkbox(row, value)
        self.update_delete_button()

    def _set_group_checkbox(self, group_val, value):
        if "group" not in self.visible_columns:
            return
        g_idx = self.visible_columns.index("group")
        for r, row_data in enumerate(self.sheet.get_sheet_data()):
            if row_data and row_data[g_idx] == group_val:
                self._set_checkbox(r, value)
        self.update_delete_button()

    # ---- Opérations utilisateur ----
    def update_delete_button(self):
        count = sum(1 for v in self.checkbox_states.values() if v)
        try:
            lang = getattr(self, 'language', 'fr')
            label = translate(lang, 'ui.trash_btn', count=count)
            self.delete_button.config(state='normal' if count else 'disabled', text=label)
        except Exception:
            pass

    def select_rows_selection(self):
        try:
            for r in self.sheet.get_selected_rows():
                self._set_checkbox(r, True)
            self.update_delete_button()
        except Exception:
            pass

    def deselect_rows_selection(self):
        try:
            for r in self.sheet.get_selected_rows():
                self._set_checkbox(r, False)
            self.update_delete_button()
        except Exception:
            pass

    def invert_rows_selection(self):
        try:
            selected = list(self.sheet.get_selected_rows())
        except Exception:
            selected = []
        if not selected:
            try:
                cur = self.sheet.get_currently_selected()
                if isinstance(cur, tuple) and len(cur) >= 1:
                    selected = [int(cur[0])]
            except Exception:
                pass
        for r in selected:
            self._set_checkbox(r, not self.checkbox_states.get(r, False))
        self.update_delete_button()

    def select_all_flac_files(self):
        if "path" not in self.visible_columns:
            return
        p_idx = self.visible_columns.index("path")
        for r, row in enumerate(self.sheet.get_sheet_data()):
            if row and str(row[p_idx]).lower().endswith('.flac'):
                self._set_checkbox(r, self.toggle_flac_state)
        self.toggle_flac_state = not self.toggle_flac_state
        self.update_delete_button()

    def toggle_highest_bitrate_per_group(self):
        # Besoin colonnes présentes
        needed = ["group", "bitrate", "date"]
        if not all(c in self.visible_columns for c in needed):
            return
        g_idx = self.visible_columns.index("group")
        b_idx = self.visible_columns.index("bitrate")
        d_idx = self.visible_columns.index("date")
        group_map = {}
        for r, row in enumerate(self.sheet.get_sheet_data()):
            if not row:
                continue
            group_map.setdefault(row[g_idx], []).append((r, row))
        for rows in group_map.values():
            max_bitrate = -1; max_rows = []
            for r, row in rows:
                try:
                    br = int(row[b_idx])
                except Exception:
                    br = 0
                if br > max_bitrate:
                    max_bitrate = br; max_rows = [(r, row)]
                elif br == max_bitrate:
                    max_rows.append((r, row))
            # parmi les meilleurs, garder le plus ancien (date min)
            min_date = float('inf'); ref_row = None
            for r, row in max_rows:
                try:
                    import datetime
                    dt = datetime.datetime.strptime(row[d_idx], '%Y-%m-%d %H:%M:%S').timestamp()
                except Exception:
                    dt = 0
                if dt < min_date:
                    min_date, ref_row = dt, r
            for r, _ in rows:
                keep = (r == ref_row)
                self._set_checkbox(r, (r != ref_row) if self.toggle_bitrate_state else keep)
        self.toggle_bitrate_state = not self.toggle_bitrate_state
        self.update_delete_button()

    def toggle_current_group(self):
        if "group" not in self.visible_columns:
            return
        g_idx = self.visible_columns.index("group")
        row = None
        try:
            cur = self.sheet.get_currently_selected(); row = int(cur[0]) if cur else None
        except Exception:
            pass
        if row is None:
            try:
                sel = list(self.sheet.get_selected_rows())
                if sel:
                    row = sel[0]
            except Exception:
                pass
        if row is None:
            return
        try:
            g_val = self.sheet.get_cell_data(row, g_idx)
        except Exception:
            return
        group_rows = [r for r, rd in enumerate(self.sheet.get_sheet_data()) if rd and rd[g_idx] == g_val]
        if not group_rows:
            return
        any_unchecked = any(not self.checkbox_states.get(r, False) for r in group_rows)
        new_state = True if any_unchecked else False
        for r in group_rows:
            self._set_checkbox(r, new_state)
        self.update_delete_button()

    def toggle_filter_selection(self):
        # Basculer mode plus vieux/plus récent
        mode = self.filter_mode
        self.filter_mode = not self.filter_mode
        try:
            lang = getattr(self, 'language', 'fr')
            self.filter_button.config(text=translate(lang, 'ui.filter_newest' if not mode else 'ui.filter_oldest'))
        except Exception:
            pass
        if not all(c in self.visible_columns for c in ("group", "date")):
            return
        g_idx = self.visible_columns.index("group")
        d_idx = self.visible_columns.index("date")
        group_map = {}
        for r, row in enumerate(self.sheet.get_sheet_data()):
            if not row:
                continue
            group_map.setdefault(row[g_idx], []).append((r, row))
        import datetime
        for rows in group_map.values():
            best_row = None; best_date = None
            for r, row in rows:
                try:
                    dt = datetime.datetime.strptime(row[d_idx], '%Y-%m-%d %H:%M:%S').timestamp()
                except Exception:
                    dt = 0
                if best_date is None or (mode and dt < best_date) or (not mode and dt > best_date):
                    best_date, best_row = dt, r
            for r, _ in rows:
                self._set_checkbox(r, r != best_row)
        self.update_delete_button()

    # ---- Collecte ----
    def get_selected_files(self):
        return [self.row_to_path_map[i] for i, v in self.checkbox_states.items() if v and i in self.row_to_path_map]

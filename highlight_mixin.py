from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tksheet import Sheet

class HighlightMixin:
    """Mise en évidence des différences intra-groupe."""
    # Attributs fournis par l'application principale / autres mixins
    sheet: 'Sheet'
    visible_columns: list[str]
    row_metadata: list[dict]
    dynamic_group_reference: dict[str, int]
    highlight_differences: bool
    checkbox_states: dict[int, bool]
    status_label: Any

    def _init_highlight_state(self):
        self.highlight_differences = True
        self.row_metadata = []
        self.dynamic_group_reference = {}
        self.debug_mode = False

    def toggle_highlight_differences(self):
        self.highlight_differences = not self.highlight_differences
        if not self.highlight_differences:
            self._clear_difference_highlighting()
        else:
            self._apply_difference_highlighting()

    def _set_dynamic_reference_from_row(self, row):
        if row is None or "group" not in self.visible_columns:
            return
        try:
            g_idx = self.visible_columns.index("group")
            g_val = self.sheet.get_cell_data(row, g_idx)
            if g_val:
                self.dynamic_group_reference[g_val] = row
                self._apply_difference_highlighting()
        except Exception:
            pass

    def _clear_difference_highlighting(self):
        try:
            keys = ["title", "artist", "album", "bitrate", "duration"]
            indices = [self.visible_columns.index(k) for k in keys if k in self.visible_columns]
            for r in range(len(self.sheet.get_sheet_data())):
                for c in indices:
                    try:
                        self.sheet.highlight_cells(row=r, column=c, fg='black', redraw=False)
                    except Exception:
                        pass
            self.sheet.redraw()
        except Exception:
            pass

    def _apply_difference_highlighting(self):
        if not (self.highlight_differences and self.row_metadata and "group" in self.visible_columns):
            return
        try:
            keys = ["title", "artist", "album", "bitrate", "duration"]
            key_to_col = {k: self.visible_columns.index(k) for k in keys if k in self.visible_columns}
            # reset couleurs
            for r in range(len(self.sheet.get_sheet_data())):
                for col in key_to_col.values():
                    try:
                        self.sheet.highlight_cells(row=r, column=col, fg='black', redraw=False)
                    except Exception:
                        pass
            # regrouper
            groups = {}
            for r, meta in enumerate(self.row_metadata):
                g = meta.get('group')
                groups.setdefault(g, {"rows": [], "ref": None})
                groups[g]["rows"].append(r)
                if meta.get('is_reference'):
                    groups[g]["ref"] = r
            for g, info in groups.items():
                rows = info['rows']
                if not rows:
                    continue
                dyn = self.dynamic_group_reference.get(g)
                ref_row = dyn if (dyn in rows) else (info.get('ref') if info.get('ref') is not None else rows[0])
                ref_vals = self.row_metadata[ref_row].get('values', {})
                for r in rows:
                    if r == ref_row:
                        continue
                    row_vals = self.row_metadata[r].get('values', {})
                    for k, col in key_to_col.items():
                        rv = row_vals.get(k, ""); rf = ref_vals.get(k, "")
                        if k == 'bitrate':
                            try:
                                diff = int(rv) != int(rf)
                            except Exception:
                                diff = rv != rf
                        else:
                            diff = str(rv).strip().lower() != str(rf).strip().lower()
                        if diff:
                            try:
                                self.sheet.highlight_cells(row=r, column=col, fg='red', redraw=False)
                            except Exception:
                                pass
            try:
                self.sheet.redraw()
            except Exception:
                pass
        except Exception:
            pass

    # Debug helpers
    def _toggle_debug(self):
        self.debug_mode = not self.debug_mode
        try:
            self.status_label.config(text=f"Mode debug {'ON' if self.debug_mode else 'OFF'}")
        except Exception:
            pass

    def _debug_show_selection_values(self):
        try:
            col = self._select_column_index()
            lines = []
            for r in range(min(50, len(self.sheet.get_sheet_data()))):
                try:
                    cell = self.sheet.get_cell_data(r, col)
                except Exception:
                    cell = None
                internal = self.checkbox_states.get(r, False)
                lines.append(f"{r}: cell={cell!r} internal={int(bool(internal))}")
            from tkinter import messagebox
            messagebox.showinfo("Debug sélection", "\n".join(lines) if lines else "(vide)")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Debug erreur", str(e))

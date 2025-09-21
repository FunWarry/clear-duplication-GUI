import datetime
from translations import translate

class DataManagerMixin:
    """Construction et rafraîchissement des données affichées dans la feuille."""
    def _init_data_state(self):
        self.all_groups = []
        self.row_to_path_map = {}
        self.hidden_items = set()

    def clear_results_data(self):
        self.all_groups = []
        self.hidden_items.clear()
        self.row_to_path_map.clear()
        if hasattr(self, 'checkbox_states'):
            self.checkbox_states.clear()
        if hasattr(self, 'row_metadata'):
            self.row_metadata.clear()
        if hasattr(self, 'dynamic_group_reference'):
            self.dynamic_group_reference.clear()
        try:
            self.sheet.set_sheet_data([[]])
        except Exception:
            pass
        try:
            self.update_delete_button()
        except Exception:
            pass
        try:
            self.status_label.config(text=translate(getattr(self,'language','fr'),'ui.ready'))
        except Exception:
            pass

    def redisplay_results(self, preserve_selection=True):
        selected_paths = set()
        if preserve_selection:
            try:
                for row_idx, is_checked in enumerate(self.sheet.get_column_data(0)):
                    if is_checked and row_idx in self.row_to_path_map:
                        selected_paths.add(self.row_to_path_map[row_idx])
            except Exception:
                pass
        self.sheet.set_sheet_data([[]])
        self.row_to_path_map.clear()
        if hasattr(self, 'row_metadata'):
            self.row_metadata.clear()
        if hasattr(self, 'dynamic_group_reference'):
            self.dynamic_group_reference.clear()
        if not self.all_groups:
            try: self.update_delete_button()
            except Exception: pass
            return
        filter_query = self.filter_var.get().lower()
        keep_type = self.keep_type_var.get()
        duration_similarity = getattr(self, 'duration_similarity_var', None)
        duration_similarity = (duration_similarity.get() / 100.0) if duration_similarity else 0.95
        data_matrix = []
        any_duration = False
        group_id = 1
        new_states = {}
        current_row = 0
        lang = getattr(self, 'language', 'fr')
        group_prefix = translate(lang, 'group.prefix')
        for group in self.all_groups:
            durations = [f.get('duration', 0) or 0 for f in group]
            if durations:
                min_d = min(durations); max_d = max(durations)
                ratio = min(min_d, max_d) / max(max_d, min_d) if max_d and min_d else 1.0
                if ratio < duration_similarity:
                    continue
            group.sort(key=lambda f: f.get('bitrate', 0), reverse=True)
            group.sort(key=lambda f: f['date'])
            file_to_keep = group[-1] if keep_type == 'recent' else group[0]
            group_label = f"{group_prefix} {group_id}"
            for info in group:
                path = info['path']
                if path in self.hidden_items:
                    continue
                if filter_query and not any(
                        filter_query in str(info.get(k, '')).lower() for k in ('title', 'artist', 'album', 'path')
                ):
                    continue
                self.row_to_path_map[current_row] = path
                if getattr(self, 'folder_paths', None):
                    try:
                        base = self.folder_paths[0]
                        display_path = os.path.relpath(path, os.path.dirname(base))
                    except Exception:
                        display_path = path
                else:
                    display_path = path
                date_str = datetime.datetime.fromtimestamp(info['date']).strftime('%Y-%m-%d %H:%M:%S')
                is_dup = (info != file_to_keep)
                checked = is_dup if not selected_paths else (path in selected_paths)
                dur_sec = info.get('duration', 0) or 0
                any_duration = any_duration or (dur_sec > 0)
                dur_str = f"{int(dur_sec // 60)}:{int(dur_sec % 60):02d}" if dur_sec > 0 else '-'
                row_values = {
                    'select': '✔' if checked else '', 'title': info.get('title', 'N/A'),
                    'artist': info.get('artist', 'N/A'), 'album': info.get('album', 'N/A'),
                    'bitrate': info.get('bitrate', 0), 'duration': dur_str, 'path': display_path,
                    'group': group_label, 'date': date_str
                }
                data_matrix.append([row_values[c] for c in self.visible_columns])
                new_states[current_row] = bool(checked)
                if hasattr(self, 'row_metadata'):
                    self.row_metadata.append({
                        'group': group_label, 'is_reference': (info == file_to_keep),
                        'values': {
                            'title': info.get('title', '') or '', 'artist': info.get('artist', '') or '',
                            'album': info.get('album', '') or '', 'bitrate': info.get('bitrate', 0) or 0,
                            'duration': dur_str
                        }
                    })
                current_row += 1
            group_id += 1
        self.sheet.set_sheet_data(data_matrix, reset_col_positions=True, reset_row_positions=True)
        try: self._apply_readonly_except_select()
        except Exception: pass
        if hasattr(self, 'checkbox_states'):
            self.checkbox_states = new_states
        if not any_duration and 'duration' in self.visible_columns:
            try: self.status_label.config(text=translate(lang,'msg.no_duration'))
            except Exception: pass
        try: self.update_delete_button()
        except Exception: pass
        try: self._apply_difference_highlighting()
        except Exception: pass

import os  # placé en bas pour ne pas polluer espace global avant définition

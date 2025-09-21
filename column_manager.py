import os, datetime, json
from typing import TYPE_CHECKING, Any
from translations import translate

if TYPE_CHECKING:  # Aide pour l'analyse statique uniquement
    from tksheet import Sheet
    sheet: 'Sheet'
    visible_columns: list[str]
    all_columns: list[str]
    column_names: dict[str, str]
    debug_mode: bool
    status_label: Any
    def redisplay_results(*args, **kwargs): ...

class ColumnManagerMixin:
    """Gestion de la configuration des colonnes (ordre, visibilité, persistance + largeurs + langue)."""
    def _init_columns(self):
        # Langue par défaut
        self.language = getattr(self, 'language', 'fr')
        self.all_columns = ["select", "title", "artist", "album", "bitrate", "duration", "path", "group", "date"]
        if not hasattr(self, 'visible_columns') or not self.visible_columns:
            self.visible_columns = list(self.all_columns)
        self.config_path = os.path.join(os.path.dirname(__file__), "column_config.json")
        self._loaded_column_widths: dict[str, int] = {}
        self._save_layout_after_id = None
        # Chargement config (peut définir language + colonnes visibles + largeurs)
        try:
            self.load_column_config()
        except Exception:
            pass
        # Construire noms colonnes selon langue (après load)
        self._build_column_names()

    def _build_column_names(self):
        self.column_names = {
            'select': translate(self.language, 'col.select'),
            'title': translate(self.language, 'col.title'),
            'artist': translate(self.language, 'col.artist'),
            'album': translate(self.language, 'col.album'),
            'bitrate': translate(self.language, 'col.bitrate'),
            'duration': translate(self.language, 'col.duration'),
            'path': translate(self.language, 'col.path'),
            'group': translate(self.language, 'col.group'),
            'date': translate(self.language, 'col.date'),
        }

    def set_language(self, lang: str):
        if lang == self.language:
            return
        self.language = lang
        self._build_column_names()
        # Réappliquer en-têtes + sauver config
        try:
            self._apply_visible_columns()
        except Exception:
            pass
        try:
            if hasattr(self, '_apply_language_texts'):
                self._apply_language_texts()
        except Exception:
            pass

    # ---- Helpers colonnes ----
    def _select_column_index(self):
        try:
            headers = self.sheet.headers()
            label = self.column_names.get("select", translate(self.language, 'col.select'))
            if label in headers:
                return headers.index(label)
        except Exception:
            pass
        return 0

    def _apply_readonly_except_select(self):
        try:
            if not hasattr(self.sheet, 'headers'):
                return
            headers = self.sheet.headers()
            select_header = self.column_names.get("select", translate(self.language, 'col.select'))
            if not hasattr(self.sheet, 'column_options'):
                return
            for idx, header in enumerate(headers):
                try:
                    self.sheet.column_options(idx, readonly= not (header == select_header))
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_visible_columns(self):
        if 'select' not in self.visible_columns:
            self.visible_columns.insert(0, 'select')
        if len(self.visible_columns) < 2 and len(self.all_columns) > 1:
            for c in self.all_columns:
                if c != 'select' and c not in self.visible_columns:
                    self.visible_columns.append(c)
                    break
        try:
            self.sheet.headers([self.column_names.get(c, c) for c in self.visible_columns])
        except Exception:
            pass
        self._apply_column_widths()
        self.save_column_config()
        self.redisplay_results()

    # ---- Largeurs ----
    def _gather_current_widths(self) -> dict[str, int]:
        widths: dict[str, int] = {}
        if not hasattr(self, 'sheet'):
            return widths
        try:
            for idx, key in enumerate(self.visible_columns):
                w = None
                try:
                    # API probable tksheet
                    w = self.sheet.column_width(idx)
                except Exception:
                    try:
                        if hasattr(self.sheet, 'get_column_widths'):
                            wlist = self.sheet.get_column_widths(); w = wlist[idx] if idx < len(wlist) else None
                    except Exception:
                        w = None
                if isinstance(w, int) and w > 0:
                    widths[key] = w
        except Exception:
            pass
        return widths

    def _apply_column_widths(self):
        if not self._loaded_column_widths:
            return
        try:
            for idx, key in enumerate(self.visible_columns):
                if key in self._loaded_column_widths:
                    try:
                        self.sheet.column_width(idx, self._loaded_column_widths[key])
                    except Exception:
                        pass
        except Exception:
            pass

    def _rebuild_visible_columns_from_headers(self):
        """Après un drag & drop manuel, reconstruire l'ordre interne à partir des en-têtes affichés."""
        try:
            headers = self.sheet.headers()
        except Exception:
            return
        new_order = []
        rev = {v: k for k, v in self.column_names.items()}
        for h in headers:
            key = rev.get(h)
            if key:
                new_order.append(key)
        if 'select' in new_order:
            new_order = ['select'] + [c for c in new_order if c != 'select']
        if new_order and new_order != self.visible_columns:
            self.visible_columns = new_order

    def _schedule_save_layout(self):
        # Eviter de sauvegarder trop souvent lors de glisser répété
        try:
            if self._save_layout_after_id is not None:
                self.after_cancel(self._save_layout_after_id)
        except Exception:
            pass
        try:
            self._save_layout_after_id = self.after(400, self._persist_layout_now)
        except Exception:
            # fallback immédiat
            self._persist_layout_now()

    def _persist_layout_now(self):
        self._save_layout_after_id = None
        # Re-capturer l'ordre réel (au cas où drag) et largeurs
        self._rebuild_visible_columns_from_headers()
        self.save_column_config()

    def _on_sheet_layout_changed(self, *_):
        # Appelé sur resize ou move -> planifier sauvegarde
        self._schedule_save_layout()

    def install_column_layout_tracking(self):
        """À appeler après création de la sheet pour suivre déplacements / redimensionnements."""
        if not hasattr(self, 'sheet'):
            return
        try:
            # Les events exacts dépendent de tksheet: on capture largeurs et déplacements en fin d'action
            for evt in ("column_width_resize", "end_move_columns", "end_column_header_drag_drop"):
                try:
                    self.sheet.extra_bindings(evt, self._on_sheet_layout_changed)
                except Exception:
                    pass
        except Exception:
            pass

    # ---- Persistance ----
    def save_column_config(self):
        try:
            data = {
                "visible_columns": self.visible_columns,
                "column_widths": self._gather_current_widths(),
                "timestamp": datetime.datetime.now().isoformat(),
                "version": 1,
                "language": self.language,
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            if getattr(self, 'debug_mode', False):
                self.status_label.config(text="Echec sauvegarde colonnes")

    def load_column_config(self):
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            lang = data.get('language')
            if isinstance(lang, str) and lang in ('fr', 'en'):
                self.language = lang
            cols = [c for c in data.get('visible_columns', []) if c in self.all_columns]
            if cols:
                if 'select' in cols:
                    cols = ['select'] + [c for c in cols if c != 'select']
                else:
                    cols.insert(0, 'select')
                self.visible_columns = cols
            widths = data.get('column_widths', {})
            if isinstance(widths, dict):
                self._loaded_column_widths = {k: int(v) for k, v in widths.items() if k in self.all_columns}
        except Exception:
            if getattr(self, 'debug_mode', False):
                self.status_label.config(text="Echec chargement colonnes")

    def reset_columns(self):
        self.visible_columns = list(self.all_columns)
        if 'select' in self.visible_columns:
            self.visible_columns.remove('select')
            self.visible_columns.insert(0, 'select')
        self._apply_visible_columns()

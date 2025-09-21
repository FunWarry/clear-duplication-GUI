import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tksheet
from translations import translate

from column_manager import ColumnManagerMixin
from selection_mixin import SelectionMixin
from highlight_mixin import HighlightMixin
from data_manager import DataManagerMixin
from scan_mixin import ScanMixin
from deletion_mixin import DeletionMixin
from folders_mixin import FoldersMixin

class DuplicateMusicFinder(tk.Tk,
                           ColumnManagerMixin,
                           SelectionMixin,
                           HighlightMixin,
                           DataManagerMixin,
                           ScanMixin,
                           DeletionMixin,
                           FoldersMixin):
    """Application principale (version refactorisée en mixins)."""
    def __init__(self):
        super().__init__()
        self.language = 'fr'  # défaut si config absente
        # Titre provisoire avant chargement config -> sera remplacé par _apply_language_texts
        self.title(translate(self.language, 'app.title'))
        self.geometry("1400x800")
        # Etats de base
        self.keep_type_var = tk.StringVar(value="recent")
        self.filter_var = tk.StringVar()
        self.similarity_var = tk.IntVar(value=80)
        self.duration_similarity_var = tk.IntVar(value=95)
        self.audio_player_path = None

        # Initialiser sous-systèmes
        self._init_columns()
        self._init_selection_state()
        self._init_highlight_state()
        self._init_data_state()
        self._init_scan_state()
        self._init_folders_state()

        # UI
        self._create_menu()
        self._create_widgets()
        self._apply_language_texts()

        # Observers
        self.filter_var.trace_add("write", lambda *_: self.redisplay_results())

        # Raccourcis globaux
        self.bind("<Control-e>", lambda e: self.select_rows_selection())
        self.bind("<Control-d>", lambda e: self.deselect_rows_selection())
        self.bind("<Control-i>", lambda e: self.invert_rows_selection())
        self.bind("<Control-g>", lambda e: self.toggle_current_group())

    # ================== Langue / Menus ==================
    def _create_menu(self):
        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)
        self.options_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=translate(self.language, 'menu.options'), menu=self.options_menu)
        self.options_menu.add_command(label=translate(self.language, 'menu.choose_player'), command=self.choose_audio_player)
        self._highlight_var = tk.BooleanVar(value=self.highlight_differences)
        self.options_menu.add_checkbutton(label=translate(self.language, 'menu.highlight_diff'),
                                          variable=self._highlight_var,
                                          onvalue=True, offvalue=False,
                                          command=self.toggle_highlight_differences)
        self.options_menu.add_separator()
        self.options_menu.add_command(label=translate(self.language, 'menu.reset_columns'), command=self.reset_columns)
        # Sous-menu langue
        self.language_var = tk.StringVar(value=self.language)
        self.lang_menu = tk.Menu(self.options_menu, tearoff=0)
        for code, label in [('fr', 'Français'), ('en', 'English')]:
            self.lang_menu.add_radiobutton(label=label, value=code, variable=self.language_var,
                                           command=lambda c=code: self.set_language(c))
        self.options_menu.add_separator()
        self.options_menu.add_cascade(label=translate(self.language, 'menu.language'), menu=self.lang_menu)

    def _rebuild_menus(self):
        # Supprimer menubar et recréer
        try:
            self.config(menu=None)
        except Exception:
            pass
        self._create_menu()

    def _apply_language_texts(self):
        lang = self.language
        # Met à jour le titre de l'application
        try:
            self.title(translate(lang, 'app.title'))
        except Exception:
            pass
        # Met à jour titres / labels / boutons
        try:
            self.folder_label.config(text=translate(lang, 'ui.folders_label'))
        except Exception: pass
        try:
            self.add_folder_btn.config(text=translate(lang, 'ui.add_folder'))
            self.add_folders_btn.config(text=translate(lang, 'ui.add_folders'))
            self.remove_folder_btn.config(text=translate(lang, 'ui.remove_folder'))
        except Exception: pass
        try:
            self.similarity_frame.config(text=translate(lang, 'ui.similarity_frame'))
            self.similarity_hint.config(text=translate(lang, 'ui.similarity_hint'))
            self.duration_frame.config(text=translate(lang, 'ui.duration_frame'))
            self.duration_hint.config(text=translate(lang, 'ui.duration_hint'))
        except Exception: pass
        try:
            self.scan_button.config(text=translate(lang, 'ui.scan'))
        except Exception: pass
        try:
            self.filter_results_label.config(text=translate(lang, 'ui.filter_results'))
        except Exception: pass
        try:
            self.select_flac_btn.config(text=translate(lang, 'ui.select_all_flac'))
            self.toggle_bitrate_btn.config(text=translate(lang, 'ui.toggle_highest_bitrate'))
            # Filtre bouton selon mode actuel
            self.filter_button.config(text=translate(lang, 'ui.filter_oldest' if self.filter_mode else 'ui.filter_newest'))
        except Exception: pass
        try:
            self.status_label.config(text=translate(lang, 'ui.ready'))
        except Exception: pass
        # Bouton corbeille via update_delete_button (recalcule le texte)
        try:
            self.update_delete_button()
        except Exception: pass
        # Menus
        self._rebuild_menus()

    # ================== Widgets ==================
    def _create_widgets(self):
        lang = self.language
        # Dossiers
        top = tk.Frame(self); top.pack(fill="x", padx=10, pady=5)
        self.folder_label = tk.Label(top, text=translate(lang,'ui.folders_label'))
        self.folder_label.pack(side="left")
        self.folder_listbox = tk.Listbox(top, height=4)
        self.folder_listbox.pack(side="left", fill="x", expand=True, padx=5)
        fb = tk.Frame(top); fb.pack(side="left", padx=5)
        self.add_folder_btn = tk.Button(fb, text=translate(lang,'ui.add_folder'), command=self.add_folder)
        self.add_folder_btn.pack(fill="x", pady=2)
        self.add_folders_btn = tk.Button(fb, text=translate(lang,'ui.add_folders'), command=self.add_multiple_folders)
        self.add_folders_btn.pack(fill="x", pady=2)
        self.remove_folder_btn = tk.Button(fb, text=translate(lang,'ui.remove_folder'), command=self.remove_folder)
        self.remove_folder_btn.pack(fill="x", pady=2)

        # Options
        opt = tk.Frame(self); opt.pack(fill="x", padx=10, pady=5)
        self.similarity_frame = tk.LabelFrame(opt, text=translate(lang,'ui.similarity_frame'))
        self.similarity_frame.pack(side="left", padx=5)
        tk.Scale(self.similarity_frame, from_=50, to=100, orient="horizontal", variable=self.similarity_var, resolution=1).pack(anchor="w")
        self.similarity_hint = tk.Label(self.similarity_frame, text=translate(lang,'ui.similarity_hint'))
        self.similarity_hint.pack(anchor="w")
        self.duration_frame = tk.LabelFrame(opt, text=translate(lang,'ui.duration_frame'))
        self.duration_frame.pack(side="left", padx=5)
        tk.Scale(self.duration_frame, from_=80, to=100, orient="horizontal", variable=self.duration_similarity_var, resolution=1,
                 command=lambda e: self.redisplay_results()).pack(anchor="w")
        self.duration_hint = tk.Label(self.duration_frame, text=translate(lang,'ui.duration_hint'))
        self.duration_hint.pack(anchor="w")
        self.scan_button = tk.Button(opt, text=translate(lang,'ui.scan'), command=self.start_scan_thread)
        self.scan_button.pack(side="left", padx=20, ipady=8)

        # Progression
        pf = tk.Frame(self); pf.pack(fill="x", padx=10, pady=5)
        self.status_label = tk.Label(pf, text=translate(lang,'ui.ready'))
        self.status_label.pack(side="left")
        self.progress_bar = ttk.Progressbar(pf, orient="horizontal", mode="determinate")
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=6)

        # Filtre texte
        ff = tk.Frame(self); ff.pack(fill="x", padx=10, pady=(5, 0))
        self.filter_results_label = tk.Label(ff, text=translate(lang,'ui.filter_results'))
        self.filter_results_label.pack(side="left")
        tk.Entry(ff, textvariable=self.filter_var).pack(side="left", fill="x", expand=True, padx=5)

        # Table
        table_frame = tk.Frame(self); table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.sheet = tksheet.Sheet(
            table_frame,
            headers=[self.column_names.get(c, c) for c in self.visible_columns],
            show_row_index=False,
            show_header=True
        )
        self.sheet.enable_bindings(
            "single_select", "row_select", "column_select", "drag_select", "rc_select", "arrowkeys",
            "column_drag_and_drop", "column_width_resize"
        )
        self.sheet.pack(fill="both", expand=True)
        # Activer suivi déplacements / redimensionnements + appliquer largeurs persistées
        try:
            self.install_column_layout_tracking()
            self._apply_column_widths()
        except Exception:
            pass

        # Bindings
        self.sheet.extra_bindings("cell_clicked", self._on_cell_clicked)
        self.sheet.extra_bindings("cell_rclick", self._on_cell_right_click)
        self.sheet.extra_bindings("header_rclick", self._on_header_right_click)
        self.sheet.bind("<Button-3>", self._on_any_right_click)
        self.sheet.bind("<Double-1>", self._on_native_double_click)
        self.sheet.bind("<space>", self._on_space_toggle)
        self.sheet.bind("<Control-i>", lambda e: self.invert_rows_selection())
        self.sheet.bind("<Control-g>", lambda e: self.toggle_current_group())

        self._apply_readonly_except_select()

        # Bas
        bottom = tk.Frame(self); bottom.pack(fill="x", pady=10)
        sf = tk.Frame(bottom); sf.pack(side="left")
        self.select_flac_btn = tk.Button(sf, text=translate(lang,'ui.select_all_flac'), command=self.select_all_flac_files)
        self.select_flac_btn.pack(side="left", padx=5)
        self.toggle_bitrate_btn = tk.Button(sf, text=translate(lang,'ui.toggle_highest_bitrate'), command=self.toggle_highest_bitrate_per_group)
        self.toggle_bitrate_btn.pack(side="left", padx=5)
        self.filter_button = tk.Button(sf, text=translate(lang,'ui.filter_oldest'), command=self.toggle_filter_selection)
        self.filter_button.pack(side="left", padx=5)
        self.delete_button = tk.Button(bottom, text=translate(lang,'ui.trash_btn', count=0), state="disabled", command=self.delete_duplicates)
        self.delete_button.pack(side="right", padx=10)

    # ================== Lecteur audio ==================
    def choose_audio_player(self):
        import shutil
        lang = self.language
        players = [
            ("VLC", shutil.which("vlc.exe")),
            ("Windows Media Player", shutil.which("wmplayer.exe")),
            ("Foobar2000", shutil.which("foobar2000.exe")),
            ("AIMP", shutil.which("aimp.exe")),
        ]
        players = [(n, p) for n, p in players if p]
        win = tk.Toplevel(self)
        win.title(translate(lang,'menu.choose_player'))
        win.geometry("420x240")
        tk.Label(win, text=translate(lang,'menu.choose_player')).pack(pady=10)
        var = tk.StringVar(value=self.audio_player_path or "")
        for name, path in players:
            tk.Radiobutton(win, text=f"{name} ({path})", variable=var, value=path).pack(anchor="w")
        def browse():
            exe = filedialog.askopenfilename(title=translate(lang,'menu.choose_player'), filetypes=[("Exécutables", "*.exe")])
            if exe: var.set(exe)
        tk.Button(win, text="...", command=browse).pack(pady=4)
        def ok():
            self.audio_player_path = var.get() or None
            win.destroy()
        tk.Button(win, text="OK", command=ok).pack(pady=6)

    # ================== Événements cellule / clavier ==================
    def _on_cell_clicked(self, event):
        row, col = event.get("row"), event.get("column")
        if row is None or col is None:
            return
        sel_col = self._select_column_index()
        # Clic dans colonne de sélection: juste focus
        if col == sel_col:
            self._set_dynamic_reference_from_row(row)
            return "break"
        # Définir référence différence
        self._set_dynamic_reference_from_row(row)
        # Ouvrir le fichier (comportement d’origine)
        try:
            if row in self.row_to_path_map:
                os.startfile(os.path.normpath(self.row_to_path_map[row]))
        except Exception as e:
            messagebox.showerror("Erreur", f"{translate(self.language,'msg.open_error')} {e}")

    def _on_native_double_click(self, _event):
        try:
            cur = self.sheet.get_currently_selected()
        except Exception:
            cur = None
        if not (isinstance(cur, tuple) and len(cur) >= 2):
            return
        try:
            row, col = int(cur[0]), int(cur[1])
        except Exception:
            return
        self._set_dynamic_reference_from_row(row)
        if col == self._select_column_index():
            self._toggle_checkbox(row)
            return "break"
        if row in self.row_to_path_map:
            try:
                os.startfile(os.path.normpath(self.row_to_path_map[row]))
            except Exception as e:
                messagebox.showerror("Erreur", f"{translate(self.language,'msg.open_error')} {e}")
        return "break"

    def _on_space_toggle(self, _event):
        try:
            selected = list(self.sheet.get_selected_rows())
        except Exception:
            selected = []
        if not selected:
            try:
                cur = self.sheet.get_currently_selected()
                if cur:
                    selected = [int(cur[0])]
            except Exception:
                pass
        for r in selected:
            self._set_checkbox(r, not self.checkbox_states.get(r, False))
        self.update_delete_button()
        return "break"

    def _on_any_right_click(self, event):
        """Routeur générique pour détecter si le clic droit est sur l’entête ou une cellule."""
        try:
            header_h = getattr(self.sheet, 'header_height', None)
            if header_h is None:
                header_h = getattr(self.sheet.MT, 'header_height', 25)
            if event.y <= header_h:
                col = None
                try:
                    if hasattr(self.sheet, 'identify_col'):
                        col = self.sheet.identify_col(event.x)
                except Exception:
                    col = None
                synth = {"column": col, "x_root": event.x_root, "y_root": event.y_root}
                return self._on_header_right_click(synth)
        except Exception:
            pass
        return self._on_cell_right_click(event)

    # ================== Événements table (menus traduits) ==================
    def _on_cell_right_click(self, event):
        lang = self.language
        if isinstance(event, dict): row = event.get("row")
        else:
            try:
                cur = self.sheet.get_currently_selected(); row = cur[0] if cur else None
            except Exception:
                row = None
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=translate(lang,'ctx.check_row'), command=lambda: self._set_row_checkbox(row, True))
        menu.add_command(label=translate(lang,'ctx.uncheck_row'), command=lambda: self._set_row_checkbox(row, False))
        menu.add_separator()
        menu.add_command(label=translate(lang,'ctx.invert_selection'), command=self.invert_rows_selection)
        if "group" in self.visible_columns and row is not None:
            try:
                g_val = self.sheet.get_cell_data(row, self.visible_columns.index("group"))
                menu.add_separator()
                menu.add_command(label=translate(lang,'ctx.check_group'), command=lambda gv=g_val: self._set_group_checkbox(gv, True))
                menu.add_command(label=translate(lang,'ctx.uncheck_group'), command=lambda gv=g_val: self._set_group_checkbox(gv, False))
                menu.add_command(label=translate(lang,'ctx.toggle_group'), command=self.toggle_current_group)
            except Exception:
                pass
        menu.add_separator()
        menu.add_checkbutton(label=translate(lang,'ctx.debug_mode'), onvalue=True, offvalue=False,
                             variable=tk.BooleanVar(value=self.debug_mode), command=self._toggle_debug)
        menu.add_command(label=translate(lang,'ctx.show_debug_select'), command=self._debug_show_selection_values)
        try:
            x_root = event.get('x_root') if isinstance(event, dict) else event.x_root
            y_root = event.get('y_root') if isinstance(event, dict) else event.y_root
        except Exception:
            x_root = self.winfo_pointerx(); y_root = self.winfo_pointery()
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            try: menu.grab_release()
            except Exception: pass
        return "break"

    def _on_header_right_click(self, event):
        lang = self.language
        menu = tk.Menu(self, tearoff=0)
        clicked_col_index = None
        try:
            if isinstance(event, dict) and 'column' in event:
                clicked_col_index = event['column']
            elif hasattr(event, 'column'):
                clicked_col_index = event.column
        except Exception:
            clicked_col_index = None
        clicked_key = None
        if isinstance(clicked_col_index, int) and 0 <= clicked_col_index < len(self.visible_columns):
            clicked_key = self.visible_columns[clicked_col_index]
        # Reset
        menu.add_command(label=translate(lang,'ctx.reset_columns'), command=self.reset_columns)
        menu.add_separator()
        # Cacher
        if clicked_key and clicked_key != 'select':
            def hide():
                if clicked_key in self.visible_columns:
                    if len(self.visible_columns) <= 2:
                        messagebox.showwarning(translate(lang,'msg.action_denied'), translate(lang,'msg.cannot_hide_more'))
                        return
                    self.visible_columns.remove(clicked_key)
                    self._apply_visible_columns()
            menu.add_command(label=translate(lang,'ctx.hide_col', name=self.column_names.get(clicked_key, clicked_key)), command=hide)
            menu.add_separator()
        # Déplacer
        if clicked_key:
            idx = self.visible_columns.index(clicked_key)
            if idx > 0 and clicked_key != 'select':
                def left():
                    i = self.visible_columns.index(clicked_key)
                    if i > 0:
                        self.visible_columns[i], self.visible_columns[i-1] = self.visible_columns[i-1], self.visible_columns[i]
                        if 'select' in self.visible_columns:
                            self.visible_columns = ['select'] + [c for c in self.visible_columns if c != 'select']
                        self._apply_visible_columns()
                menu.add_command(label=translate(lang,'ctx.move_left'), command=left)
            if idx < len(self.visible_columns) - 1:
                def right():
                    i = self.visible_columns.index(clicked_key)
                    if i < len(self.visible_columns)-1:
                        self.visible_columns[i], self.visible_columns[i+1] = self.visible_columns[i+1], self.visible_columns[i]
                        if 'select' in self.visible_columns:
                            self.visible_columns = ['select'] + [c for c in self.visible_columns if c != 'select']
                        self._apply_visible_columns()
                menu.add_command(label=translate(lang,'ctx.move_right'), command=right)
            menu.add_separator()
        # Colonnes cachées
        hidden = [c for c in self.all_columns if c not in self.visible_columns]
        if hidden:
            show_sub = tk.Menu(menu, tearoff=0)
            for key in hidden:
                def make_show(k=key):
                    if k not in self.visible_columns:
                        self.visible_columns.append(k)
                        if k == 'select':
                            self.visible_columns = ['select'] + [c for c in self.visible_columns if c != 'select']
                        self._apply_visible_columns()
                show_sub.add_command(label=self.column_names.get(key, key), command=make_show)
            menu.add_cascade(label=translate(lang,'ctx.show_hidden_col'), menu=show_sub)
        else:
            menu.add_command(label=translate(lang,'ctx.no_hidden_col'), state='disabled')
        def show_all():
            self.visible_columns = list(self.all_columns)
            if 'select' in self.visible_columns:
                self.visible_columns.remove('select'); self.visible_columns.insert(0, 'select')
            self._apply_visible_columns()
        menu.add_command(label=translate(lang,'ctx.show_all'), command=show_all)
        menu.add_separator()
        toggle_sub = tk.Menu(menu, tearoff=0)
        for col in self.all_columns:
            if col == 'select':
                continue
            var = tk.BooleanVar(value=col in self.visible_columns)
            def toggle(c=col, v=var):
                if v.get():
                    if c not in self.visible_columns: self.visible_columns.append(c)
                else:
                    if c in self.visible_columns and len(self.visible_columns) > 2:
                        self.visible_columns.remove(c)
                    elif c in self.visible_columns and len(self.visible_columns) <= 2:
                        v.set(True)
                self._apply_visible_columns()
            toggle_sub.add_checkbutton(label=self.column_names[col], variable=var, command=toggle)
        menu.add_cascade(label=translate(lang,'ctx.visible_columns'), menu=toggle_sub)
        try:
            x_root = event.get('x_root') if isinstance(event, dict) else event.x_root
            y_root = event.get('y_root') if isinstance(event, dict) else event.y_root
        except Exception:
            x_root = self.winfo_pointerx(); y_root = self.winfo_pointery()
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            try: menu.grab_release()
            except Exception: pass
        return "break"

    # ================== Divers ==================
    def _toggle_debug(self):  # override mixin to re-utiliser status_label
        self.debug_mode = not self.debug_mode
        try:
            self.status_label.config(text=f"Mode debug {'ON' if self.debug_mode else 'OFF'}")
        except Exception:
            pass

if __name__ == "__main__":
    app = DuplicateMusicFinder()
    app.mainloop()

import datetime
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from send2trash import send2trash
import tksheet
from dialogs import AskMultipleFoldersDialog  # réintroduit
from scanner import scan_duplicates

class DuplicateMusicFinder(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Détecteur de Doublons de Musique")
        self.geometry("1400x800")
        self.folder_paths = []
        self.keep_type_var = tk.StringVar(value="recent")
        self.filter_var = tk.StringVar()
        self.scan_in_progress = False
        self.all_groups = []
        self.hidden_items = set()
        self.audio_player_path = None
        self.toggle_flac_state = True
        self.visible_columns = ["select", "title", "artist", "album", "bitrate", "duration", "path", "group", "date"]
        self.all_columns = ["select", "title", "artist", "album", "bitrate", "duration", "path", "group", "date"]
        self.column_names = {"select": "Supprimer?", "title": "Titre", "artist": "Artiste", "album": "Album",
            "bitrate": "Bitrate (kbps)", "duration": "Durée", "path": "Chemin du Fichier", "group": "Groupe",
            "date": "Date"}
        self.row_to_path_map = {}
        self.debug_mode = False  # Permet d'afficher des infos supplémentaires
        self.checkbox_states = {}  # index de ligne -> bool sélection
        self.highlight_differences = True  # Active la mise en évidence des différences intra-groupe
        self.row_metadata = []  # métadonnées par ligne (groupe, is_reference, valeurs comparables)
        self.dynamic_group_reference = {}  # groupe -> row index choisi dynamiquement par l'utilisateur
        self._create_widgets()
        self._create_menu()
        self.queue = queue.Queue()
        self.process_queue()
        self.filter_var.trace_add("write", lambda *args: self.redisplay_results())
        # Raccourcis clavier pour la sélection
        self.bind("<Control-e>", lambda e: self.select_rows_selection())  # e pour 'enable'
        self.bind("<Control-d>", lambda e: self.deselect_rows_selection())  # d pour 'disable'
        self.bind("<Control-i>", lambda e: self.invert_rows_selection())  # i pour 'invert'
        self.bind("<Control-g>", lambda e: self.toggle_current_group())  # g pour basculer le groupe courant
        # Ajout: binding aussi sur la feuille (focus souvent dessus)
        # Le binding root ne fonctionne pas toujours si tksheet consomme l'événement
        # On attend que self.sheet soit créé plus tard; on ajoutera un binding dans _create_widgets.

    # --- Helper pour retrouver l'index de la colonne de sélection ---
    def _select_column_index(self):
        try:
            headers = self.sheet.headers()
            label = self.column_names.get("select", "Supprimer?")
            if label in headers:
                return headers.index(label)
        except Exception:
            pass
        return 0

    def _create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        options_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_command(label="Choisir le lecteur audio...", command=self.choose_audio_player)
        options_menu.add_checkbutton(label="Mettre en évidence les différences", onvalue=True, offvalue=False,
                                     command=self.toggle_highlight_differences,
                                     variable=tk.BooleanVar(value=self.highlight_differences))

    def choose_audio_player(self):
        import shutil
        players = [
            ("VLC", shutil.which("vlc.exe")),
            ("Windows Media Player", shutil.which("wmplayer.exe")),
            ("Foobar2000", shutil.which("foobar2000.exe")),
            ("AIMP", shutil.which("aimp.exe")),
        ]
        players = [(name, path) for name, path in players if path]
        win = tk.Toplevel(self)
        win.title("Choisir le lecteur audio")
        win.geometry("400x200")
        tk.Label(win, text="Sélectionnez un lecteur audio ou parcourez...").pack(pady=10)
        var = tk.StringVar(value=self.audio_player_path or "")
        for name, path in players:
            tk.Radiobutton(win, text=f"{name} ({path})", variable=var, value=path).pack(anchor="w")
        def browse():
            exe = filedialog.askopenfilename(title="Choisir un exécutable", filetypes=[("Exécutables", "*.exe")])
            if exe:
                var.set(exe)
        tk.Button(win, text="Parcourir...", command=browse).pack(pady=5)
        def valider():
            self.audio_player_path = var.get() if var.get() else None
            win.destroy()
        tk.Button(win, text="Valider", command=valider).pack(pady=10)

    def _create_widgets(self):
        top_frame = tk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(top_frame, text="Dossier(s) à scanner:").pack(side="left", anchor="w", pady=5)
        self.folder_listbox = tk.Listbox(top_frame, height=4)
        self.folder_listbox.pack(side="left", fill="x", expand=True, padx=5)
        folder_buttons_frame = tk.Frame(top_frame)
        folder_buttons_frame.pack(side="left", fill="y", padx=5)
        self.add_folder_button = tk.Button(folder_buttons_frame, text="Ajouter...", command=self.add_folder)
        self.add_folder_button.pack(fill="x", pady=2)
        self.add_multiple_folders_button = tk.Button(folder_buttons_frame, text="Ajouter plusieurs...", command=self.add_multiple_folders)
        self.add_multiple_folders_button.pack(fill="x", pady=2)
        self.remove_folder_button = tk.Button(folder_buttons_frame, text="Retirer", command=self.remove_folder)
        self.remove_folder_button.pack(fill="x", pady=2)
        options_frame = tk.Frame(self)
        options_frame.pack(fill="x", padx=10, pady=5)
        similarity_frame = tk.LabelFrame(options_frame, text="Seuil de ressemblance des titres (%)")
        similarity_frame.pack(side="left", padx=5)
        self.similarity_var = tk.IntVar(value=80)
        self.similarity_scale = tk.Scale(similarity_frame, from_=50, to=100, orient="horizontal", variable=self.similarity_var, resolution=1)
        self.similarity_scale.pack(anchor="w")
        tk.Label(similarity_frame, text="Plus le seuil est bas, plus la détection sera tolérante.").pack(anchor="w")
        duration_filter_frame = tk.LabelFrame(options_frame, text="Tolérance sur la durée (%)")
        duration_filter_frame.pack(side="left", padx=5)
        self.duration_similarity_var = tk.IntVar(value=95)
        self.duration_similarity_scale = tk.Scale(duration_filter_frame, from_=80, to=100, orient="horizontal", variable=self.duration_similarity_var, resolution=1, command=lambda e: self.redisplay_results())
        self.duration_similarity_scale.pack(anchor="w")
        tk.Label(duration_filter_frame, text="Seuil de similarité des durées pour filtrer les groupes.").pack(anchor="w")
        self.scan_button = tk.Button(options_frame, text="Scanner les Doublons", command=self.start_scan_thread)
        self.scan_button.pack(side="left", padx=20, ipady=10)
        progress_frame = tk.Frame(self)
        progress_frame.pack(fill="x", padx=10, pady=5)
        self.status_label = tk.Label(progress_frame, text="Prêt.")
        self.status_label.pack(side="left")
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=5)
        filter_frame = tk.Frame(self)
        filter_frame.pack(fill="x", padx=10, pady=(5, 0))
        tk.Label(filter_frame, text="Filtrer les résultats:").pack(side="left", padx=(0, 5))
        filter_entry = tk.Entry(filter_frame, textvariable=self.filter_var)
        filter_entry.pack(side="left", fill="x", expand=True)
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        columns = ("select", "title", "artist", "album", "bitrate", "duration", "path", "group", "date")
        self.sheet = tksheet.Sheet(
            tree_frame,
            headers=[self.column_names[col] for col in columns],
            show_row_index=False,
            show_header=True
        )
        self.sheet.enable_bindings(
            "single_select", "row_select", "column_select", "drag_select", "rc_select", "arrowkeys",
            "column_drag_and_drop", "column_width_resize"
        )
        self.sheet.pack(fill="both", expand=True)
        self.sheet.extra_bindings("cell_clicked", self._on_cell_clicked)
        self.sheet.extra_bindings("cell_rclick", self._on_cell_right_click)
        self.sheet.extra_bindings("header_rclick", self._on_header_right_click)
        try:
            self.sheet.bind("<Button-3>", self._on_cell_right_click)
            self.sheet.bind("<Double-1>", self._on_native_double_click)
            self.sheet.bind("<space>", self._on_space_toggle)
            # Ajout: bindings clavier sur la feuille pour inversion et groupe
            self.sheet.bind("<Control-i>", lambda e: self.invert_rows_selection())
            self.sheet.bind("<Control-g>", lambda e: self.toggle_current_group())
        except Exception:
            pass
        self._apply_readonly_except_select()  # Appliquer readonly aux autres colonnes
        bottom_frame = tk.Frame(self)
        bottom_frame.pack(fill="x", pady=10)
        selection_frame = tk.Frame(bottom_frame)
        selection_frame.pack(side="left")
        tk.Button(selection_frame, text="Sélectionner tous les .flac", command=self.select_all_flac_files).pack(side="left", padx=5)
        self.toggle_bitrate_state = True
        self.toggle_bitrate_btn = tk.Button(selection_frame, text="Toggle plus gros bitrate/groupe", command=self.toggle_highest_bitrate_per_group)
        self.toggle_bitrate_btn.pack(side="left", padx=5)
        self.filter_mode = True
        self.filter_button = tk.Button(selection_frame, text="Filtrer (plus vieux)", command=self.toggle_filter_selection)
        self.filter_button.pack(side="left", padx=5)
        self.delete_button = tk.Button(bottom_frame, text="Mettre à la corbeille (0)", state="disabled", command=self.delete_duplicates)
        self.delete_button.pack(side="right", padx=10)

    def _apply_readonly_except_select(self):
        """Rend toutes les colonnes sauf la colonne de sélection en lecture seule."""
        try:
            headers = self.sheet.headers()
            select_header = self.column_names["select"]
            for idx, header in enumerate(headers):
                if header == select_header:
                    # colonne sélection modifiable
                    self.sheet.column_options(idx, readonly=False)
                else:
                    self.sheet.column_options(idx, readonly=True)
        except Exception:
            pass

    def redisplay_results(self, preserve_selection=True):
        selected_paths = set()
        if preserve_selection:
            for row_idx, is_checked in enumerate(self.sheet.get_column_data(0)):
                if is_checked and row_idx in self.row_to_path_map:
                    selected_paths.add(self.row_to_path_map[row_idx])

        self.sheet.set_sheet_data([[]])
        self.row_to_path_map.clear()
        self.row_metadata = []  # réinitialiser les métadonnées
        self.dynamic_group_reference = {}  # reset références dynamiques sur reconstruction

        if not self.all_groups:
            self.update_delete_button()
            return

        filter_query = self.filter_var.get().lower()
        keep_type = self.keep_type_var.get()
        group_id = 1
        any_duration = False
        duration_similarity = self.duration_similarity_var.get() / 100.0 if hasattr(self, 'duration_similarity_var') else 0.95
        data_matrix = []
        current_row_idx = 0
        new_states = {}

        for group in self.all_groups:
            durations = [file_info.get("duration", 0) or 0 for file_info in group]
            min_dur = min(durations) if durations else 0
            max_dur = max(durations) if durations else 0
            ratio = min(min_dur, max_dur) / max(max_dur, min_dur) if max_dur > 0 and min_dur > 0 else 1.0
            if ratio < duration_similarity:
                continue

            group.sort(key=lambda f: f.get("bitrate", 0), reverse=True)
            group.sort(key=lambda f: f["date"])
            file_to_keep = group[-1] if keep_type == "recent" else group[0]

            for file_info in group:
                path = file_info["path"]
                if path in self.hidden_items:
                    continue

                if filter_query and not any(filter_query in str(file_info.get(v, "")).lower() for v in ["title", "artist", "album", "path"]):
                    continue

                self.row_to_path_map[current_row_idx] = path

                display_path = os.path.relpath(path, os.path.dirname(self.folder_paths[0])) if self.folder_paths else path
                date_str = datetime.datetime.fromtimestamp(file_info["date"]).strftime('%Y-%m-%d %H:%M:%S')
                is_duplicate = (file_info != file_to_keep)
                
                check_char = is_duplicate
                if preserve_selection and selected_paths:
                    check_char = (path in selected_paths)
                # Représentation texte de la case: "✔" si coché sinon vide
                select_cell = "✔" if check_char else ""

                duration_sec = file_info.get("duration", 0) or 0
                any_duration = any_duration or (duration_sec > 0)
                duration_str = f"{int(duration_sec // 60)}:{int(duration_sec % 60):02d}" if duration_sec > 0 else "-"

                values_dict = {"select": select_cell, "title": file_info.get("title", "N/A"),
                    "artist": file_info.get("artist", "N/A"), "album": file_info.get("album", "N/A"),
                    "bitrate": file_info.get("bitrate", 0), "duration": duration_str, "path": display_path,
                    "group": f"Groupe {group_id}", "date": date_str}
                row_data = [values_dict[col] for col in self.visible_columns]
                data_matrix.append(row_data)
                new_states[current_row_idx] = bool(check_char)
                # Ajouter métadonnées de ligne
                is_reference = (file_info == file_to_keep)
                self.row_metadata.append({
                    "group": f"Groupe {group_id}",
                    "is_reference": is_reference,
                    "values": {
                        "title": file_info.get("title", "") or "",
                        "artist": file_info.get("artist", "") or "",
                        "album": file_info.get("album", "") or "",
                        "bitrate": file_info.get("bitrate", 0) or 0,
                        "duration": duration_str  # durée formatée mm:SS pour cohérence d'affichage
                    }
                })
                current_row_idx += 1

            group_id += 1

        self.sheet.set_sheet_data(data_matrix, reset_col_positions=True, reset_row_positions=True)
        self._apply_readonly_except_select()
        # Initialiser états internes depuis new_states
        self.checkbox_states = new_states
        if not any_duration and "duration" in self.visible_columns:
            self.status_label.config(text="Aucune durée trouvée : le scan ne fournit pas la durée des fichiers.")
        self.update_delete_button()
        # Appliquer la coloration des différences après la mise à jour du bouton
        self._apply_difference_highlighting()

    def get_selected_files(self):
        selected_paths = []
        for row_idx, checked in self.checkbox_states.items():
            if checked and row_idx in self.row_to_path_map:
                selected_paths.append(self.row_to_path_map[row_idx])
        return selected_paths

    def update_delete_button(self):
        count = sum(1 for v in self.checkbox_states.values() if v)
        state = tk.NORMAL if count > 0 else tk.DISABLED
        self.delete_button.config(state=state, text=f"Mettre à la corbeille ({count})")
        if self.debug_mode:
            sample = ", ".join(f"{i}:{int(self.checkbox_states[i])}" for i in list(self.checkbox_states.keys())[:10])
            self.status_label.config(text=f"Debug états internes: {sample} | count={count}")

    def delete_duplicates(self):
        files_to_delete = self.get_selected_files()
        if not files_to_delete:
            messagebox.showwarning("Aucune sélection", "Aucun fichier n'est coché pour la suppression.")
            return

        # Pré‑validation des chemins (détection chemins relatifs / inexistants)
        precheck_rows = []
        reconstructed = []
        base_dirs = self.folder_paths[:]  # dossiers racines
        validated_files = []
        for f_path in files_to_delete:
            original = f_path
            abs_path = os.path.abspath(f_path)
            exists = os.path.exists(abs_path)
            # Si le chemin ne pointe à rien mais ressemble à un relatif, tenter reconstruction
            if not exists and not os.path.isabs(f_path):
                for base in base_dirs:
                    candidate = os.path.abspath(os.path.join(base, f_path))
                    if os.path.exists(candidate):
                        abs_path = candidate
                        exists = True
                        reconstructed.append((original, candidate))
                        break
            # Dernier recours: si perdu et qu'il y a un mapping row -> path on le garde tel quel
            validated_files.append((original, abs_path, exists))
        if any(not e for (_, _, e) in validated_files):
            missing_list = "\n".join(f"- {orig} (après tentative: {abs_p})" for (orig, abs_p, e) in validated_files if not e)
            if not messagebox.askyesno(
                "Fichiers introuvables",
                "Certains fichiers semblent introuvables et ne seront pas supprimés:\n" + missing_list + "\n\nContinuer quand même pour les autres ?"
            ):
                return
        if reconstructed and self.debug_mode:
            recon_msg = "\n".join(f"{o} -> {r}" for o, r in reconstructed)
            self.status_label.config(text=f"Reconstruit: {len(reconstructed)} chemins")

        # Ne conserver que ceux qui existent réellement
        existing_files = [abs_p for (orig, abs_p, e) in validated_files if e]
        if not existing_files:
            messagebox.showerror("Suppression", "Aucun des fichiers sélectionnés n'a été trouvé sur le disque.")
            return

        msg_lines = [f"{len(existing_files)} fichier(s) seront envoyés à la corbeille."]
        if reconstructed:
            msg_lines.append(f"{len(reconstructed)} chemin(s) ont été reconstruits depuis un chemin relatif.")
        if len(existing_files) <= 10:
            msg_lines.append("Liste :")
            msg_lines.extend(existing_files)
        msg = "\n".join(msg_lines) + "\n\nContinuer ?"
        if not messagebox.askyesno("Confirmation", msg):
            return

        deleted_count, error_count = 0, 0
        errors = []
        for abs_path in existing_files:
            try:
                send2trash(abs_path)
                deleted_count += 1
            except Exception as e:
                errors.append(f"- {abs_path}: {e}")
                error_count += 1

        # Mise à jour des groupes : fi['path'] peut être absolu, on compare sur normalisation
        deleted_set_norm = {os.path.normcase(os.path.abspath(p)) for p in existing_files}
        new_groups = []
        for g in self.all_groups:
            new_g = []
            for fi in g:
                try:
                    p_norm = os.path.normcase(os.path.abspath(fi["path"]))
                except Exception:
                    p_norm = fi.get("path")
                if p_norm not in deleted_set_norm:
                    new_g.append(fi)
            if len(new_g) > 1:  # garder uniquement les groupes qui restent des doublons
                new_groups.append(new_g)
        self.all_groups = new_groups

        info_message = f"{deleted_count} fichier(s) déplacé(s) vers la corbeille."
        if error_count > 0:
            info_message += f"\n{error_count} erreur(s) lors du déplacement:\n" + "\n".join(errors)
        if reconstructed:
            info_message += f"\n{len(reconstructed)} chemin(s) reconstruits (voir console / debug)."
        messagebox.showinfo("Opération Terminée", info_message)
        self.redisplay_results(preserve_selection=False)

    def _set_dynamic_reference_from_row(self, row):
        """Définit la ligne de référence dynamique pour son groupe (si colonne groupe visible)."""
        if row is None:
            return
        if "group" not in self.visible_columns:
            return
        try:
            g_idx = self.visible_columns.index("group")
            g_val = self.sheet.get_cell_data(row, g_idx)
            if g_val:
                self.dynamic_group_reference[g_val] = row
                # Re-appliquer uniquement le groupe concerné (on recolorise tout pour simplicité)
                self._apply_difference_highlighting()
        except Exception:
            pass

    def _on_cell_clicked(self, event):
        row, col = event["row"], event["column"]
        sel_idx = self._select_column_index()
        if col == sel_idx:
            # Simple clic dans colonne Supprimer?: on sélectionne juste la ligne visuellement, pas de toggle.
            try:
                if hasattr(self.sheet, 'set_currently_selected'):
                    self.sheet.set_currently_selected((row, col))
                if hasattr(self.sheet, 'select_row'):
                    self.sheet.select_row(row)
                elif hasattr(self.sheet, 'add_selection'):
                    self.sheet.add_selection("row", row, redraw=True)
            except Exception:
                pass
            # Mise à jour référence dynamique malgré retour break
            self._set_dynamic_reference_from_row(row)
            return "break"
        # Autres colonnes : ouverture du fichier (simple clic)
        self._set_dynamic_reference_from_row(row)
        self.after(10, self.update_delete_button)
        try:
            if row in self.row_to_path_map:
                file_path = self.row_to_path_map[row]
                os.startfile(os.path.normpath(file_path))
        except Exception as e:
            messagebox.showerror("Erreur de Lecture", f"Impossible d'ouvrir le fichier :\n{e}")

    def _on_native_double_click(self, event):
        """Gestion du double-clic (fallback natif Tk) pour cocher/décocher ou ouvrir le fichier.
        Utilise la cellule actuellement sélectionnée par le simple clic précédent."""
        try:
            current = self.sheet.get_currently_selected()
        except Exception:
            current = None
        if not (isinstance(current, tuple) and len(current) >= 2):
            return
        row, col = current[0], current[1]
        try:
            row = int(row); col = int(col)
        except Exception:
            return
        sel_idx = self._select_column_index()
        # Toujours mettre à jour la référence dynamique (quel que soit la colonne) pour retour visuel immédiat
        self._set_dynamic_reference_from_row(row)
        if col == sel_idx:
            # Toggle case
            self._toggle_checkbox(row)
            return "break"
        # Double clic ailleurs : ouvrir le fichier
        if row in self.row_to_path_map:
            try:
                file_path = self.row_to_path_map[row]
                os.startfile(os.path.normpath(file_path))
            except Exception as e:
                messagebox.showerror("Erreur de Lecture", f"Impossible d'ouvrir le fichier :\n{e}")
        return "break"

    def _on_cell_right_click(self, event):
        """Menu contextuel sur clic droit dans une cellule.
        Accepte soit un dict (événement tksheet), soit un événement Tk classique.
        """
        row = None
        col = None
        x_root = None
        y_root = None
        # Cas dict (tksheet extra_bindings)
        if isinstance(event, dict):
            row = event.get("row")
            col = event.get("column")
            x_root = event.get("x_root")
            y_root = event.get("y_root")
        else:
            # Événement Tk classique
            try:
                x_root = event.x_root
                y_root = event.y_root
            except Exception:
                try:
                    x_root = self.winfo_pointerx()
                    y_root = self.winfo_pointery()
                except Exception:
                    pass
            # Essayer de récupérer la cellule actuellement sélectionnée
            try:
                current = self.sheet.get_currently_selected()
                if isinstance(current, tuple) and len(current) >= 2:
                    row, col = current[0], current[1]
            except Exception:
                pass
            # Sinon essayer les lignes sélectionnées
            if row is None:
                try:
                    sel_rows = self.sheet.get_selected_rows()
                    if sel_rows:
                        row = list(sel_rows)[0]
                except Exception:
                    pass
        # Construction du menu (version épurée)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Cocher la ligne", command=lambda: self._set_row_checkbox(row, True))
        menu.add_command(label="Décocher la ligne", command=lambda: self._set_row_checkbox(row, False))
        # Ajouter systématiquement l'option inversion (même sans sélection multiple)
        menu.add_separator()
        menu.add_command(label="Inverser la sélection (Ctrl+I)", command=self.invert_rows_selection)
        # Actions de groupe si colonne groupe visible
        if "group" in self.visible_columns and row is not None:
            try:
                group_val = self.sheet.get_cell_data(row, self.visible_columns.index("group"))
                menu.add_separator()
                menu.add_command(label="Cocher tout le groupe", command=lambda gv=group_val: self._set_group_checkbox(gv, True))
                menu.add_command(label="Décocher tout le groupe", command=lambda gv=group_val: self._set_group_checkbox(gv, False))
                menu.add_command(label="Basculer tout le groupe (Ctrl+G)", command=self.toggle_current_group)
            except Exception:
                pass
        menu.add_separator()
        menu.add_command(label="Mettre à jour le bouton", command=self.update_delete_button)
        menu.add_checkbutton(label="Mode debug (afficher valeurs)", onvalue=True, offvalue=False,
                             variable=tk.BooleanVar(value=self.debug_mode),
                             command=lambda: self._toggle_debug())
        menu.add_command(label="Voir valeurs brutes col sélection", command=self._debug_show_selection_values)
        try:
            if x_root is None or y_root is None:
                x_root = self.winfo_pointerx()
                y_root = self.winfo_pointery()
            menu.tk_popup(x_root, y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass
        # Empêcher éventuel menu par défaut
        return "break"

    def _on_header_right_click(self, event):
        menu = tk.Menu(self, tearoff=0)
        for col in self.all_columns:
            if col == "select": continue
            checked = tk.BooleanVar(value=col in self.visible_columns)
            def toggle_col(c=col, var=checked):
                if var.get():
                    if c not in self.visible_columns: self.visible_columns.append(c)
                else:
                    if c in self.visible_columns: self.visible_columns.remove(c)
                if len(self.visible_columns) < 2: self.visible_columns.append(c)
                if 'select' not in self.visible_columns: self.visible_columns.insert(0, 'select')
                self.sheet.headers([self.column_names[c] for c in self.visible_columns])
                self.redisplay_results()
            menu.add_checkbutton(label=self.column_names[col], variable=checked, command=toggle_col)
        menu.tk_popup(event["x_root"], event["y_root"])

    def _set_checkbox(self, row, value):
        self.checkbox_states[row] = bool(value)
        try:
            sel_idx = self._select_column_index()
            self.sheet.set_cell_data(row, sel_idx, "✔" if value else "")
        except Exception:
            pass

    def _toggle_checkbox(self, row):
        current = self.checkbox_states.get(row, False)
        self._set_checkbox(row, not current)
        self.update_delete_button()

    def _set_row_checkbox(self, row, value):
        if row is None:
            return
        self._set_checkbox(row, value)
        self.update_delete_button()

    def _set_group_checkbox(self, group_val, value):
        group_idx = self.visible_columns.index("group") if "group" in self.visible_columns else None
        if group_idx is None:
            return
        sel_idx = self._select_column_index()
        for r, row_data in enumerate(self.sheet.get_sheet_data()):
            if row_data and row_data[group_idx] == group_val:
                self._set_checkbox(r, value)
        self.update_delete_button()

    def select_rows_selection(self):
        for r in self.sheet.get_selected_rows():
            self._set_checkbox(r, True)
        self.update_delete_button()

    def deselect_rows_selection(self):
        for r in self.sheet.get_selected_rows():
            self._set_checkbox(r, False)
        self.update_delete_button()

    def invert_rows_selection(self):
        """Inverse l'état des cases des lignes sélectionnées; si aucune sélection explicite, utilise la ligne courante."""
        try:
            selected = list(self.sheet.get_selected_rows())
        except Exception:
            selected = []
        if not selected:
            # Utiliser la ligne courante si aucune sélection multiple
            try:
                current = self.sheet.get_currently_selected()
                if isinstance(current, tuple) and len(current) >= 1:
                    selected = [int(current[0])]
            except Exception:
                selected = []
        if not selected:
            return
        for r in selected:
            self._set_checkbox(r, not self.checkbox_states.get(r, False))
        self.update_delete_button()

    def select_group(self):
        selected = self.sheet.get_selected_rows()
        if not selected:
            return
        row = selected.pop()
        group_val = self.sheet.get_cell_data(row, self.visible_columns.index("group"))
        for r, row_data in enumerate(self.sheet.get_sheet_data()):
            if row_data and row_data[self.visible_columns.index("group")] == group_val:
                self._set_checkbox(r, True)
        self.update_delete_button()

    def deselect_group(self):
        selected = self.sheet.get_selected_rows()
        if not selected:
            return
        row = selected.pop()
        group_val = self.sheet.get_cell_data(row, self.visible_columns.index("group"))
        for r, row_data in enumerate(self.sheet.get_sheet_data()):
            if row_data and row_data[self.visible_columns.index("group")] == group_val:
                self._set_checkbox(r, False)
        self.update_delete_button()

    def select_all_flac_files(self):
        path_idx = self.visible_columns.index("path")
        for r, row_data in enumerate(self.sheet.get_sheet_data()):
            if row_data and str(row_data[path_idx]).lower().endswith('.flac'):
                self._set_checkbox(r, self.toggle_flac_state)
        self.toggle_flac_state = not self.toggle_flac_state
        self.update_delete_button()

    def toggle_highest_bitrate_per_group(self):
        group_idx = self.visible_columns.index("group")
        bitrate_idx = self.visible_columns.index("bitrate")
        date_idx = self.visible_columns.index("date")
        data = self.sheet.get_sheet_data()
        group_map = {}
        for r, row_data in enumerate(data):
            if not row_data:
                continue
            group = row_data[group_idx]
            group_map.setdefault(group, []).append((r, row_data))
        for group_items in group_map.values():
            max_bitrate = -1
            max_rows = []
            for r, row_data in group_items:
                bitrate = int(row_data[bitrate_idx]) if str(row_data[bitrate_idx]).isdigit() else 0
                if bitrate > max_bitrate:
                    max_bitrate = bitrate
                    max_rows = [(r, row_data)]
                elif bitrate == max_bitrate:
                    max_rows.append((r, row_data))
            min_date, min_row = float('inf'), None
            for r, row_data in max_rows:
                date = datetime.datetime.strptime(row_data[date_idx], '%Y-%m-%d %H:%M:%S').timestamp()
                if date < min_date:
                    min_date, min_row = date, r
            for r, _ in group_items:
                self._set_checkbox(r, (r != min_row) if self.toggle_bitrate_state else (r == min_row))
        self.toggle_bitrate_state = not self.toggle_bitrate_state
        self.update_delete_button()

    def start_scan_thread(self):
        if self.scan_in_progress:
            return
        if not self.folder_paths:
            messagebox.showerror("Erreur", "Veuillez ajouter au moins un dossier à analyser.")
            return
        self.scan_in_progress = True
        self.scan_button.config(state="disabled")
        self.add_folder_button.config(state="disabled")
        # Boutons multiples dossiers si présent
        if hasattr(self, 'add_multiple_folders_button'):
            self.add_multiple_folders_button.config(state="disabled")
        self.remove_folder_button.config(state="disabled")
        self.clear_results_data()
        thread = threading.Thread(
            target=scan_duplicates,
            args=(self.folder_paths.copy(), self.keep_type_var.get(), self.queue, self.similarity_var.get() / 100.0),
            daemon=True
        )
        thread.start()

    def process_queue(self):
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "status":
                    self.status_label.config(text=data)
                elif msg_type == "progress":
                    self.progress_bar["value"] = data
                elif msg_type == "progress_max":
                    self.progress_bar["maximum"] = data
                elif msg_type == "message":
                    level, text = data
                    if level == "info":
                        messagebox.showinfo("Information", text)
                    else:
                        messagebox.showerror("Erreur", text)
                elif msg_type == "results":
                    self.all_groups = data
                    self.redisplay_results(preserve_selection=False)
                elif msg_type == "finished":
                    self.scan_in_progress = False
                    self.scan_button.config(state="normal")
                    self.add_folder_button.config(state="normal")
                    if hasattr(self, 'add_multiple_folders_button'):
                        self.add_multiple_folders_button.config(state="normal")
                    self.remove_folder_button.config(state="normal")
                    self.status_label.config(text="Analyse terminée.")
                    self.progress_bar["value"] = 0
        except queue.Empty:
            self.after(100, self.process_queue)

    def clear_results_data(self):
        self.all_groups = []
        self.hidden_items = set()
        self.checkbox_states = {}
        self.row_metadata = []
        self.dynamic_group_reference = {}
        try:
            self.sheet.set_sheet_data([[]])
        except Exception:
            pass
        self.update_delete_button()
        self.status_label.config(text="Prêt.")

    def toggle_filter_selection(self):
        mode = self.filter_mode
        self.filter_mode = not self.filter_mode
        self.filter_button.config(text="Filtrer (plus récent)" if not mode else "Filtrer (plus vieux)")
        if "group" not in self.visible_columns or "date" not in self.visible_columns:
            return
        group_idx = self.visible_columns.index("group")
        date_idx = self.visible_columns.index("date")
        data = self.sheet.get_sheet_data()
        group_map = {}
        for r, row_data in enumerate(data):
            if not row_data:
                continue
            group = row_data[group_idx]
            group_map.setdefault(group, []).append((r, row_data))
        for group_items in group_map.values():
            best_row, best_date = None, None
            for r, row_data in group_items:
                try:
                    date = datetime.datetime.strptime(row_data[date_idx], '%Y-%m-%d %H:%M:%S').timestamp()
                except Exception:
                    date = 0
                if best_date is None or (mode and date < best_date) or (not mode and date > best_date):
                    best_date, best_row = date, r
            for r, _ in group_items:
                self._set_checkbox(r, r != best_row)
        self.update_delete_button()

    # --- Réintroduction des méthodes supprimées par inadvertance ---
    def add_folder(self):
        path = filedialog.askdirectory()
        if path and path not in self.folder_paths:
            self.folder_paths.append(path)
            self.folder_listbox.insert(tk.END, path)
            self.clear_results_data()

    def add_multiple_folders(self):
        dialog = AskMultipleFoldersDialog(self)
        new_paths = dialog.paths
        if new_paths:
            for path in new_paths:
                if path not in self.folder_paths:
                    self.folder_paths.append(path)
                    self.folder_listbox.insert(tk.END, path)
            self.clear_results_data()

    def remove_folder(self):
        selected_indices = self.folder_listbox.curselection()
        if not selected_indices:
            return
        for i in sorted(selected_indices, reverse=True):
            del self.folder_paths[i]
            self.folder_listbox.delete(i)
        self.clear_results_data()

    # --- SUPPRESSION des doublons: les méthodes suivantes étaient redéfinies plus bas ---
    # Les définitions en double de start_scan_thread, process_queue, clear_results_data,
    # toggle_filter_selection, add_folder, add_multiple_folders, remove_folder ont été supprimées
    # pour éviter toute confusion. Les versions actives restent plus haut dans le fichier.

    # Fin des suppressions de doublons.

    # === Ajout méthodes debug manquantes ===
    def _toggle_debug(self):
        self.debug_mode = not self.debug_mode
        state = "ON" if self.debug_mode else "OFF"
        self.status_label.config(text=f"Mode debug {state}")
        self.update_delete_button()

    def _debug_show_selection_values(self):
        try:
            sel_idx = self._select_column_index()
            rows = len(self.sheet.get_sheet_data())
            raw = []
            for r in range(min(rows, 50)):
                try:
                    cell_val = self.sheet.get_cell_data(r, sel_idx)
                except Exception:
                    cell_val = None
                internal = self.checkbox_states.get(r, False)
                raw.append(f"{r}: cell={cell_val!r} internal={int(bool(internal))}")
            if not raw:
                raw.append("(aucune ligne)")
            messagebox.showinfo("Debug sélection", "\n".join(raw))
        except Exception as e:
            messagebox.showerror("Debug erreur", str(e))

    def _on_space_toggle(self, event):
        """Toggle via barre espace: toutes les lignes sélectionnées si selection, sinon la ligne courante."""
        try:
            selected_rows = list(self.sheet.get_selected_rows())
        except Exception:
            selected_rows = []
        if not selected_rows:
            # ligne courante
            try:
                current = self.sheet.get_currently_selected()
                if isinstance(current, tuple) and len(current) >= 1:
                    row = int(current[0])
                    selected_rows = [row]
            except Exception:
                pass
        toggled_any = False
        for r in selected_rows:
            old = self.checkbox_states.get(r, False)
            self._set_checkbox(r, not old)
            toggled_any = True
        if toggled_any:
            self.update_delete_button()
        return "break"

    def toggle_current_group(self):
        """Bascule (cocher/décocher) l'ensemble du groupe de la ligne courante ou de la première ligne sélectionnée.
        Si au moins un élément du groupe n'est pas coché -> tout cocher, sinon tout décocher."""
        if "group" not in self.visible_columns:
            return
        group_idx = self.visible_columns.index("group")
        # Récupérer la ligne courante prioritairement
        row = None
        try:
            current = self.sheet.get_currently_selected()
            if isinstance(current, tuple) and len(current) >= 1:
                row = int(current[0])
        except Exception:
            pass
        if row is None:
            try:
                sel = self.sheet.get_selected_rows()
                if sel:
                    row = list(sel)[0]
            except Exception:
                pass
        if row is None:
            return
        try:
            group_val = self.sheet.get_cell_data(row, group_idx)
        except Exception:
            return
        # Collecter les lignes du groupe
        group_rows = []
        for r, row_data in enumerate(self.sheet.get_sheet_data()):
            if row_data and row_data[group_idx] == group_val:
                group_rows.append(r)
        if not group_rows:
            return
        any_unchecked = any(not self.checkbox_states.get(r, False) for r in group_rows)
        new_state = True if any_unchecked else False
        for r in group_rows:
            self._set_checkbox(r, new_state)
        self.update_delete_button()

    def toggle_highlight_differences(self):
        """Active/Désactive la mise en évidence des différences intra-groupe.
        Quand on désactive, on tente de restaurer la couleur par défaut (noir) sur les colonnes comparables.
        """
        self.highlight_differences = not self.highlight_differences
        if not self.highlight_differences:
            self._clear_difference_highlighting()
        else:
            self._apply_difference_highlighting()

    def _clear_difference_highlighting(self):
        """Remet les couleurs par défaut (texte noir) sur les colonnes susceptibles d'avoir été colorées."""
        try:
            comparable_keys = ["title", "artist", "album", "bitrate", "duration"]
            # Limiter aux colonnes visibles
            target_indices = [self.visible_columns.index(k) for k in comparable_keys if k in self.visible_columns]
            data = self.sheet.get_sheet_data()
            for r in range(len(data)):
                for c in target_indices:
                    try:
                        if hasattr(self.sheet, 'highlight_cells'):
                            self.sheet.highlight_cells(row=r, column=c, fg='black', redraw=False)
                    except Exception:
                        pass
            try:
                self.sheet.redraw()
            except Exception:
                pass
        except Exception:
            pass

    def _apply_difference_highlighting(self):
        """Coloration fine : seules les cellules qui diffèrent de la ligne de référence (fichier conservé) sont rouges.
        Référence = ligne marquée is_reference dans self.row_metadata pour chaque groupe.
        Colonnes analysées: title, artist, album, bitrate, duration (si visibles).
        """
        if not self.highlight_differences:
            return
        if not self.row_metadata or not self.visible_columns:
            return
        try:
            comparable_keys = ["title", "artist", "album", "bitrate", "duration"]
            key_to_col = {k: self.visible_columns.index(k) for k in comparable_keys if k in self.visible_columns}
            if "group" not in self.visible_columns:
                return
            # Nettoyage préalable
            if hasattr(self.sheet, 'highlight_cells'):
                for r in range(len(self.sheet.get_sheet_data())):
                    for col_idx in key_to_col.values():
                        try:
                            self.sheet.highlight_cells(row=r, column=col_idx, fg='black', redraw=False)
                        except Exception:
                            pass
            # Regrouper
            groups = {}
            for r, meta in enumerate(self.row_metadata):
                g = meta.get("group")
                groups.setdefault(g, {"rows": [], "ref_row": None})
                groups[g]["rows"].append(r)
                if meta.get("is_reference"):
                    groups[g]["ref_row"] = r
            # Appliquer
            for g, info in groups.items():
                rows = info['rows']
                if not rows:
                    continue
                # Choisir: référence dynamique prioritaire si still present
                dyn_ref = self.dynamic_group_reference.get(g)
                if dyn_ref is not None and dyn_ref in rows:
                    ref_row = dyn_ref
                else:
                    ref_row = info.get('ref_row') if info.get('ref_row') is not None else rows[0]
                ref_vals = self.row_metadata[ref_row].get('values', {})
                for r in rows:
                    if r == ref_row:
                        continue
                    row_vals = self.row_metadata[r].get('values', {})
                    for key, col_idx in key_to_col.items():
                        rv = row_vals.get(key, ""); rf = ref_vals.get(key, "")
                        if key == 'bitrate':
                            try: rvn = int(rv)
                            except Exception: rvn = -1
                            try: rfn = int(rf)
                            except Exception: rfn = -1
                            diff = (rvn != rfn)
                        else:
                            lv = rv.strip().lower() if isinstance(rv, str) else rv
                            lf = rf.strip().lower() if isinstance(rf, str) else rf
                            diff = (lv != lf)
                        if diff:
                            try:
                                if hasattr(self.sheet, 'highlight_cells'):
                                    self.sheet.highlight_cells(row=r, column=col_idx, fg='red', redraw=False)
                            except Exception:
                                pass
            try:
                self.sheet.redraw()
            except Exception:
                pass
        except Exception:
            # En cas d'échec silencieux (compatibilité versions tksheet)
            pass

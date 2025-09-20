import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import datetime
import threading
import queue
import os
import json
from send2trash import send2trash

from scanner import scan_duplicates
from dialogs import AskMultipleFoldersDialog

CONFIG_FILE = "config.json"

class DuplicateMusicFinder(tk.Tk):
    """Classe principale de l'application Détecteur de Doublons de Musique."""
    def __init__(self):
        """Initialise l'application, ses variables et le mixer audio."""
        super().__init__()
        self.title("Détecteur de Doublons de Musique")
        self.geometry("1400x800")

        self.folder_paths = []
        self.keep_type_var = tk.StringVar(value="recent")
        self.filter_var = tk.StringVar()
        self.scan_in_progress = False

        self.all_groups = []
        self.hidden_items = set()

        self.audio_player_path = None  # Chemin du lecteur audio préféré

        self.toggle_flac_state = True  # True = sélectionner les .flac, False = sélectionner tout sauf les .flac

        self._create_widgets()
        self._create_menu()

        self.queue = queue.Queue()
        self.process_queue()

        self.load_config()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.filter_var.trace_add("write", lambda *args: self.redisplay_results())

        self.visible_columns = ["select", "title", "artist", "album", "bitrate", "duration", "path", "group", "date"]
        self.all_columns = ["select", "title", "artist", "album", "bitrate", "duration", "path", "group", "date"]
        self.column_names = {
            "select": "Supprimer?",
            "title": "Titre",
            "artist": "Artiste",
            "album": "Album",
            "bitrate": "Bitrate (kbps)",
            "duration": "Durée",
            "path": "Chemin du Fichier",
            "group": "Groupe",
            "date": "Date"
        }
        self._setup_treeview_columns()
        self._setup_treeview_events()

    def _create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        options_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_command(label="Choisir le lecteur audio...", command=self.choose_audio_player)

    def choose_audio_player(self):
        # Liste de lecteurs courants à proposer
        import shutil
        players = [
            ("VLC", shutil.which("vlc.exe")),
            ("Windows Media Player", shutil.which("wmplayer.exe")),
            ("Foobar2000", shutil.which("foobar2000.exe")),
            ("AIMP", shutil.which("aimp.exe")),
        ]
        players = [(name, path) for name, path in players if path]
        # Boîte de dialogue simple
        win = tk.Toplevel(self)
        win.title("Choisir le lecteur audio")
        win.geometry("400x200")
        tk.Label(win, text="Sélectionnez un lecteur audio ou parcourez...").pack(pady=10)
        var = tk.StringVar(value=self.audio_player_path or "")
        for name, path in players:
            tk.Radiobutton(win, text=f"{name} ({path})", variable=var, value=path).pack(anchor=tk.W)
        def browse():
            exe = filedialog.askopenfilename(title="Choisir un exécutable", filetypes=[("Exécutables", "*.exe")])
            if exe:
                var.set(exe)
        tk.Button(win, text="Parcourir...", command=browse).pack(pady=5)
        def valider():
            self.audio_player_path = var.get() if var.get() else None
            self.save_config()
            win.destroy()
        tk.Button(win, text="Valider", command=valider).pack(pady=10)

    def _create_widgets(self):
        """Crée et positionne tous les widgets de l'interface graphique."""

        style = ttk.Style(self)
        style.configure("Treeview.Heading",
                        borderwidth=1,
                        relief="solid",
                        background="#E1E1E1",
                        font=('Arial', 10, 'bold'))
        style.configure("Treeview", borderwidth=0)

        top_frame = tk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(top_frame, text="Dossier(s) à scanner:").pack(side=tk.LEFT, anchor=tk.N, pady=5)

        self.folder_listbox = tk.Listbox(top_frame, height=4)
        self.folder_listbox.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        folder_buttons_frame = tk.Frame(top_frame)
        folder_buttons_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self.add_folder_button = tk.Button(folder_buttons_frame, text="Ajouter...", command=self.add_folder)
        self.add_folder_button.pack(fill=tk.X, pady=2)
        self.add_multiple_folders_button = tk.Button(folder_buttons_frame, text="Ajouter plusieurs...", command=self.add_multiple_folders)
        self.add_multiple_folders_button.pack(fill=tk.X, pady=2)
        self.remove_folder_button = tk.Button(folder_buttons_frame, text="Retirer", command=self.remove_folder)
        self.remove_folder_button.pack(fill=tk.X, pady=2)

        options_frame = tk.Frame(self)
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        keep_frame = tk.LabelFrame(options_frame, text="Action par défaut")
        keep_frame.pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(keep_frame, text="Garder le plus récent", variable=self.keep_type_var, value="recent", command=self.redisplay_results).pack(anchor=tk.W)
        tk.Radiobutton(keep_frame, text="Garder le plus ancien", variable=self.keep_type_var, value="oldest", command=self.redisplay_results).pack(anchor=tk.W)

        # Ajout du slider pour la similarité des titres
        similarity_frame = tk.LabelFrame(options_frame, text="Seuil de ressemblance des titres (%)")
        similarity_frame.pack(side=tk.LEFT, padx=5)
        self.similarity_var = tk.IntVar(value=80)
        self.similarity_scale = tk.Scale(similarity_frame, from_=50, to=100, orient=tk.HORIZONTAL, variable=self.similarity_var, resolution=1)
        self.similarity_scale.pack(anchor=tk.W)
        tk.Label(similarity_frame, text="Plus le seuil est bas, plus la détection sera tolérante.").pack(anchor=tk.W)

        self.scan_button = tk.Button(options_frame, text="Scanner les Doublons", command=self.start_scan_thread)
        self.scan_button.pack(side=tk.LEFT, padx=20, ipady=10)

        progress_frame = tk.Frame(self)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        self.status_label = tk.Label(progress_frame, text="Prêt.")
        self.status_label.pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        filter_frame = tk.Frame(self)
        filter_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        tk.Label(filter_frame, text="Filtrer les résultats:").pack(side=tk.LEFT, padx=(0, 5))
        filter_entry = tk.Entry(filter_frame, textvariable=self.filter_var)
        filter_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        tree_frame = tk.Frame(self)
        tree_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        columns = ("select", "title", "artist", "album", "bitrate", "duration", "path", "group", "date")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        self.tree.tag_configure('oddrow', background='white')
        self.tree.tag_configure('evenrow', background='#F0F0F0')

        self.tree.heading("select", text="Supprimer?")
        self.tree.heading("title", text="Titre")
        self.tree.heading("artist", text="Artiste")
        self.tree.heading("album", text="Album")
        self.tree.heading("bitrate", text="Bitrate (kbps)")
        self.tree.heading("duration", text="Durée")
        self.tree.heading("path", text="Chemin du Fichier")
        self.tree.heading("group", text="Groupe")
        self.tree.heading("date", text="Date")

        for col in ("title", "artist", "album", "bitrate", "path", "group", "date"):
            self.tree.heading(col, command=lambda c=col: self.sort_treeview_column(c, False))

        self.tree.column("select", width=80, anchor=tk.CENTER)
        self.tree.column("title", width=200)
        self.tree.column("artist", width=150)
        self.tree.column("album", width=200)
        self.tree.column("bitrate", width=100, anchor=tk.CENTER)
        self.tree.column("duration", width=90, anchor=tk.CENTER, stretch=True)
        self.tree.column("path", width=300)
        self.tree.column("group", width=100, anchor=tk.CENTER)
        self.tree.column("date", width=150, anchor=tk.CENTER)

        self.tree.bind("<Button-1>", self.toggle_selection)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Double-1>", self.play_selected_audio)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(expand=True, fill=tk.BOTH)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Tout sélectionner dans ce groupe", command=self.select_group)
        self.context_menu.add_command(label="Tout désélectionner dans ce groupe", command=self.deselect_group)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Écouter ce fichier", command=lambda: self.play_selected_audio(None))

        # --- BOUTONS DE SÉLECTION AVANCÉE ET SUPPRESSION EN BAS ---
        bottom_frame = tk.Frame(self)
        bottom_frame.pack(fill=tk.X, pady=10)
        # Frame pour les boutons de sélection à gauche
        selection_frame = tk.Frame(bottom_frame)
        selection_frame.pack(side=tk.LEFT, anchor="w")
        tk.Button(selection_frame, text="Sélectionner tous les .flac", command=self.select_all_flac_files).pack(side=tk.LEFT, padx=5)
        self.toggle_bitrate_state = True  # True = sélectionner, False = désélectionner
        self.toggle_bitrate_btn = tk.Button(selection_frame, text="Toggle plus gros bitrate/groupe", command=self.toggle_highest_bitrate_per_group)
        self.toggle_bitrate_btn.pack(side=tk.LEFT, padx=5)
        # Bouton de suppression à droite
        self.delete_button = tk.Button(bottom_frame, text="Mettre à la corbeille (0)", state="disabled", command=self.delete_duplicates)
        self.delete_button.pack(side=tk.RIGHT, padx=10)

    def on_closing(self):
        """Gère la fermeture de l'application : sauvegarde la config et quitte pygame."""
        self.save_config()
        self.destroy()

    def save_config(self):
        """Sauvegarde les paramètres actuels dans le fichier config.json."""
        config_data = {
            "folder_paths": self.folder_paths,
            "keep_type": self.keep_type_var.get(),
            "audio_player_path": self.audio_player_path,
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=4)
        except IOError as e:
            print(f"Could not save config file: {e}")

    def load_config(self):
        """Charge les paramètres depuis config.json s'il existe."""
        try:
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
            
            self.keep_type_var.set(config_data.get("keep_type", "recent"))
            self.audio_player_path = config_data.get("audio_player_path", None)

            self.folder_paths = config_data.get("folder_paths", [])
            self.folder_listbox.delete(0, tk.END)
            for path in self.folder_paths:
                self.folder_listbox.insert(tk.END, path)

        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def play_selected_audio(self, event):
        """Ouvre le fichier audio sélectionné avec le lecteur choisi ou le lecteur par défaut du système."""
        selected_item = self.tree.selection()
        if not selected_item:
            return
        file_path = selected_item[0]
        try:
            if self.audio_player_path:
                import subprocess
                subprocess.Popen([self.audio_player_path, file_path])
            else:
                os.startfile(file_path)
        except Exception as e:
            messagebox.showerror("Erreur d'ouverture", f"Impossible d'ouvrir le fichier audio :\n{e}")

    def clear_results_data(self):
        """Efface toutes les données des résultats de l'analyse en cours."""
        self.all_groups = []
        self.hidden_items = set()
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.update_delete_button()
        self.status_label.config(text="Prêt.")

    def add_folder(self):
        """Ouvre une boîte de dialogue pour ajouter un dossier à la liste."""
        path = filedialog.askdirectory()
        if path and path not in self.folder_paths:
            self.folder_paths.append(path)
            self.folder_listbox.insert(tk.END, path)
            self.clear_results_data()

    def add_multiple_folders(self):
        """Ouvre une boîte de dialogue personnalisée pour ajouter plusieurs dossiers."""
        dialog = AskMultipleFoldersDialog(self)
        new_paths = dialog.paths
        added_count = 0
        if new_paths:
            for path in new_paths:
                if path not in self.folder_paths:
                    self.folder_paths.append(path)
                    self.folder_listbox.insert(tk.END, path)
                    added_count += 1
            if added_count > 0:
                self.clear_results_data()

    def remove_folder(self):
        """Retire le dossier sélectionné de la liste."""
        selected_indices = self.folder_listbox.curselection()
        if not selected_indices:
            return
        for i in sorted(selected_indices, reverse=True):
            del self.folder_paths[i]
            self.folder_listbox.delete(i)
        self.clear_results_data()

    def start_scan_thread(self):
        """Lance le scan des doublons dans un thread séparé pour ne pas bloquer l'UI."""
        if self.scan_in_progress:
            return
        if not self.folder_paths:
            messagebox.showerror("Erreur", "Veuillez ajouter au moins un dossier à analyser.")
            return

        self.scan_in_progress = True
        self.scan_button.config(state="disabled")
        self.add_folder_button.config(state="disabled")
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
        """Traite les messages reçus du thread de scan (statut, progression, résultats)."""
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
                    self.redisplay_results()
                elif msg_type == "finished":
                    self.scan_in_progress = False
                    self.scan_button.config(state="normal")
                    self.add_folder_button.config(state="normal")
                    self.add_multiple_folders_button.config(state="normal")
                    self.remove_folder_button.config(state="normal")
                    self.status_label.config(text="Analyse terminée.")
                    self.progress_bar["value"] = 0
        except queue.Empty:
            self.after(100, self.process_queue)

    def _setup_treeview_columns(self):
        self.tree["displaycolumns"] = self.visible_columns
        for col in self.all_columns:
            self.tree.heading(col, text=self.column_names[col], command=lambda c=col: self.sort_treeview_column(c, False))

    def _setup_treeview_events(self):
        # Drag & drop colonnes
        self.tree.bind('<ButtonPress-1>', self._on_treeview_heading_press, add='+')
        self.tree.bind('<B1-Motion>', self._on_treeview_heading_motion, add='+')
        self.tree.bind('<ButtonRelease-1>', self._on_treeview_heading_release, add='+')
        # Menu contextuel colonnes
        self.tree.bind('<Button-3>', self._on_treeview_heading_right_click, add='+')
        self._dragged_col = None
        self._dragged_col_index = None
        self._col_menu = None

    def _on_treeview_heading_press(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == 'heading':
            col = self.tree.identify_column(event.x)
            col_index = int(col.replace('#', '')) - 1
            self._dragged_col = self.visible_columns[col_index]
            self._dragged_col_index = col_index
        else:
            self._dragged_col = None
            self._dragged_col_index = None

    def _on_treeview_heading_motion(self, event):
        if self._dragged_col is None:
            return
        region = self.tree.identify_region(event.x, event.y)
        if region != 'heading':
            return
        col = self.tree.identify_column(event.x)
        col_index = int(col.replace('#', '')) - 1
        if col_index != self._dragged_col_index and 0 <= col_index < len(self.visible_columns):
            # Ne pas permettre de déplacer la colonne 'select'
            if self._dragged_col == 'select' or self.visible_columns[col_index] == 'select':
                return
            self.visible_columns.insert(col_index, self.visible_columns.pop(self._dragged_col_index))
            self.tree["displaycolumns"] = self.visible_columns
            self._dragged_col_index = col_index

    def _on_treeview_heading_release(self, event):
        self._dragged_col = None
        self._dragged_col_index = None

    def _on_treeview_heading_right_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != 'heading':
            return
        if self._col_menu:
            self._col_menu.destroy()
        self._col_menu = tk.Menu(self, tearoff=0)
        for col in self.all_columns:
            if col == 'select':
                continue  # Toujours visible
            checked = tk.BooleanVar(value=col in self.visible_columns)
            def toggle_col(c=col, var=checked):
                if var.get():
                    if c not in self.visible_columns:
                        # Ajoute à la fin sauf si c'était masqué
                        self.visible_columns.append(c)
                else:
                    if c in self.visible_columns:
                        self.visible_columns.remove(c)
                # Toujours au moins une colonne visible en plus de 'select'
                if len(self.visible_columns) < 2:
                    self.visible_columns.append(c)
                # 'select' toujours en premier
                if 'select' in self.visible_columns:
                    self.visible_columns.remove('select')
                    self.visible_columns.insert(0, 'select')
                self.tree["displaycolumns"] = self.visible_columns
            self._col_menu.add_checkbutton(label=self.column_names[col], variable=checked, command=toggle_col)
        self._col_menu.tk_popup(event.x_root, event.y_root)

    def _get_column_index(self, col_name):
        # Retourne l'index de la colonne (dans self.visible_columns) pour le Treeview
        try:
            return self.visible_columns.index(col_name)
        except ValueError:
            return -1

    # Adapter redisplay_results pour n'afficher que les colonnes visibles
    def redisplay_results(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        if not self.all_groups:
            return
        filter_query = self.filter_var.get().lower()
        keep_type = self.keep_type_var.get()
        group_id = 1
        item_index = 0
        any_duration = False
        for group in self.all_groups:
            group.sort(key=lambda f: f.get("bitrate", 0), reverse=True)
            group.sort(key=lambda f: f["date"])
            file_to_keep = group[-1] if keep_type == "recent" else group[0]
            for file_info in group:
                path = file_info["path"]
                if path in self.hidden_items:
                    continue
                if filter_query:
                    searchable_values = (
                        str(file_info.get("title", "")),
                        str(file_info.get("artist", "")),
                        str(file_info.get("album", "")),
                        str(file_info.get("path", ""))
                    )
                    if not any(filter_query in v.lower() for v in searchable_values):
                        continue
                display_path = path
                for folder in self.folder_paths:
                    if path.startswith(folder):
                        display_path = os.path.relpath(path, os.path.dirname(folder))
                        break
                date_str = datetime.datetime.fromtimestamp(file_info["date"]).strftime('%Y-%m-%d %H:%M:%S')
                is_duplicate = (file_info != file_to_keep)
                check_char = "✓" if is_duplicate else "☐"
                tag = 'evenrow' if item_index % 2 == 0 else 'oddrow'
                # Format durée (en secondes) en mm:ss
                duration_sec = file_info.get("duration", 0)
                if duration_sec is None:
                    duration_sec = 0
                if isinstance(duration_sec, str):
                    try:
                        duration_sec = float(duration_sec)
                    except Exception:
                        duration_sec = 0
                if duration_sec > 0:
                    any_duration = True
                minutes = int(duration_sec // 60)
                seconds = int(duration_sec % 60)
                duration_str = f"{minutes}:{seconds:02d}" if duration_sec > 0 else "-"
                values_dict = {
                    "select": check_char,
                    "title": file_info.get("title", "N/A"),
                    "artist": file_info.get("artist", "N/A"),
                    "album": file_info.get("album", "N/A"),
                    "bitrate": file_info.get("bitrate", 0),
                    "duration": duration_str,
                    "path": display_path,
                    "group": f"Groupe {group_id}",
                    "date": date_str
                }
                values = tuple(values_dict[col] for col in self.visible_columns)
                self.tree.insert("", "end", iid=path, values=values, tags=(tag,))
                item_index += 1
            group_id += 1
        self.update_delete_button()
        self.tree["displaycolumns"] = self.visible_columns
        # Affiche un avertissement si aucune durée n'est trouvée
        if not any_duration and "duration" in self.visible_columns:
            self.status_label.config(text="Aucune durée trouvée : le scan ne fournit pas la durée des fichiers.")

    def get_selected_files(self):
        """Retourne la liste des chemins des fichiers cochés pour suppression."""
        return [item_id for item_id in self.tree.get_children() if self.tree.item(item_id, "values")[0] == "✓"]

    def update_delete_button(self):
        """Met à jour l'état et le texte du bouton de suppression en fonction du nombre de fichiers sélectionnés."""
        count = len(self.get_selected_files())
        state = "normal" if count > 0 else "disabled"
        self.delete_button.config(state=state, text=f"Mettre à la corbeille ({count})")

    def delete_duplicates(self):
        """Déplace les fichiers sélectionnés vers la corbeille."""
        files_to_delete = self.get_selected_files()
        if not files_to_delete:
            return

        msg = f"Êtes-vous sûr de vouloir déplacer {len(files_to_delete)} fichier(s) vers la corbeille ?"
        if messagebox.askyesno("Confirmation", msg):
            deleted_count, error_count = 0, 0
            errors = []
            for f_path in files_to_delete:
                # Nettoyage du chemin (suppression des préfixes spéciaux et normalisation)
                clean_path = os.path.normpath(f_path)
                if clean_path.startswith('\\\\?\\'):
                    clean_path = clean_path[4:]
                if not os.path.exists(clean_path):
                    errors.append(f"- {clean_path}: Fichier introuvable (déjà supprimé ou déplacé)")
                    error_count += 1
                    continue
                try:
                    send2trash(clean_path)
                    self.tree.delete(f_path)
                    deleted_count += 1
                except Exception as e:
                    errors.append(f"- {clean_path}: {e}")
                    error_count += 1

            self.all_groups = [
                [file_info for file_info in group if file_info["path"] not in files_to_delete]
                for group in self.all_groups
            ]
            self.all_groups = [group for group in self.all_groups if len(group) > 1]

            info_message = f"{deleted_count} fichier(s) déplacé(s) vers la corbeille."
            if error_count > 0:
                info_message += f"\n{error_count} erreur(s) lors du déplacement:\n" + "\n".join(errors)
            messagebox.showinfo("Opération Terminée", info_message)

            self.redisplay_results()
            self.update_delete_button()

    def toggle_selection(self, event):
        """Inverse la sélection (coché/décoché) d'une ligne sur un clic."""
        row_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)
        if not row_id or column_id != "#1":
            return

        current_values = list(self.tree.item(row_id, "values"))
        current_check = current_values[0]
        current_values[0] = "☐" if current_check == "✓" else "✓"
        self.tree.item(row_id, values=tuple(current_values))
        self.update_delete_button()

    def show_context_menu(self, event):
        """Affiche le menu contextuel sur un clic droit."""
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.context_menu.post(event.x_root, event.y_root)

    def _get_group_from_item(self, item_id):
        """Helper pour récupérer l'ID de groupe d'un élément du Treeview."""
        return self.tree.item(item_id, "values")[6]

    def _toggle_group_selection(self, select):
        """Coche ou décoche tous les éléments du même groupe que l'élément sélectionné."""
        if not self.tree.selection():
            return
        selected_item = self.tree.selection()[0]
        target_group = self._get_group_from_item(selected_item)

        for item_id in self.tree.get_children():
            if self._get_group_from_item(item_id) == target_group:
                current_values = list(self.tree.item(item_id, "values"))
                current_values[0] = "✓" if select else "☐"
                self.tree.item(item_id, values=tuple(current_values))
        self.update_delete_button()

    def select_group(self):
        """Coche tous les éléments du groupe sélectionné."""
        self._toggle_group_selection(True)

    def deselect_group(self):
        """Décoche tous les éléments du groupe sélectionné."""
        self._toggle_group_selection(False)

    def hide_item(self):
        """Masque l'élément sélectionné de la liste des résultats."""
        if not self.tree.selection():
            return
        selected_item = self.tree.selection()[0]
        self.hidden_items.add(selected_item)
        self.tree.detach(selected_item)
        self.update_delete_button()

    def unhide_all_items(self):
        """Réaffiche tous les éléments qui ont été masqués."""
        self.hidden_items.clear()
        self.redisplay_results()

    def sort_treeview_column(self, col, reverse):
        """Trie le Treeview en fonction de la colonne cliquée."""
        try:
            if col == "group":
                data = [(int(self.tree.set(item, col).split(" ")[1]), item) for item in self.tree.get_children('')]
            elif col == "bitrate":
                data = [(int(self.tree.set(item, col)), item) for item in self.tree.get_children('')]
            else:
                data = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]

            data.sort(reverse=reverse)

            for index, (val, item) in enumerate(data):
                self.tree.move(item, '', index)

            self.tree.heading(col, command=lambda: self.sort_treeview_column(col, not reverse))
        except Exception as e:
            print(f"Erreur de tri: {e}")

    def select_all_flac_files(self):
        """Toggle : coche tous les fichiers .flac OU tous les fichiers sauf les .flac."""
        select_idx = self._get_column_index("select")
        if select_idx == -1:
            return
        for item_id in self.tree.get_children():
            values = list(self.tree.item(item_id, "values"))
            is_flac = str(item_id).lower().endswith('.flac')
            if self.toggle_flac_state:
                values[select_idx] = "✓" if is_flac else "☐"
            else:
                values[select_idx] = "✓" if not is_flac else "☐"
            self.tree.item(item_id, values=tuple(values))
        self.toggle_flac_state = not self.toggle_flac_state
        self.update_delete_button()

    def toggle_highest_bitrate_per_group(self):
        """Toggle la sélection du fichier avec le plus gros bitrate dans chaque groupe. Si plusieurs ont le même bitrate, sélectionne TOUJOURS le plus ancien, sans alternance."""
        group_idx = self._get_column_index("group")
        bitrate_idx = self._get_column_index("bitrate")
        date_idx = self._get_column_index("date")
        select_idx = self._get_column_index("select")
        if group_idx == -1 or bitrate_idx == -1 or date_idx == -1 or select_idx == -1:
            return
        group_map = {}
        for item_id in self.tree.get_children():
            group = self.tree.item(item_id, "values")[group_idx]
            group_map.setdefault(group, []).append(item_id)
        for group_items in group_map.values():
            # Trouver le(s) item(s) avec le plus gros bitrate
            max_bitrate = -1
            max_items = []
            for item_id in group_items:
                try:
                    bitrate = int(self.tree.item(item_id, "values")[bitrate_idx])
                except Exception:
                    bitrate = 0
                if bitrate > max_bitrate:
                    max_bitrate = bitrate
                    max_items = [item_id]
                elif bitrate == max_bitrate:
                    max_items.append(item_id)
            # Si plusieurs, choisir le plus ancien (date la plus petite)
            min_date = None
            min_item = None
            for item_id in max_items:
                try:
                    date_str = self.tree.item(item_id, "values")[date_idx]
                    date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').timestamp()
                except Exception:
                    date = float('inf')
                if min_date is None or date < min_date:
                    min_date = date
                    min_item = item_id
            # Si plusieurs fichiers ont le même bitrate max, TOUJOURS sélectionner le plus ancien
            if len(max_items) > 1:
                for item_id in group_items:
                    values = list(self.tree.item(item_id, "values"))
                    values[select_idx] = "✓" if item_id == min_item else "☐"
                    self.tree.item(item_id, values=tuple(values))
            else:
                # Toggle normal si un seul fichier a le plus gros bitrate
                for item_id in group_items:
                    values = list(self.tree.item(item_id, "values"))
                    if item_id == min_item:
                        values[select_idx] = "☐" if self.toggle_bitrate_state else "✓"
                    else:
                        values[select_idx] = "✓" if self.toggle_bitrate_state else "☐"
                    self.tree.item(item_id, values=tuple(values))
        self.toggle_bitrate_state = not self.toggle_bitrate_state
        self.update_delete_button()

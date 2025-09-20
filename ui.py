import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import datetime
import threading
import queue
import os

from scanner import scan_duplicates
from dialogs import AskMultipleFoldersDialog

class DuplicateMusicFinder(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Détecteur de Doublons de Musique")
        self.geometry("1200x800")

        self.folder_paths = []
        self.date_type_var = tk.StringVar(value="modification")
        self.keep_type_var = tk.StringVar(value="recent")
        self.similarity_threshold_var = tk.DoubleVar(value=85)
        self.scan_in_progress = False

        self.all_groups = []
        self.hidden_items = set()

        self._create_widgets()

        self.queue = queue.Queue()
        self.process_queue()

    def _create_widgets(self):
        """Crée et positionne tous les widgets de l'interface."""

        # --- Cadre supérieur pour la sélection des dossiers ---
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

        # --- Cadre pour les options ---
        options_frame = tk.Frame(self)
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        date_frame = tk.LabelFrame(options_frame, text="Trier par date de")
        date_frame.pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(date_frame, text="Modification", variable=self.date_type_var, value="modification", command=self.ask_clear_results).pack(anchor=tk.W)
        tk.Radiobutton(date_frame, text="Création", variable=self.date_type_var, value="creation", command=self.ask_clear_results).pack(anchor=tk.W)

        keep_frame = tk.LabelFrame(options_frame, text="Action par défaut")
        keep_frame.pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(keep_frame, text="Garder le plus récent", variable=self.keep_type_var, value="recent", command=self.redisplay_results).pack(anchor=tk.W)
        tk.Radiobutton(keep_frame, text="Garder le plus ancien", variable=self.keep_type_var, value="oldest", command=self.redisplay_results).pack(anchor=tk.W)

        # Seuil de similarité
        similarity_frame = tk.LabelFrame(options_frame, text="Seuil de similarité (%)")
        similarity_frame.pack(side=tk.LEFT, padx=5, fill=tk.Y)

        self.similarity_spinbox = ttk.Spinbox(
            similarity_frame,
            from_=0,
            to=100,
            textvariable=self.similarity_threshold_var,
            wrap=True,
            width=5,
            command=self.ask_clear_results
        )
        self.similarity_spinbox.pack(padx=5, pady=10)
        # Lier la modification manuelle du texte à la vérification
        self.similarity_threshold_var.trace_add("write", self.on_similarity_change)


        self.scan_button = tk.Button(options_frame, text="Scanner les Doublons", command=self.start_scan_thread)
        self.scan_button.pack(side=tk.LEFT, padx=20, ipady=10)

        # --- Cadre de progression ---
        progress_frame = tk.Frame(self)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        self.status_label = tk.Label(progress_frame, text="Prêt.")
        self.status_label.pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        # --- Treeview pour les résultats ---
        tree_frame = tk.Frame(self)
        tree_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        self.tree = ttk.Treeview(tree_frame, columns=("select", "path", "group", "date", "status"), show="headings")
        self.tree.heading("select", text="Supprimer?")
        self.tree.heading("path", text="Chemin du Fichier")
        self.tree.heading("group", text="Groupe")
        self.tree.heading("date", text="Date")
        self.tree.heading("status", text="Statut")

        for col in ("path", "group", "date", "status"):
            self.tree.heading(col, command=lambda c=col: self.sort_treeview_column(c, False))

        self.tree.column("select", width=80, anchor=tk.CENTER)
        self.tree.column("path", width=500)
        self.tree.column("group", width=100, anchor=tk.CENTER)
        self.tree.column("date", width=150, anchor=tk.CENTER)
        self.tree.column("status", width=100, anchor=tk.CENTER)

        self.tree.bind("<Button-1>", self.toggle_selection)
        self.tree.bind("<Button-3>", self.show_context_menu)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(expand=True, fill=tk.BOTH)

        # --- Menu contextuel ---
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Tout sélectionner dans ce groupe", command=self.select_group)
        self.context_menu.add_command(label="Tout désélectionner dans ce groupe", command=self.deselect_group)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Masquer cet élément", command=self.hide_item)
        self.context_menu.add_command(label="Afficher les éléments masqués", command=self.unhide_all_items)

        # --- Bouton de suppression ---
        self.delete_button = tk.Button(self, text="Supprimer les fichiers sélectionnés (0)", state="disabled", command=self.delete_duplicates)
        self.delete_button.pack(pady=10)

    def on_similarity_change(self, *args):
        """Appelé quand la valeur du seuil de similarité change."""
        # On utilise after pour laisser le temps à la variable de se mettre à jour
        # et éviter des appels récursifs ou des erreurs de validation.
        self.after(50, self.ask_clear_results)

    def ask_clear_results(self, *args):
        if not self.all_groups:
            return
        if messagebox.askyesno("Paramètres modifiés", "Les paramètres de scan ont changé. Cela nécessite un nouveau scan.\nVoulez-vous effacer les résultats actuels ?"):
            self.clear_results_data()

    def clear_results_data(self):
        self.all_groups = []
        self.hidden_items = set()
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.update_delete_button()
        self.status_label.config(text="Prêt.")

    def add_folder(self):
        path = filedialog.askdirectory()
        if path and path not in self.folder_paths:
            self.folder_paths.append(path)
            self.folder_listbox.insert(tk.END, path)
            self.ask_clear_results()

    def add_multiple_folders(self):
        """Ouvre une boîte de dialogue pour ajouter plusieurs dossiers."""
        dialog = AskMultipleFoldersDialog(self)
        # La fenêtre attend que la dialogue soit fermée, puis récupère les chemins
        new_paths = dialog.paths

        added_count = 0
        if new_paths:
            for path in new_paths:
                # Éviter les doublons dans la liste
                if path not in self.folder_paths:
                    self.folder_paths.append(path)
                    self.folder_listbox.insert(tk.END, path)
                    added_count += 1

            if added_count > 0:
                self.ask_clear_results()

    def remove_folder(self):
        selected_indices = self.folder_listbox.curselection()
        if not selected_indices:
            return
        for i in sorted(selected_indices, reverse=True):
            del self.folder_paths[i]
            self.folder_listbox.delete(i)
        self.ask_clear_results()

    def start_scan_thread(self):
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
            args=(
                self.folder_paths.copy(),
                self.date_type_var.get(),
                self.similarity_threshold_var.get(),
                self.queue
            ),
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

    def redisplay_results(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        if not self.all_groups:
            return

        keep_type = self.keep_type_var.get()
        group_id = 1
        for group in self.all_groups:
            group.sort(key=lambda f: f["date"])
            file_to_keep = group[-1] if keep_type == "recent" else group[0]

            for file_info in group:
                path = file_info["path"]
                if path in self.hidden_items:
                    continue

                date_str = datetime.datetime.fromtimestamp(file_info["date"]).strftime('%Y-%m-%d %H:%M:%S')
                is_duplicate = (file_info != file_to_keep)
                check_char = "✓" if is_duplicate else "☐"
                status = "À supprimer" if is_duplicate else "À garder"

                self.tree.insert("", "end", iid=path, values=(check_char, path, f"Groupe {group_id}", date_str, status))
            group_id += 1
        self.update_delete_button()

    def get_selected_files(self):
        return [item_id for item_id in self.tree.get_children() if self.tree.item(item_id, "values")[0] == "✓"]

    def update_delete_button(self):
        count = len(self.get_selected_files())
        state = "normal" if count > 0 else "disabled"
        self.delete_button.config(state=state, text=f"Supprimer les fichiers sélectionnés ({count})")

    def delete_duplicates(self):
        files_to_delete = self.get_selected_files()
        if not files_to_delete:
            return

        msg = f"Êtes-vous sûr de vouloir supprimer définitivement {len(files_to_delete)} fichier(s) ?\n\nCette action est irréversible."
        if messagebox.askyesno("Confirmation de Suppression", msg):
            deleted_count, error_count = 0, 0
            errors = []
            for f_path in files_to_delete:
                try:
                    os.remove(f_path)
                    self.tree.delete(f_path)
                    deleted_count += 1
                except OSError as e:
                    errors.append(f"- {f_path}: {e}")
                    error_count += 1

            self.all_groups = [
                [file_info for file_info in group if file_info["path"] not in files_to_delete]
                for group in self.all_groups
            ]
            self.all_groups = [group for group in self.all_groups if len(group) > 1]

            info_message = f"{deleted_count} fichier(s) supprimé(s)."
            if error_count > 0:
                info_message += f"\n{error_count} erreur(s) lors de la suppression:\n" + "\n".join(errors)
            messagebox.showinfo("Opération Terminée", info_message)

            self.redisplay_results()
            self.update_delete_button()

    def toggle_selection(self, event):
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
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.context_menu.post(event.x_root, event.y_root)

    def _get_group_from_item(self, item_id):
        return self.tree.item(item_id, "values")[2]

    def _toggle_group_selection(self, select):
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
        self._toggle_group_selection(True)

    def deselect_group(self):
        self._toggle_group_selection(False)

    def hide_item(self):
        if not self.tree.selection():
            return
        selected_item = self.tree.selection()[0]
        self.hidden_items.add(selected_item)
        self.tree.detach(selected_item)
        self.update_delete_button()

    def unhide_all_items(self):
        self.hidden_items.clear()
        self.redisplay_results()

    def sort_treeview_column(self, col, reverse):
        try:
            if col == "group":
                data = [(int(self.tree.set(item, col).split(" ")[1]), item) for item in self.tree.get_children('')]
            else:
                data = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]

            data.sort(reverse=reverse)

            for index, (val, item) in enumerate(data):
                self.tree.move(item, '', index)

            self.tree.heading(col, command=lambda: self.sort_treeview_column(col, not reverse))
        except Exception as e:
            print(f"Erreur de tri: {e}")

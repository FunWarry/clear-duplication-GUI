from tkinter import filedialog

class FoldersMixin:
    """Ajout / retrait des dossiers à analyser."""
    def _init_folders_state(self):
        if not hasattr(self, 'folder_paths'):
            self.folder_paths = []

    def add_folder(self):
        path = filedialog.askdirectory()
        if path and path not in self.folder_paths:
            self.folder_paths.append(path)
            try:
                self.folder_listbox.insert('end', path)
            except Exception:
                pass
            self.clear_results_data()

    def add_multiple_folders(self):
        try:
            from dialogs import AskMultipleFoldersDialog
        except Exception:
            return
        dialog = AskMultipleFoldersDialog(self)
        added = False
        for p in getattr(dialog, 'paths', []):
            if p not in self.folder_paths:
                self.folder_paths.append(p); added = True
                try: self.folder_listbox.insert('end', p)
                except Exception: pass
        if added:
            self.clear_results_data()

    def remove_folder(self):
        try:
            selection = list(self.folder_listbox.curselection())
        except Exception:
            selection = []
        if not selection:
            return
        for idx in sorted(selection, reverse=True):
            try:
                del self.folder_paths[idx]
                self.folder_listbox.delete(idx)
            except Exception:
                pass
        self.clear_results_data()


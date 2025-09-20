import tkinter as tk
from tkinter import messagebox, filedialog
import os

class AskMultipleFoldersDialog(tk.Toplevel):
    """
    Une boîte de dialogue Toplevel pour permettre à l'utilisateur de sélectionner
    plusieurs dossiers via l'explorateur de fichiers.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("Ajouter plusieurs dossiers")
        self.geometry("600x400")

        self.paths = []  # Pour stocker les chemins valides

        # Frame principal
        main_frame = tk.Frame(self)
        main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Bouton pour ajouter un dossier
        browse_button = tk.Button(main_frame, text="Parcourir...", command=self.browse_folder)
        browse_button.pack(pady=(0, 10))

        # Listbox pour afficher les dossiers sélectionnés
        self.listbox = tk.Listbox(main_frame)
        self.listbox.pack(expand=True, fill=tk.BOTH)

        # Frame pour les boutons de validation
        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)

        ok_button = tk.Button(button_frame, text="Valider", command=self.on_ok)
        ok_button.pack(side=tk.LEFT, padx=5)

        cancel_button = tk.Button(button_frame, text="Annuler", command=self.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set() # Rendre la fenêtre modale
        self.wait_window(self)

    def browse_folder(self):
        """Ouvre l'explorateur de fichiers pour sélectionner un dossier."""
        path = filedialog.askdirectory(parent=self)
        if path and path not in self.listbox.get(0, tk.END):
            self.listbox.insert(tk.END, path)

    def on_ok(self):
        """
        Appelé lorsque l'utilisateur clique sur 'Valider'.
        Récupère les chemins de la listbox et ferme la fenêtre.
        """
        self.paths = list(self.listbox.get(0, tk.END))
        self.destroy()

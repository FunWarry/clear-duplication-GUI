import threading, queue
from tkinter import messagebox
from scanner import scan_duplicates

class ScanMixin:
    """Gestion du lancement du scan et du traitement de la file de messages."""
    def _init_scan_state(self):
        self.scan_in_progress = False
        self.queue = queue.Queue()
        # Démarrer boucle de traitement
        self.after(150, self.process_queue)

    def start_scan_thread(self):
        if self.scan_in_progress:
            return
        if not getattr(self, 'folder_paths', None):
            messagebox.showerror("Erreur", "Veuillez ajouter au moins un dossier.")
            return
        self.scan_in_progress = True
        try:
            self.scan_button.config(state='disabled')
        except Exception:
            pass
        try:  # Désactiver ajout dossiers si présent
            self.status_label.config(text="Analyse en cours...")
        except Exception:
            pass
        try:
            self.clear_results_data()
        except Exception:
            pass
        t = threading.Thread(
            target=scan_duplicates,
            args=(self.folder_paths.copy(), self.keep_type_var.get(), self.queue, self.similarity_var.get() / 100.0),
            daemon=True
        )
        t.start()

    def process_queue(self):
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == 'status':
                    try: self.status_label.config(text=data)
                    except Exception: pass
                elif msg_type == 'progress':
                    try: self.progress_bar['value'] = data
                    except Exception: pass
                elif msg_type == 'progress_max':
                    try: self.progress_bar['maximum'] = data
                    except Exception: pass
                elif msg_type == 'message':
                    level, text = data
                    try:
                        (messagebox.showinfo if level == 'info' else messagebox.showerror)(
                            'Information' if level == 'info' else 'Erreur', text)
                    except Exception:
                        pass
                elif msg_type == 'results':
                    self.all_groups = data
                    self.redisplay_results(preserve_selection=False)
                elif msg_type == 'finished':
                    self.scan_in_progress = False
                    try: self.scan_button.config(state='normal')
                    except Exception: pass
                    try: self.status_label.config(text='Analyse terminée.')
                    except Exception: pass
                    try: self.progress_bar['value'] = 0
                    except Exception: pass
        except queue.Empty:
            pass
        finally:
            # Replanifier
            self.after(150, self.process_queue)


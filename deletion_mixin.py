import os
from send2trash import send2trash
from tkinter import messagebox

class DeletionMixin:
    """Suppression (envoi corbeille) des fichiers cochés et mise à jour des groupes."""

    def delete_duplicates(self):
        files = self.get_selected_files() if hasattr(self, 'get_selected_files') else []
        if not files:
            messagebox.showwarning("Aucune sélection", "Aucun fichier sélectionné.")
            return
        base_dirs = getattr(self, 'folder_paths', [])[:]
        validated = []
        reconstructed = []
        for p in files:
            orig = p
            abs_p = os.path.abspath(p)
            exists = os.path.exists(abs_p)
            if not exists and not os.path.isabs(p):
                for base in base_dirs:
                    cand = os.path.abspath(os.path.join(base, p))
                    if os.path.exists(cand):
                        abs_p = cand; exists = True; reconstructed.append((orig, cand)); break
            validated.append((orig, abs_p, exists))
        if any(not e for *_, e in validated):
            missing = "\n".join(f"- {o} (tentative: {a})" for (o,a,e) in validated if not e)
            if not messagebox.askyesno("Fichiers introuvables", "Certains fichiers seront ignorés :\n"+missing+"\nContinuer ?"):
                return
        existing = [a for (o,a,e) in validated if e]
        if not existing:
            messagebox.showerror("Suppression", "Aucun fichier existant trouvé.")
            return
        lines = [f"{len(existing)} fichier(s) seront envoyés à la corbeille."]
        if reconstructed:
            lines.append(f"{len(reconstructed)} chemin(s) reconstruits.")
        if len(existing) <= 10:
            lines.append("Liste :"); lines.extend(existing)
        if not messagebox.askyesno("Confirmation", "\n".join(lines)+"\nConfirmer ?"):
            return
        errors = []
        for p in existing:
            try: send2trash(p)
            except Exception as e: errors.append(f"- {p}: {e}")
        if errors:
            messagebox.showwarning("Erreurs", "Certaines suppressions ont échoué :\n"+"\n".join(errors))
        # Mise à jour groupes (suppression des entrées disparues)
        deleted_norm = {os.path.normcase(os.path.abspath(p)) for p in existing}
        new_groups = []
        for g in getattr(self, 'all_groups', []):
            kept = []
            for fi in g:
                try: normp = os.path.normcase(os.path.abspath(fi['path']))
                except Exception: normp = fi.get('path')
                if normp not in deleted_norm:
                    kept.append(fi)
            if len(kept) > 1:
                new_groups.append(kept)
        self.all_groups = new_groups
        try:
            self.redisplay_results(preserve_selection=False)
        except Exception:
            pass
        messagebox.showinfo("Terminé", f"Suppression effectuée. {len(existing)} fichier(s) envoyé(s) à la corbeille.")


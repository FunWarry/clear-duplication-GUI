import os
from rapidfuzz import fuzz

def scan_duplicates(paths_to_scan, date_type, similarity_threshold, queue):
    """
    Scanne les dossiers à la recherche de fichiers musicaux en double.

    Cette fonction est conçue pour être exécutée dans un thread séparé afin de ne pas
    bloquer l'interface utilisateur. Elle communique les résultats et la progression
    via une file d'attente (queue).

    Args:
        paths_to_scan (list): Liste des chemins de dossier à analyser.
        date_type (str): Le critère de date à utiliser ('modification' ou 'creation').
        similarity_threshold (float): Le seuil de similarité pour comparer les noms de fichiers.
        queue (queue.Queue): La file d'attente pour envoyer des messages à l'interface utilisateur.
    """
    try:
        # Étape 1: Collecte des fichiers musicaux
        queue.put(("status", "Étape 1/3: Recherche des fichiers musicaux..."))
        music_files = []
        supported_extensions = ('.mp3', '.flac', '.wav', '.m4a', '.ogg')

        all_files = []
        for path in paths_to_scan:
            for root, _, files in os.walk(path):
                for f in files:
                    all_files.append(os.path.join(root, f))

        queue.put(("progress_max", len(all_files)))
        for i, full_path in enumerate(all_files):
            queue.put(("progress", i + 1))
            if full_path.lower().endswith(supported_extensions):
                try:
                    stat = os.stat(full_path)
                    music_files.append({
                        "path": full_path,
                        "name": os.path.splitext(os.path.basename(full_path))[0],
                        "date": stat.st_mtime if date_type == "modification" else stat.st_ctime
                    })
                except FileNotFoundError:
                    continue  # Le fichier a peut-être été supprimé entre-temps

        if not music_files:
            queue.put(("message", ("info", "Aucun fichier musical trouvé.")))
            return

        # Étape 2: Groupement des fichiers par similarité de nom
        queue.put(("status", f"Étape 2/3: Analyse de {len(music_files)} fichiers..."))
        queue.put(("progress_max", len(music_files)))
        groups = []
        processed_indices = set()

        for i in range(len(music_files)):
            queue.put(("progress", i + 1))
            if i in processed_indices:
                continue

            current_group = [music_files[i]]
            processed_indices.add(i)

            for j in range(i + 1, len(music_files)):
                if j in processed_indices:
                    continue

                # Comparaison avec rapidfuzz pour la performance
                if fuzz.ratio(music_files[i]["name"], music_files[j]["name"]) > similarity_threshold:
                    current_group.append(music_files[j])
                    processed_indices.add(j)

            if len(current_group) > 1:
                groups.append(current_group)

        if not groups:
            queue.put(("message", ("info", "Analyse terminée. Aucun doublon trouvé.")))
            return

        # Étape 3: Envoi des résultats pour affichage
        queue.put(("status", "Étape 3/3: Préparation de l'affichage..."))
        queue.put(("results", groups))

    except Exception as e:
        queue.put(("message", ("error", f"Une erreur est survenue durant le scan: {e}")))
    finally:
        queue.put(("finished", None))


import os
import subprocess
from mutagen import File
import acoustid
import traceback
import hashlib
import difflib
import re
from mutagen.id3 import ID3, TXXX, ID3NoHeaderError
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4

# Path to the fpcalc executable (assuming it's in the same directory)
FPCALC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fpcalc.exe")

def file_sha1(path, block_size=65536):
    sha1 = hashlib.sha1()
    try:
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                sha1.update(block)
        return sha1.hexdigest()
    except Exception:
        return None

def clean_title(title):
    """Nettoie le titre en supprimant ce qui est entre parenthèses ou crochets et en passant en minuscules."""
    if not isinstance(title, str):
        return ''
    # Supprimer ce qui est entre parenthèses ou crochets
    cleaned = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', title)
    # Supprimer les espaces en trop et passer en minuscules
    return cleaned.strip().lower()

def group_by_title_similarity(file_infos, threshold=0.8):
    groups = []
    used = set()
    for i, f1 in enumerate(file_infos):
        if i in used:
            continue
        group = [f1]
        used.add(i)
        title1 = clean_title(f1['title'])
        for j, f2 in enumerate(file_infos):
            if j <= i or j in used:
                continue
            title2 = clean_title(f2['title'])
            if title1 and title2:
                ratio = difflib.SequenceMatcher(None, title1, title2).ratio()
                if ratio >= threshold:
                    group.append(f2)
                    used.add(j)
        if len(group) > 1:
            groups.append(group)
    return groups

FINGERPRINT_TAG = "ACOUSTID_FINGERPRINT"

def get_fingerprint_from_tags(filepath):
    try:
        if filepath.lower().endswith('.mp3'):
            try:
                tags = ID3(filepath)
            except ID3NoHeaderError:
                return None
            for frame in tags.getall('TXXX'):
                if frame.desc == FINGERPRINT_TAG:
                    return frame.text[0]
        elif filepath.lower().endswith('.flac'):
            audio = FLAC(filepath)
            return audio.get(FINGERPRINT_TAG, [None])[0]
        elif filepath.lower().endswith('.ogg'):
            audio = OggVorbis(filepath)
            return audio.get(FINGERPRINT_TAG, [None])[0]
        elif filepath.lower().endswith(('.m4a', '.mp4')):
            audio = MP4(filepath)
            return audio.tags.get(f"----:{FINGERPRINT_TAG}", [None])[0]
    except Exception:
        return None
    return None

def set_fingerprint_in_tags(filepath, fingerprint):
    try:
        written = False
        # S'assurer que fingerprint est une chaîne pour tous les formats sauf MP4/M4A
        fp_str = fingerprint.decode('utf-8') if isinstance(fingerprint, bytes) else fingerprint
        if filepath.lower().endswith('.mp3'):
            try:
                tags = ID3(filepath)
            except ID3NoHeaderError:
                tags = ID3()
            tags.delall('TXXX')  # Pour éviter les doublons
            tags.add(TXXX(encoding=3, desc=FINGERPRINT_TAG, text=fp_str))
            tags.save(filepath)
            written = True
        elif filepath.lower().endswith('.flac'):
            audio = FLAC(filepath)
            audio[FINGERPRINT_TAG] = fp_str
            audio.save()
            written = True
        elif filepath.lower().endswith('.ogg'):
            audio = OggVorbis(filepath)
            audio[FINGERPRINT_TAG] = fp_str
            audio.save()
            written = True
        elif filepath.lower().endswith(('.m4a', '.mp4')):
            audio = MP4(filepath)
            # Pour MP4/M4A, il faut des bytes
            fp_bytes = fingerprint.encode('utf-8') if isinstance(fingerprint, str) else fingerprint
            audio.tags[f"----:{FINGERPRINT_TAG}"] = [fp_bytes]
            audio.save()
            written = True
        # Vérification immédiate après écriture
        if written:
            check = get_fingerprint_from_tags(filepath)
            if check != fp_str:
                print(f"[WARNING] L'empreinte n'a pas été retrouvée dans le tag après écriture pour : {filepath}")
        else:
            print(f"[WARNING] Format non supporté pour l'écriture de l'empreinte : {filepath}")
    except Exception as e:
        print(f"[ERROR] Impossible d'écrire l'empreinte dans le tag pour {filepath} : {e}")

def scan_duplicates(paths_to_scan, date_type, queue, title_similarity_threshold=0.8):
    """
    Scanne les dossiers à la recherche de fichiers musicaux en double en utilisant
    la technologie d'empreinte acoustique pour une précision maximale.

    Ce processus se déroule en trois étapes :
    1.  Collecte de tous les fichiers audio compatibles.
    2.  Génération d'une empreinte acoustique unique pour chaque fichier via fpcalc.
    3.  Groupement des fichiers par empreinte identique pour trouver les doublons.

    La fonction est conçue pour être exécutée dans un thread afin de ne pas bloquer
    l'interface utilisateur et communique sa progression via une file d'attente.

    Args:
        paths_to_scan (list): Liste des chemins de dossier à analyser.
        date_type (str): Le critère de date à utiliser ('modification' ou 'creation').
        queue (queue.Queue): La file d'attente pour envoyer des messages (statut,
                             progression, résultats) à l'interface utilisateur.
    """
    try:
        if not os.path.exists(FPCALC_PATH):
            queue.put(("message", ("error", f"fpcalc.exe non trouvé. Veuillez le placer dans le dossier de l'application.")))
            return

        # Set the path to fpcalc for the acoustid library
        acoustid.FPCOMMAND = FPCALC_PATH

        # Étape 1: Collecte des fichiers
        queue.put(("status", "Étape 1/3: Recherche des fichiers musicaux..."))
        supported_extensions = ('.mp3', '.flac', '.wav', '.m4a', '.ogg')

        all_files_to_process = []
        for path in paths_to_scan:
            for root, _, files in os.walk(path):
                for f in files:
                    if f.lower().endswith(supported_extensions):
                        all_files_to_process.append(os.path.join(root, f))
        
        # Étape 2: Génération des empreintes
        queue.put(("status", f"Étape 2/3: Génération des empreintes pour {len(all_files_to_process)} fichiers..."))
        queue.put(("progress_max", len(all_files_to_process)))

        fingerprint_map = {}
        fp_cache = {}  # {sha1: (duration, fp)}
        all_file_infos = []
        for i, full_path in enumerate(all_files_to_process):
            queue.put(("progress", i + 1))
            try:
                file_hash = file_sha1(full_path)
                # Vérifier si l'empreinte est déjà stockée dans les tags
                fp_from_tag = get_fingerprint_from_tags(full_path)
                duration = None
                if fp_from_tag:
                    fp = fp_from_tag
                    duration = None  # On ne stocke pas la durée dans le tag, donc on la laisse à None
                elif file_hash and file_hash in fp_cache:
                    duration, fp = fp_cache[file_hash]
                else:
                    duration, fp = acoustid.fingerprint_file(full_path)
                    if file_hash:
                        fp_cache[file_hash] = (duration, fp)
                    set_fingerprint_in_tags(full_path, fp)
                # Toujours essayer de lire la durée si elle est absente
                if duration is None:
                    try:
                        audio = File(full_path)
                        if audio and hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                            duration = float(audio.info.length)
                        else:
                            duration = 0
                    except Exception:
                        duration = 0
                stat = os.stat(full_path)
                try:
                    audio = File(full_path, easy=True)
                    title, artist, album, bitrate = (audio.get('title', ['N/A'])[0], 
                                                     audio.get('artist', ['N/A'])[0], 
                                                     audio.get('album', ['N/A'])[0], 
                                                     int(audio.info.bitrate / 1000) if hasattr(audio, 'info') and hasattr(audio.info, 'bitrate') else 0) if audio else ('N/A', 'N/A', 'N/A', 0)
                except Exception:
                    title, artist, album, bitrate = 'N/A', 'N/A', 'N/A', 0
                file_info = {
                    "path": full_path,
                    "date": stat.st_mtime if date_type == "modification" else stat.st_ctime,
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "bitrate": bitrate,
                    "duration": duration
                }
                all_file_infos.append(file_info)
                if fp not in fingerprint_map:
                    fingerprint_map[fp] = []
                fingerprint_map[fp].append(file_info)
            except (acoustid.FingerprintGenerationError, subprocess.CalledProcessError) as e:
                print(f"Could not process file {full_path}: {e}")
                continue
            except FileNotFoundError:
                continue
        # Étape 3: Filtrer les groupes pour ne garder que les doublons acoustiques
        queue.put(("status", "Étape 3/3: Finalisation..."))
        duplicate_groups = [group for group in fingerprint_map.values() if len(group) > 1]
        # Ajout : groupes par similarité de titre
        title_sim_groups = group_by_title_similarity(all_file_infos, threshold=title_similarity_threshold)
        # Fusionner les deux types de groupes (en évitant les doublons)
        all_groups = duplicate_groups[:]
        # On évite d'ajouter deux fois les mêmes fichiers
        already_in_group = set(f["path"] for group in duplicate_groups for f in group)
        for group in title_sim_groups:
            if any(f["path"] in already_in_group for f in group):
                continue
            all_groups.append(group)
            already_in_group.update(f["path"] for f in group)
        if not all_groups:
            queue.put(("message", ("info", "Analyse terminée. Aucun doublon trouvé.")))
        else:
            queue.put(("results", all_groups))
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        queue.put(("message", ("error", f"Erreur lors du scan : {e}\n\n{tb}")))
    finally:
        queue.put(("finished", None))

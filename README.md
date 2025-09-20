# Détecteur de Doublons de Musique

![Duplicate Music Finder Screenshot](https://raw.githubusercontent.com/Warry/DuplicateMusicFinder/main/docs/screenshot.png) <!-- Placeholder for a real screenshot -->

**Détecteur de Doublons de Musique** est une application de bureau pour Windows, macOS et Linux conçue pour vous aider à trouver, gérer et nettoyer les fichiers musicaux en double sur votre ordinateur. Grâce à une technologie d'empreinte acoustique, elle identifie les doublons avec une précision maximale, même si les noms de fichiers ou les métadonnées sont différents.

---

## Table des matières

- [Fonctionnalités principales](#fonctionnalités-principales)
- [Installation](#installation)
- [Comment utiliser](#comment-utiliser)
- [Contribuer](#contribuer)
- [Licence](#licence)

---

## Fonctionnalités principales

- **Détection par Empreinte Acoustique** : Identifie les fichiers audio identiques en analysant leur contenu sonore, garantissant une précision maximale indépendamment des métadonnées ou des noms de fichiers.
- **Analyse multi-dossiers** : Sélectionnez un ou plusieurs dossiers à analyser, l'application explorera tous les sous-dossiers.
- **Affichage des Métadonnées** : Affiche les informations essentielles (Titre, Artiste, Album, Bitrate) pour vous aider à décider quel fichier conserver.
- **Prévisualisation Audio** : Double-cliquez sur n'importe quel fichier dans la liste pour l'écouter directement dans l'application et confirmer son contenu.
- **Mise à la Corbeille Sécurisée** : Les fichiers ne sont pas supprimés définitivement. Ils sont envoyés à la corbeille de votre système, vous permettant de les récupérer en cas d'erreur.
- **Sauvegarde de la Configuration** : L'application mémorise vos dossiers et vos préférences entre les sessions pour un accès plus rapide.
- **Filtrage Dynamique** : Un champ de recherche vous permet de filtrer instantanément les résultats pour trouver facilement des fichiers spécifiques.
- **Interface Réactive** : L'analyse s'exécute en arrière-plan, vous permettant de continuer à utiliser l'application sans aucun gel.
- **Gestion Flexible des Résultats** :
    - Cochez/décochez manuellement les fichiers à supprimer.
    - Sélectionnez ou désélectionnez un groupe entier de doublons en un clic.
    - Masquez les éléments pour nettoyer la vue.

---

## Installation

Pour utiliser l'application, vous devez avoir Python 3 (version 3.9 à 3.12 recommandée) installé sur votre système.

1.  **Dépendance Externe : `fpcalc`**

    Cette application nécessite l'outil `fpcalc` pour générer les empreintes acoustiques.
    -   Téléchargez l'exécutable `fpcalc` depuis le [site officiel de Chromaprint](https://acoustid.org/chromaprint).
    -   Décompressez le fichier si nécessaire.
    -   **Crucial :** Placez le fichier `fpcalc.exe` (ou `fpcalc` sur macOS/Linux) **dans le même dossier** que les scripts `ui.py` et `scanner.py` de l'application.

2.  **Clonez le dépôt**
    ```bash
    git clone https://github.com/VOTRE_NOM/DuplicateMusicFinder.git
    cd DuplicateMusicFinder
    ```

3.  **Créez un environnement virtuel** (recommandé)
    ```bash
    python -m venv .venv
    ```
    Sous Windows, activez-le avec :
    ```bash
    .venv\Scripts\activate
    ```

4.  **Installez les dépendances Python**
    Le projet utilise un fichier `requirements.txt` pour lister toutes ses dépendances.
    ```bash
    pip install -r requirements.txt
    ```

---

## Comment utiliser

Une fois les dépendances installées et `fpcalc` en place, lancez l'application en exécutant le fichier `main.py` :

```bash
python main.py
```

1.  Cliquez sur **"Ajouter..."** ou **"Ajouter plusieurs..."** pour sélectionner les dossiers contenant votre musique.
2.  Ajustez les options de tri (garder le plus récent/ancien) selon vos besoins.
3.  Cliquez sur **"Scanner les Doublons"**.
4.  Une fois l'analyse terminée, gérez les résultats dans le tableau. Double-cliquez sur une ligne pour écouter le fichier.
5.  Cliquez sur le bouton **"Mettre à la corbeille"** pour nettoyer les fichiers sélectionnés.

---

## Analyse avancée par similarité des titres

- L’application permet de détecter les doublons même si les titres des fichiers ne sont pas strictement identiques.
- Un curseur (slider) dans l’interface permet de choisir le pourcentage minimal de ressemblance des titres (de 50 % à 100 %).
- Plus le seuil est bas, plus la détection sera tolérante : les titres légèrement différents seront considérés comme des doublons.
- Plus le seuil est élevé, plus seuls les titres très proches seront regroupés.
- Cette analyse s’ajoute à la détection par empreinte acoustique pour maximiser la détection des doublons réels.

---

## Dépendances principales

- **Python 3.9 à 3.12** (Python 3.13 n’est pas supporté à cause de la suppression du module `aifc` requis par certaines bibliothèques audio)
- **fpcalc** (Chromaprint)
- **pygame** (lecture audio)
- **mutagen** (lecture des métadonnées)
- **pyacoustid** (empreinte acoustique)
- **send2trash** (mise à la corbeille multiplateforme)

Toutes les dépendances Python sont listées dans `requirements.txt` et s’installent automatiquement.

---

## Conseils et limitations

- **Compatibilité Python** : Utilisez impérativement Python 3.9, 3.10, 3.11 ou 3.12.  
  Python 3.13 n’est pas supporté car certaines bibliothèques audio (comme audioread, utilisée par pyacoustid) nécessitent le module standard `aifc` qui a été supprimé dans Python 3.13.
- **Formats supportés** : mp3, flac, wav, m4a, ogg (AIFF non supporté sous Python 3.13).
- **Sécurité** : Les fichiers supprimés sont envoyés à la corbeille, pas effacés définitivement.
- **Performance** : L’analyse peut être longue sur de très grandes bibliothèques musicales, mais l’interface reste réactive.

---

## Contribuer

Les contributions sont les bienvenues ! Si vous souhaitez améliorer l'application, veuillez consulter le fichier [CONTRIBUTING.md](CONTRIBUTING.md) pour connaître les lignes directrices.

---

## Licence

Ce projet est distribué sous la licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## Support

Pour toute question, suggestion ou bug, ouvre une issue sur le dépôt GitHub ou contacte le mainteneur.

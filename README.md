# Duplicate Music Finder

![Duplicate Music Finder Screenshot](https://raw.githubusercontent.com/Warry/DuplicateMusicFinder/main/docs/screenshot.png) <!-- Placeholder for a real screenshot -->

**Duplicate Music Finder** est une application de bureau pour Windows conçue pour vous aider à trouver, gérer et supprimer les fichiers musicaux en double sur votre ordinateur. Simple, rapide et efficace, elle vous redonne le contrôle sur votre bibliothèque musicale.

---

## Table des matières

- [Fonctionnalités principales](#fonctionnalités-principales)
- [Installation](#installation)
- [Comment utiliser](#comment-utiliser)
- [Contribuer](#contribuer)
- [Licence](#licence)

---

## Fonctionnalités principales

- **Analyse multi-dossiers** : Sélectionnez un ou plusieurs dossiers à analyser, l'application explorera tous les sous-dossiers.
- **Seuil de similarité ajustable** : Définissez avec précision (de 0% à 100%) à quel point les noms de fichiers doivent être similaires pour être considérés comme des doublons.
- **Critères de tri avancés** : Triez les doublons par date de modification ou de création pour décider facilement lequel garder.
- **Présélection intelligente** : Configurez l'application pour qu'elle présélectionne automatiquement les fichiers les plus anciens ou les plus récents pour une suppression rapide.
- **Interface réactive** : L'analyse s'exécute en arrière-plan, vous permettant de continuer à utiliser l'application sans aucun gel.
- **Gestion flexible des résultats** :
    - Cochez/décochez manuellement les fichiers à supprimer.
    - Sélectionnez ou désélectionnez un groupe entier de doublons en un clic.
    - Masquez les "faux positifs" pour nettoyer la vue.
- **Suppression sécurisée** : Une boîte de dialogue de confirmation vous protège contre toute suppression accidentelle.

---

## Installation

Pour utiliser l'application, vous devez avoir Python 3 installé sur votre système.

1.  **Clonez le dépôt**
    ```bash
    git clone https://github.com/VOTRE_NOM/DuplicateMusicFinder.git
    cd DuplicateMusicFinder
    ```

2.  **Créez un environnement virtuel** (recommandé)
    ```bash
    python -m venv .venv
    ```
    Sous Windows, activez-le avec :
    ```bash
    .venv\Scripts\activate
    ```

3.  **Installez les dépendances**
    Le projet utilise la bibliothèque `rapidfuzz` pour une comparaison de chaînes performante. Installez-la via le fichier `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

---

## Comment utiliser

Une fois les dépendances installées, lancez l'application en exécutant le fichier `main.py` :

```bash
python main.py
```

1.  Cliquez sur **"Ajouter..."** ou **"Ajouter plusieurs..."** pour sélectionner les dossiers contenant votre musique.
2.  Ajustez les paramètres d'analyse (seuil de similarité, critère de date, etc.) selon vos besoins.
3.  Cliquez sur **"Scanner les Doublons"**.
4.  Une fois l'analyse terminée, gérez les résultats dans le tableau.
5.  Cliquez sur le bouton **"Supprimer les fichiers sélectionnés"** pour finaliser l'opération.

---

## Contribuer

Les contributions sont les bienvenues ! Si vous souhaitez améliorer l'application, veuillez consulter le fichier [CONTRIBUTING.md](CONTRIBUTING.md) pour connaître les lignes directrices.

---

## Licence

Ce projet est distribué sous la licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.


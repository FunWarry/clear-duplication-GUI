"""Point d'entrée principal de l'application Détecteur de Doublons de Musique."""

from ui import DuplicateMusicFinder

if __name__ == "__main__":
    # Crée une instance de l'application et lance la boucle principale.
    app = DuplicateMusicFinder()
    app.mainloop()

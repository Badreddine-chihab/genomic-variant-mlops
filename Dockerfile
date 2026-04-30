# Utiliser une image Python officielle légère
FROM python:3.11-slim

# Empêcher Python de créer des fichiers .pyc et forcer l'affichage des logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Définir le dossier de travail dans le conteneur
WORKDIR /app

# Installer les dépendances système requises (pour compiler certains packages ML)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copier le fichier des dépendances et les installer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code de ton projet dans le conteneur
COPY . .

# Exposer le port par défaut de Streamlit
EXPOSE 8501

# Commande par défaut pour lancer l'application
CMD ["python", "-m", "streamlit", "run", "src/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
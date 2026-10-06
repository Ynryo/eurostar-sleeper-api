FROM python:3.12-slim

WORKDIR /app

# Empêche la génération de fichiers .pyc et force l'envoi immédiat des logs au terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DOCKER=1
ENV HOST=0.0.0.0
ENV PORT=8080
ENV TZ=Europe/Paris

# Installation des dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source et des fichiers statiques
COPY . .

# Exposition du port web
EXPOSE 8080

# Commande de démarrage
CMD ["python", "gtfs.py"]

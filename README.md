# API Chatbot Juridique

API REST construite avec FastAPI et MongoDB pour l'authentification et la gestion des utilisateurs.

## Prérequis

- Docker et Docker Compose
- Python 3.11+

## Installation et démarrage

### Démarrage rapide avec Docker

```bash
# Cloner le projet et se placer dans le dossier api
cd /chemin/vers/le/projet/api

# Lancer l'application avec Docker Compose
docker-compose up --build

# L'API sera accessible sur http://localhost:8000
```

### Configuration

Les variables d'environnement principales :

```
MONGODB_URL=mongodb://mongo:27017
DATABASE_NAME=chatbot_db
SECRET_KEY=your-secret-key-here
```

## Fonctionnalités

### Authentification

L'API propose un système d'authentification complet basé sur JWT :

- **Inscription** : Création de nouveaux comptes utilisateur
- **Connexion** : Authentification avec email/mot de passe
- **Tokens JWT** : Gestion des sessions sécurisées
- **Protection des routes** : Middleware d'authentification

### Endpoints disponibles

#### Routes publiques
- `GET /` - Page d'accueil de l'API
- `POST /auth/register` - Inscription utilisateur
- `POST /auth/login` - Connexion utilisateur

#### Routes protégées (nécessitent un token JWT)
- `GET /auth/me` - Informations du profil utilisateur
- `GET /protected` - Route de test pour l'authentification

## Utilisation

### 1. Inscription d'un utilisateur

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "motdepasse123",
    "full_name": "Nom Utilisateur"
  }'
```

### 2. Connexion

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "motdepasse123"
  }'
```

La réponse contient un `access_token` à utiliser pour les requêtes authentifiées.

### 3. Accès aux routes protégées

```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Architecture

### Structure du projet

```
app/
├── main.py                 # Application FastAPI principale
├── core/
│   ├── config.py          # Configuration et variables d'environnement
│   ├── database.py        # Gestionnaire de connexion MongoDB
│   └── security.py        # Utilitaires JWT et cryptographie
├── models/
│   └── user.py           # Modèles Pydantic pour les utilisateurs
├── repositories/
│   └── user_repository.py # Couche d'accès aux données MongoDB
├── services/
│   └── auth_service.py    # Logique métier d'authentification
└── routes/
    └── auth.py           # Endpoints d'authentification
```

### Technologies utilisées

- **FastAPI** : Framework web moderne et performant
- **MongoDB** : Base de données NoSQL avec Motor (driver async)
- **JWT** : Gestion des tokens d'authentification
- **bcrypt** : Hachage sécurisé des mots de passe
- **Pydantic** : Validation et sérialisation des données

## Tests

### Tests automatisés

```bash
# Lancer les tests
python test_api.py
```

### Tests manuels

```bash
# Tester tous les endpoints
make test-api

# Ou utiliser curl directement
curl http://localhost:8000/
```

## Développement

### Commandes utiles

```bash
# Reconstruire les containers
docker-compose up --build

# Voir les logs
docker-compose logs -f

# Arrêter l'application
docker-compose down

# Nettoyer les volumes
docker-compose down -v
```

### Base de données

MongoDB est configuré avec :
- Base de données : `chatbot_db`
- Collection : `users`
- Index unique sur le champ `email`

## Sécurité

- Mots de passe hachés avec bcrypt
- Tokens JWT avec expiration configurable
- Validation stricte des données d'entrée
- Protection CORS configurée
- Gestion des erreurs sécurisée

## Documentation

Une fois l'API lancée, la documentation interactive est disponible sur :
- Swagger UI : http://localhost:8000/docs
- ReDoc : http://localhost:8000/redoc
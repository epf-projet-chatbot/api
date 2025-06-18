# ================================
# 🤖 CHATBOT API MAKEFILE
# ================================

.PHONY: help build up down dev prod logs clean test lint format

# ================================
# 📖 HELP
# ================================
help: ## Afficher l'aide
	@echo "🤖 Chatbot API - Commandes disponibles:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ================================
# 🐳 DOCKER COMMANDS
# ================================
build: ## Construire les images Docker
	@echo "🏗️  Building Docker images..."
	docker-compose build --no-cache

up: ## Démarrer tous les services
	@echo "🚀 Starting all services..."
	docker-compose up -d

dev: ## Démarrer en mode développement avec hot reload
	@echo "🛠️  Starting development mode..."
	docker-compose up

prod: ## Démarrer avec Mongo Express (interface admin)
	@echo "🚀 Starting with admin tools..."
	docker-compose --profile admin up -d

down: ## Arrêter tous les services
	@echo "🛑 Stopping all services..."
	docker-compose down

restart: down up ## Redémarrer tous les services

# ================================
# 📊 MONITORING
# ================================
logs: ## Afficher les logs
	docker-compose logs -f

logs-api: ## Afficher les logs de l'API uniquement
	docker-compose logs -f api

logs-mongo: ## Afficher les logs de MongoDB
	docker-compose logs -f mongo

status: ## Afficher le statut des services
	@echo "📊 Services status:"
	@docker-compose ps

health: ## Vérifier la santé de l'API
	@echo "🏥 Checking API health..."
	@curl -f http://localhost:8000/health || echo "❌ API not healthy"

# ================================
# 🧹 MAINTENANCE
# ================================
clean: ## Nettoyer les containers et volumes
	@echo "🧹 Cleaning up..."
	docker-compose down -v --remove-orphans
	docker system prune -f

clean-all: ## Nettoyer complètement (ATTENTION: supprime les données)
	@echo "⚠️  WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " -n 1 -r && echo && [[ $$REPLY =~ ^[Yy]$$ ]] || exit 1
	docker-compose down -v --remove-orphans
	docker system prune -af
	docker volume prune -f

# ================================
# 🧪 TESTING & DEVELOPMENT
# ================================
test: up ## Démarrer et tester l'API
	@echo "🧪 Testing API..."
	@sleep 15
	@curl -f http://localhost:8000/health && echo "✅ API is healthy"

install: ## Installer les dépendances Python localement
	@echo "📦 Installing Python dependencies..."
	pip install -r requirements.txt

run-local: ## Exécuter l'API en local (sans Docker)
	@echo "🐍 Running API locally..."
	cd app && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# ================================
# 📁 FILE OPERATIONS
# ================================
backup-db: ## Sauvegarder la base de données
	@echo "💾 Backing up database..."
	docker exec chatbot-mongo mongodump --db chatbot_db --out /tmp/backup
	docker cp chatbot-mongo:/tmp/backup ./backup-$(shell date +%Y%m%d-%H%M%S)

# ================================
# 🔧 UTILITIES
# ================================
shell-api: ## Ouvrir un shell dans le container API
	docker-compose exec api bash

shell-mongo: ## Ouvrir un shell MongoDB
	docker-compose exec mongo mongosh chatbot_db

env: ## Créer le fichier .env depuis .env.example
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env file..."; \
		cp .env.example .env; \
		echo "✅ .env created! Please edit it with your values."; \
	else \
		echo "⚠️  .env file already exists"; \
	fi
	@echo "Lancement des tests..."
	python test_api.py
	@echo "Arrêt des services..."
	$(MAKE) down

# Voir les logs
logs:
	docker-compose logs -f

# Nettoyer tout (containers, images, volumes)
clean:
	docker-compose down -v
	docker-compose rm -f
	docker system prune -f

# Démarrer en mode développement (avec logs)
dev:
	docker-compose up

# Redémarrer l'API seulement
restart-api:
	docker-compose restart web

# Accéder au shell du container API
shell:
	docker-compose exec web bash

# Vérifier la santé des services
health:
	@echo "🔍 Vérification de la santé des services..."
	@curl -s http://localhost:8000/health | jq . || echo "API non disponible"
	@docker-compose ps

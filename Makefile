# Makefile pour l'API Chatbot

.PHONY: build up down test logs clean

# Construire les images Docker
build:
	docker-compose build

# Démarrer les services
up:
	docker-compose up -d

# Arrêter les services
down:
	docker-compose down

# Démarrer et tester l'API
test: up
	@echo "⏳ Attente du démarrage des services..."
	@sleep 10
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

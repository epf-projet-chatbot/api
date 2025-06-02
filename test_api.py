#!/usr/bin/env python3
"""
Script de test pour l'API Chatbot en Docker
"""
import requests
import json
import time
import sys


def wait_for_api(url, max_retries=30):
    """Attendre que l'API soit disponible"""
    for i in range(max_retries):
        try:
            response = requests.get(f"{url}/")
            if response.status_code == 200:
                print("API est disponible")
                return True
        except requests.ConnectionError:
            pass
        
        print(f"Attente de l'API... ({i+1}/{max_retries})")
        time.sleep(2)
    
    return False


def test_api_endpoints():
    """Tester les endpoints de l'API"""
    base_url = "http://localhost:8000"
    
    # Attendre que l'API soit disponible
    if not wait_for_api(base_url):
        print("L'API n'est pas disponible")
        return False
    
    try:
        # Test endpoint root
        print("\nTest endpoint root...")
        response = requests.get(f"{base_url}/")
        assert response.status_code == 200
        print("Endpoint root OK")
        
        # Test registration
        print("\n🧪 Test registration...")
        user_data = {
            "email": "test@example.com",
            "password": "testpassword123",
            "role": "user"
        }
        response = requests.post(f"{base_url}/auth/register", json=user_data)
        if response.status_code == 201:
            print("Utilisateur créé avec succès")
        elif response.status_code == 400 and "already registered" in response.text:
            print("Utilisateur existe déjà")
        else:
            print(f"Erreur lors de l'enregistrement: {response.status_code} - {response.text}")
            return False
        
        # Test login
        print("\nTest login...")
        login_data = {
            "username": "test@example.com",  # OAuth2PasswordRequestForm utilise "username"
            "password": "testpassword123"
        }
        response = requests.post(f"{base_url}/auth/login", data=login_data)
        assert response.status_code == 200
        token_data = response.json()
        access_token = token_data["access_token"]
        print("Login OK")
        
        # Test endpoint protégé
        print("\nTest endpoint protégé...")
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{base_url}/auth/me", headers=headers)
        assert response.status_code == 200
        user_info = response.json()
        assert user_info["email"] == "test@example.com"
        print("Endpoint protégé OK")
        
        print("\nTous les tests sont passés avec succès!")
        return True
        
    except Exception as e:
        print(f"Erreur lors des tests: {e}")
        return False


if __name__ == "__main__":
    success = test_api_endpoints()
    sys.exit(0 if success else 1)

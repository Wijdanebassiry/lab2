
# API Gateway - Lab 5

## 1. Présentation

L'API Gateway est le point d'entrée unique de l'application
microservices.

Il reçoit les requêtes du frontend et les transmet au microservice
correspondant.

Le Gateway est développé avec Python, FastAPI et HTTPX.

- Port : 8080
- Dossier : `msoa-backend/api-gateway`
- Mode par défaut : `dynamic`

## 2. Installation

Se placer dans le dossier du Gateway :

```bash
cd msoa-backend/api-gateway
```

Créer un environnement virtuel :

```bash
python -m venv .venv
```

Activer l'environnement sous Windows PowerShell :

```powershell
.\.venv\Scripts\Activate.ps1
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

## 3. Lancement

Démarrer le Gateway :

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Vérifier son état :

```text
http://127.0.0.1:8080/health
```

## 4. Modes de fonctionnement

### Mode static

Dans ce mode, les adresses des microservices sont récupérées
depuis `app/config.py`.

Les adresses peuvent être personnalisées avec des variables
d'environnement.

### Mode dynamic

Dans ce mode, les adresses sont récupérées depuis le registre
de services en mémoire.

Les services doivent être enregistrés auprès du Gateway.

Le mode par défaut est `dynamic`.

Pour sélectionner le mode :

PowerShell :

```powershell
$env:GATEWAY_MODE = "static"
```

ou :

```powershell
$env:GATEWAY_MODE = "dynamic"
```

## 5. Routes vers les microservices

| Chemin | Microservice | Adresse par défaut |
|---|---|---|
| `/api/auth` | auth-service | `http://127.0.0.1:8081` |
| `/products` | catalog-service | `http://127.0.0.1:8082` |
| `/v2/products` | catalog-service | `http://127.0.0.1:8082` |
| `/api/inventory` | inventory-service | `http://127.0.0.1:8083` |
| `/api/orders` | orders-service | `http://127.0.0.1:8084` |
| `/api/payments` | payments-service | `http://127.0.0.1:8085` |
| `/api/shipments` | shipping-service | `http://127.0.0.1:8086` |

## 6. API du registre

### Enregistrer un service

`POST /registry/register`

Exemple de corps JSON :

```json
{
  "name": "catalog-service",
  "address": "http://127.0.0.1:8082"
}
```

Réponse attendue :

```json
{
  "message": "Service registered successfully",
  "name": "catalog-service",
  "address": "http://127.0.0.1:8082"
}
```

Un nouvel enregistrement du même nom remplace l'ancienne adresse.

### Consulter les services enregistrés

`GET /registry/services`

Exemple de réponse :

```json
{
  "catalog-service": "http://127.0.0.1:8082"
}
```

## 7. Script d'enregistrement

Le script `scripts/register.py` permet d'enregistrer les microservices.

Enregistrer les six services :

```bash
python scripts/register.py
```

Enregistrer un seul service :

```bash
python scripts/register.py catalog-service http://127.0.0.1:8082
```

Modifier l'adresse du Gateway :

PowerShell :

```powershell
$env:GATEWAY_URL = "http://127.0.0.1:8080"
```

Le script utilise uniquement la bibliothèque standard Python `urllib`.

## 8. Codes d'erreur

| Code HTTP | Signification |
|---|---|
| 400 | Requête d'enregistrement invalide |
| 404 | Aucune route correspondante |
| 502 | Microservice inaccessible |
| 503 | Microservice non enregistré |
| 504 | Délai d'attente dépassé |

## 9. Vérifications avec PowerShell

Vérifier l'état du Gateway :

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

Consulter le registre :

```powershell
Invoke-RestMethod http://127.0.0.1:8080/registry/services
```

Enregistrer Catalog :

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/registry/register `
  -ContentType "application/json" `
  -Body '{"name":"catalog-service","address":"http://127.0.0.1:8082"}'
```

Tester la route Catalog :

```powershell
Invoke-RestMethod http://127.0.0.1:8080/products
```

## 10. Scénario Service Discovery

Le scénario permet de vérifier la découverte dynamique des services :

1. Sans enregistrement de Catalog, `/products` retourne HTTP 503.
2. Enregistrer Catalog à l'adresse `http://127.0.0.1:8082`.
3. Vérifier sa présence dans `/registry/services`.
4. Vérifier que `/products` fonctionne.
5. Relancer Catalog sur le port 9192.
6. Sans mettre à jour le registre, `/products` retourne HTTP 502.
7. Enregistrer la nouvelle adresse `http://127.0.0.1:9192`.
8. Vérifier que `/products` fonctionne de nouveau.

Le Gateway n'est pas redémarré pendant cette séquence.
Le registre est conservé en mémoire pendant toute son exécution.

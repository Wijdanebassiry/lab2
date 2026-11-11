# Shipping Service

## 1. Présentation

Shipping est un microservice du projet MSOA (Microservices Oriented Architecture).

Il permet de gérer les livraisons associées aux commandes.

**Technologies utilisées :**
- Java 21
- Spring Boot 3.2.5
- Spring Data JPA
- Hibernate
- MySQL
- Maven

## 2. Configuration

Le service utilise le port **8086**.

La base de données utilisée est `shipping_db`.

Les paramètres sont configurables avec les variables d'environnement suivantes :

| Variable | Valeur par défaut |
|---|---|
| DB_URL | jdbc:mysql://localhost:3306/shipping_db |
| DB_USERNAME | root |
| DB_PASSWORD | vide |
| ORDERS_URL | http://localhost:8084 |
| AUTH_URL | http://localhost:8081 |

## 3. Fonctionnalités

- Consulter toutes les livraisons.
- Consulter une livraison par identifiant de commande.
- Créer une livraison pour une commande payée.
- Mettre à jour le statut d'une livraison.
- Vérifier les tokens JWT auprès du service Auth.
- Vérifier auprès du service Orders que la commande existe et possède le statut PAID.

Shipping ne modifie pas directement le statut de la commande dans Orders.

## 4. Endpoints REST

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/api/shipments` | Liste des livraisons |
| GET | `/api/shipments/order/{orderId}` | Livraison d'une commande |
| POST | `/api/shipments` | Créer une livraison |
| PATCH | `/api/shipments/{id}/status` | Modifier le statut |

Les requêtes protégées nécessitent un token :

`Authorization: Bearer <token>`

### Exemple de création

**POST** `/api/shipments`

```json
{
  "orderId": "order-123",
  "address": {
    "name": "Demo Customer",
    "address": "123 Main Street",
    "city": "Casablanca"
  }
}
```

La commande doit être payée (`PAID`) pour permettre la création de la livraison.

## 5. Statuts de livraison

Les statuts disponibles sont :

- PREPARING
- SHIPPED
- IN_TRANSIT
- DELIVERED
- CANCELLED

Transitions actuellement autorisées :

`PREPARING → SHIPPED → IN_TRANSIT → DELIVERED`

## 6. Lancement local

Prérequis :
- Java 21
- MySQL
- Maven

Créer la base de données `shipping_db`, démarrer MySQL, puis exécuter :

```bash
./mvnw spring-boot:run
```

Sous Windows :

```powershell
.\mvnw.cmd spring-boot:run
```

Le service sera accessible sur :

`http://localhost:8086`

## 7. Tests

Exécuter les tests avec :

```powershell
.\mvnw.cmd clean test
```

La configuration de test utilise H2 en mémoire via le profil `test`.

Les tests unitaires vérifient notamment :
- La création d'une livraison.
- La gestion des doublons.
- Le refus d'une commande non payée.
- Les transitions de statut.
- Les erreurs liées aux livraisons inexistantes.

## 9. Dépendances entre microservices

- **Auth (8081)** : validation des tokens JWT via `/api/auth/me`.
- **Orders (8084)** : vérification de l'existence et du paiement de la commande.

Les tests d'intégration avec les services Auth et Orders doivent être réalisés lorsque ces services sont disponibles.

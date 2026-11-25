# Analytics Service (Lab 4, cas 3)

Consomme les evenements Kafka des autres services, les conserve, calcule des
statistiques et peut **rejouer** tout l'historique. Port **8087**.

## Role dans l'architecture
- Producteurs : Orders (`orders.events`), Payments (`payments.events`), Shipping (`shipments.events`).
- Consommateur : Analytics, groupe `analytics`, `auto_offset_reset=earliest`.
- Contrat : `contracts/event.envelope.v1.schema.json` (chaque message est valide ; un message invalide est ignore et compte).
- Idempotence : cle unique `eventId` (un doublon n'est pas compte deux fois).
- L'offset est valide **apres** l'enregistrement en base. Si Kafka tombe, le service reste en vie et se reconnecte.

## Lancer
```
cd msoa-backend/analytics-service
python -m venv venv ; .\venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn app.main:app --port 8087
```
Variables : `KAFKA_BOOTSTRAP` (localhost:9092), `KAFKA_TOPICS`, `ANALYTICS_GROUP` (analytics),
`ANALYTICS_DB` (data/analytics.db), `KAFKA_ENABLED` (true).

## API
| Methode | Route | Role |
|---|---|---|
| GET | `/api/analytics/summary` | commandes, paiements, chiffre d'affaires, livraisons par statut |
| GET | `/api/analytics/events?eventType=&orderId=&limit=` | evenements stockes (les plus recents d'abord) |
| POST | `/api/analytics/replay` | vide la base et relit les topics depuis le debut (202) |
| GET | `/health` | etat du service et de la connexion Kafka |

Chiffre d'affaires = somme des `PaymentCompleted.amount` (MAD). Commandes actives = creees - annulees.

## Tester
```
python -m pytest -q          # 10 tests, sans broker
python scripts/send_sample_events.py     # envoie 3 evenements dans Kafka
curl http://localhost:8087/api/analytics/summary
```

## Scenario de preuve (captures)
1. Kafka demarre, topics crees (`infra/README.md`). Payments, Orders, Shipping produisent des evenements.
2. **Arreter Analytics**, produire d'autres evenements, **redemarrer** : les evenements manques sont rattrapes (offsets du groupe).
3. `POST /api/analytics/replay` : le resume est recalcule a l'identique depuis le debut des topics.
4. Demarrer un **nouveau** service avec `ANALYTICS_GROUP=analytics-2` : il relit tout l'historique, preuve que Kafka garde les evenements.
5. Envoyer un doublon et un message invalide (`kafka-console-producer`) : le compteur `consumer` de `/health` montre `duplicates` et `rejected`.

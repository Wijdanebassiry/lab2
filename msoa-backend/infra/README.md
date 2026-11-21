# Infrastructure du Lab 4 : RabbitMQ et Kafka

Prérequis : Docker Desktop. Les six services tournent en local, seuls les brokers sont dans Docker.

## Démarrer et arrêter
```
cd infra
docker compose up -d
docker compose ps
```
Arrêter **en gardant** les messages et les événements : `docker compose stop` (puis `docker compose start`).
`docker compose down` supprime les conteneurs, donc les événements Kafka.

## RabbitMQ
- Interface web : http://localhost:15672 (identifiants `guest` / `guest`), onglet « Queues ».
- Les services se connectent à `amqp://guest:guest@localhost:5672/`.
- L'échange, les files et leurs liaisons sont déclarés par les services au démarrage (voir CONTRACTS.md, section Lab 4).

## Kafka : créer les trois topics (rétention illimitée pour pouvoir rejouer)
```
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic orders.events --partitions 3 --replication-factor 1 --config retention.ms=-1
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic payments.events --partitions 3 --replication-factor 1 --config retention.ms=-1
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic shipments.events --partitions 3 --replication-factor 1 --config retention.ms=-1
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```
Les services se connectent à `localhost:9092`.

## Vérifier avec la console
Lire un topic depuis le début :
```
docker exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic payments.events --from-beginning --property print.key=true
```
Envoyer un message de test (clé:valeur) :
```
docker exec -it kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic payments.events --property parse.key=true --property key.separator=:
```

## Rejouer l'historique (Analytics arrêté)
```
docker exec kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group analytics --reset-offsets --to-earliest --all-topics --execute
```
Au redémarrage, Analytics relit tout depuis le début.

Remarque : ce `docker-compose.yml` est standard, mais il n'a pas été exécuté dans l'environnement de préparation : testez-le une fois sur une machine avec Docker avant de commencer.
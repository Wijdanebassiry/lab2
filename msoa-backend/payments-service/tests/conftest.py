import os

# Les tests ne doivent jamais dependre d'un vrai Kafka : le producteur global est
# desactive avant l'import de l'application (les tests Kafka creent leur propre
# producteur ou un faux).
os.environ["KAFKA_ENABLED"] = "false"

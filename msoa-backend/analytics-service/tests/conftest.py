import os
os.environ["ANALYTICS_DB"] = ":memory:"      # avant l'import de app.main
os.environ["KAFKA_ENABLED"] = "false"        # les tests n'ont pas besoin de broker

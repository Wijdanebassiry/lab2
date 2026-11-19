from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Create the demo user used by the frontend"

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            email="demo@msoa.shop",
            defaults={
                "id": "user-1",
                "name": "Demo Customer",
                "role": "CUSTOMER",
            },
        )
        user.set_password("demo123")
        user.save()
        state = "created" if created else "updated"
        self.stdout.write(f"Demo user {state}: {user.email} ({user.id})")
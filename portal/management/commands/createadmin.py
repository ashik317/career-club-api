from getpass import getpass

from django.core.management.base import BaseCommand, CommandError

from portal.models import Admin


class Command(BaseCommand):
    help = "Create an admin account, or reset the password of an existing one."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--name", default="admin")
        parser.add_argument("--password", help="Asked for interactively when omitted.")

    def handle(self, *args, email, name, password, **options):
        password = password or getpass("Password: ")
        if len(password) < 8:
            raise CommandError("The password must be at least 8 characters.")
        admin, created = Admin.objects.get_or_create(
            email=email.lower(), defaults={"name": name})
        admin.set_password(password)
        admin.save()
        self.stdout.write(self.style.SUCCESS(
            f"Admin {admin.email} {'created' if created else 'password reset'}."))

from django.core.management import BaseCommand, CommandParser
from django.db import IntegrityError
from houses.models import LiveHouseWebsite


class Command(BaseCommand):
    help = "Add a new live house website"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("url", type=str, help="URL of the live house website")

    def handle(self, *args, **options) -> None:  # noqa: C901, PLR0912, PLR0915, PLR0911
        url: str = options["url"]

        try:
            website = LiveHouseWebsite.objects.create(url=url)
            self.stdout.write(self.style.SUCCESS(f"Successfully created LiveHouseWebsite with URL: {website.url}"))
        except IntegrityError:
            self.stderr.write(self.style.ERROR(f"Website with URL '{url}' already exists"))

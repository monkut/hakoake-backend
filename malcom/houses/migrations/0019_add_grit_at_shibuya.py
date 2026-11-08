import datetime

from django.db import migrations


def add_grit_at_shibuya(apps, schema_editor):
    LiveHouseWebsite = apps.get_model("houses", "LiveHouseWebsite")
    LiveHouse = apps.get_model("houses", "LiveHouse")

    website = LiveHouseWebsite.objects.get(id=22)
    website.crawler_class = "GritAtShibuyaCrawler"
    website.schedule_url = "https://grit-live.jp/events"
    website.save(update_fields=["crawler_class", "schedule_url"])

    LiveHouse.objects.create(
        website=website,
        name="GRIT at Shibuya",
        name_kana="グリット アット シブヤ",
        name_romaji="GRIT at Shibuya",
        address="東京都渋谷区道玄坂2丁目23−12 フォンティスビル B1F",
        phone_number="03-6416-1840",
        capacity=0,
        opened_date=datetime.date(2000, 1, 1),
    )


def remove_grit_at_shibuya(apps, schema_editor):
    LiveHouseWebsite = apps.get_model("houses", "LiveHouseWebsite")
    LiveHouse = apps.get_model("houses", "LiveHouse")

    LiveHouse.objects.filter(name="GRIT at Shibuya").delete()

    LiveHouseWebsite.objects.filter(id=22).update(
        crawler_class="",
        schedule_url="https://grit-live.jp/schedule/",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("houses", "0018_merge_20261023_1240"),
    ]

    operations = [
        migrations.RunPython(add_grit_at_shibuya, remove_grit_at_shibuya),
    ]

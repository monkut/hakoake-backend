from django.db import migrations


def fix_crawler_classes(apps, schema_editor):
    LiveHouseWebsite = apps.get_model("houses", "LiveHouseWebsite")
    LiveHouseWebsite.objects.filter(url="https://club-malcolm.com/").update(crawler_class="MalcolmCrawler")
    LiveHouseWebsite.objects.filter(url="https://shinjuku-face.com/").update(crawler_class="ShinjukuFaceCrawler")
    LiveHouseWebsite.objects.filter(url="https://www.fever-popo.com/").update(crawler_class="FeverPopoCrawler")


def revert_crawler_classes(apps, schema_editor):
    LiveHouseWebsite = apps.get_model("houses", "LiveHouseWebsite")
    LiveHouseWebsite.objects.filter(url="https://club-malcolm.com/").update(crawler_class="ClubQuattroCrawler")
    LiveHouseWebsite.objects.filter(url="https://shinjuku-face.com/").update(crawler_class="CycloneCrawler")
    LiveHouseWebsite.objects.filter(url="https://www.fever-popo.com/").update(crawler_class="ShinjukuFaceCrawler")


class Migration(migrations.Migration):
    dependencies = [
        ("houses", "0019_add_grit_at_shibuya"),
    ]

    operations = [
        migrations.RunPython(fix_crawler_classes, revert_crawler_classes),
    ]

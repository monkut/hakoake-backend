from django.db import migrations


def fix_crawlers(apps, schema_editor):
    LiveHouseWebsite = apps.get_model("houses", "LiveHouseWebsite")
    # #160: Assign LoftProjectShelterCrawler to Loft main schedule page
    LiveHouseWebsite.objects.filter(url="https://www.loft-prj.co.jp/schedule/loft").update(
        crawler_class="LoftProjectShelterCrawler"
    )
    # #161: Assign UnitCrawler to UNIT website
    LiveHouseWebsite.objects.filter(url="https://www.unit-tokyo.com/").update(
        crawler_class="UnitCrawler"
    )
    # #163: Update Club Quattro website URL to working Japanese domain
    LiveHouseWebsite.objects.filter(url="https://en.club-quattro.com/shibuya/").update(
        url="https://club-quattro.com/shibuya/"
    )


def revert_crawlers(apps, schema_editor):
    LiveHouseWebsite = apps.get_model("houses", "LiveHouseWebsite")
    LiveHouseWebsite.objects.filter(url="https://www.loft-prj.co.jp/schedule/loft").update(
        crawler_class="WarpCrawler"
    )
    LiveHouseWebsite.objects.filter(url="https://www.unit-tokyo.com/").update(
        crawler_class="SeventhFloorCrawler"
    )
    LiveHouseWebsite.objects.filter(url="https://club-quattro.com/shibuya/").update(
        url="https://en.club-quattro.com/shibuya/"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("houses", "0020_fix_wrong_crawler_class_assignments"),
    ]

    operations = [
        migrations.RunPython(fix_crawlers, revert_crawlers),
    ]

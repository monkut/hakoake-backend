from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("houses", "0011_performanceschedule_event_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="weeklyplaylist",
            name="intro_youtube_video_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="weeklyplaylist",
            name="intro_video_inserted_datetime",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="weeklyplaylist",
            name="instagram_post_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]

"""
Tests confirming that the playlist song-selection ORM filter enforces
MIN_SONG_SELECTION_DURATION_SECONDS correctly.

Context: a Lailah playlist entry was found to be only 18 seconds long.
Prior to the _parse_duration fix, a song whose duration string could not be
parsed was stored with youtube_duration_seconds=30 (the old fallback).
30 >= MIN (25), so it passed the filter and entered the playlist despite the
actual video being shorter than the minimum.

After the fix, unparseable durations are stored as 0.  0 < 25, so such songs
are now excluded.  Songs with a correctly-stored 18-second duration were
always supposed to be excluded; this suite confirms that boundary.
"""

from django.conf import settings
from django.test import TestCase
from performers.models import Performer, PerformerSong


def _make_performer(name: str) -> Performer:
    p = Performer(name=name, name_kana=name, name_romaji=name)
    p._skip_image_fetch = True  # noqa: SLF001
    p.save()
    return p


def _make_song(performer: Performer, duration_seconds: int | None, video_id: str = "vid123") -> PerformerSong:
    return PerformerSong.objects.create(
        performer=performer,
        title=f"Song ({duration_seconds}s)",
        youtube_video_id=video_id,
        youtube_url=f"https://www.youtube.com/watch?v={video_id}",
        youtube_view_count=10000,
        youtube_duration_seconds=duration_seconds,
    )


def _eligible_songs(performer: Performer) -> list[PerformerSong]:
    """Reproduce the ORM filter used by create_weekly_playlist and create_monthly_playlist."""
    min_s = settings.MIN_SONG_SELECTION_DURATION_SECONDS
    max_s = settings.MAX_SONG_SELECTION_DURATION_MINUTES * 60
    return list(
        PerformerSong.objects.filter(
            performer=performer,
            youtube_video_id__isnull=False,
            youtube_duration_seconds__gte=min_s,
            youtube_duration_seconds__lte=max_s,
        )
        .exclude(youtube_video_id="")
        .order_by("-youtube_view_count", "title")
    )


class TestPlaylistMinDurationSetting(TestCase):
    """MIN_SONG_SELECTION_DURATION_SECONDS must be above 18 so Lailah-length songs are blocked."""

    def test_min_duration_greater_than_18(self) -> None:
        self.assertGreater(
            settings.MIN_SONG_SELECTION_DURATION_SECONDS,
            18,
            "MIN_SONG_SELECTION_DURATION_SECONDS must be > 18 to filter out the Lailah entry",
        )


class TestPlaylistDurationFilter(TestCase):
    """Confirm the ORM filter used by playlist creation commands excludes short songs."""

    def setUp(self) -> None:
        self.performer = _make_performer("Lailah")

    def test_18_second_song_excluded(self) -> None:
        """An 18-second song (Lailah's actual duration) must not be eligible for playlist selection."""
        _make_song(self.performer, duration_seconds=18)
        self.assertEqual(_eligible_songs(self.performer), [])

    def test_zero_second_song_excluded(self) -> None:
        """A song stored with duration=0 (new _parse_duration fallback for unparseable strings)
        must not be eligible — this is the path that previously stored 30 and slipped through.
        """
        _make_song(self.performer, duration_seconds=0)
        self.assertEqual(_eligible_songs(self.performer), [])

    def test_null_duration_excluded(self) -> None:
        """A song with no duration data at all (NULL) must not be eligible."""
        _make_song(self.performer, duration_seconds=None)
        self.assertEqual(_eligible_songs(self.performer), [])

    def test_min_boundary_included(self) -> None:
        """A song at exactly MIN_SONG_SELECTION_DURATION_SECONDS must be eligible."""
        min_s = settings.MIN_SONG_SELECTION_DURATION_SECONDS
        song = _make_song(self.performer, duration_seconds=min_s)
        self.assertEqual(_eligible_songs(self.performer), [song])

    def test_one_below_min_boundary_excluded(self) -> None:
        """A song one second below MIN must not be eligible."""
        song = _make_song(self.performer, duration_seconds=settings.MIN_SONG_SELECTION_DURATION_SECONDS - 1)
        self.assertNotIn(song, _eligible_songs(self.performer))

    def test_valid_duration_song_included(self) -> None:
        """A song well within the valid range must be eligible."""
        song = _make_song(self.performer, duration_seconds=240)
        self.assertEqual(_eligible_songs(self.performer), [song])

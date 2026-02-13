import os
import sys
from urllib.parse import quote_plus

import discord
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.embed_utils import (
    PERIOD_LABELS,
    build_collage_embed,
    format_top_tracks,
)
from models import TopTracksModel, TrackModel


def _make_track(name="Song", artist="Artist", rank=1, playcount=10):
    return TrackModel.model_validate(
        {"name": name, "artist": {"name": artist}, "@attr": {"rank": rank}, "playcount": playcount}
    )


def _make_top_tracks(tracks_data):
    raw = [
        {"name": t[0], "artist": {"name": t[1]}, "@attr": {"rank": i + 1}, "playcount": t[2]}
        for i, t in enumerate(tracks_data)
    ]
    return TopTracksModel.model_validate({"toptracks": {"track": raw}})


# --- format_top_tracks ---


class TestFormatTopTracks:
    def test_numbered_list_with_youtube_links(self):
        tracks = [_make_track("My Song", "Cool Artist", 1, 42)]
        result = format_top_tracks(tracks)
        expected_url = f"https://www.youtube.com/results?search_query={quote_plus('Cool Artist My Song')}"
        assert result == f"1. [Cool Artist - My Song]({expected_url}) (42 plays)"

    def test_multiple_tracks(self):
        tracks = [
            _make_track("A", "X", 1, 5),
            _make_track("B", "Y", 2, 3),
        ]
        result = format_top_tracks(tracks)
        lines = result.split("\n")
        assert len(lines) == 2
        assert lines[0].startswith("1. ")
        assert lines[1].startswith("2. ")

    def test_default_limit_is_five(self):
        tracks = [_make_track(f"Song{i}", "Art", i, 1) for i in range(10)]
        result = format_top_tracks(tracks)
        assert len(result.split("\n")) == 5

    def test_respects_custom_limit(self):
        tracks = [_make_track(f"Song{i}", "Art", i, 1) for i in range(10)]
        result = format_top_tracks(tracks, limit=3)
        assert len(result.split("\n")) == 3

    def test_fewer_tracks_than_limit(self):
        tracks = [_make_track("Only", "One", 1, 7)]
        result = format_top_tracks(tracks, limit=5)
        assert len(result.split("\n")) == 1

    def test_youtube_url_uses_quote_plus(self):
        tracks = [_make_track("Hello World", "Foo & Bar", 1, 1)]
        result = format_top_tracks(tracks)
        expected_query = quote_plus("Foo & Bar Hello World")
        assert expected_query in result


# --- build_collage_embed ---


class TestBuildCollageEmbed:
    def test_returns_embed(self):
        top_tracks = _make_top_tracks([("S", "A", 1)])
        embed = build_collage_embed("My Title", top_tracks, "7day")
        assert isinstance(embed, discord.Embed)

    def test_title_matches(self):
        top_tracks = _make_top_tracks([("S", "A", 1)])
        embed = build_collage_embed("My Title", top_tracks, "7day")
        assert embed.title == "My Title"

    def test_color_is_spotify_green(self):
        top_tracks = _make_top_tracks([("S", "A", 1)])
        embed = build_collage_embed("T", top_tracks, "7day")
        assert embed.color.value == 0x1DB954

    def test_description_contains_top_tracks_header(self):
        top_tracks = _make_top_tracks([("Song", "Artist", 10)])
        embed = build_collage_embed("T", top_tracks, "7day")
        assert "Top 5 Tracks:" in embed.description

    def test_description_contains_formatted_tracks(self):
        top_tracks = _make_top_tracks([("Song", "Artist", 10)])
        embed = build_collage_embed("T", top_tracks, "7day")
        assert "Artist - Song" in embed.description
        assert "10 plays" in embed.description

    def test_none_top_tracks_shows_no_tracks_message(self):
        embed = build_collage_embed("T", None, "7day")
        assert embed.description == "*No tracks found for this period.*"

    def test_empty_tracks_list_shows_no_tracks_message(self):
        top_tracks = TopTracksModel.model_validate({"toptracks": {"track": []}})
        embed = build_collage_embed("T", top_tracks, "7day")
        assert embed.description == "*No tracks found for this period.*"

    def test_footer_contains_period_label(self):
        for period_val, label in PERIOD_LABELS.items():
            embed = build_collage_embed("T", None, period_val)
            assert label in embed.footer.text

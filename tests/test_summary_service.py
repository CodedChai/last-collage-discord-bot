import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from models import (
    ArtistModel,
    TopArtistsModel,
    AlbumModel,
    TopAlbumsModel,
    TrackModel,
    TopTracksModel,
)
from services.summary_service import (
    UserListeningData,
    extract_listening_data,
    compute_pair_overlap,
    compute_group_summary,
    format_summary_text,
)


def _make_user(name, artists=None, albums=None, tracks=None):
    """
    Helper to create UserListeningData.
    tracks should be a dict mapping (artist, track) tuples to playcounts,
    or a list of tuples which will be converted to dict with playcount=1.
    """
    if tracks is None:
        tracks_dict = {}
    elif isinstance(tracks, dict):
        tracks_dict = tracks
    else:
        # Convert list of tuples to dict with default playcount of 1
        tracks_dict = {t: 1 for t in tracks}

    return UserListeningData(
        display_name=name,
        artists=set(artists or []),
        albums=set(albums or []),
        tracks=tracks_dict,
    )


class TestExtractListeningData:
    def test_extracts_all_fields(self):
        top_artists = TopArtistsModel.model_validate(
            {
                "topartists": {
                    "artist": [
                        {"name": "Radiohead", "@attr": {"rank": 1}, "playcount": 100},
                        {"name": "Bjork", "@attr": {"rank": 2}, "playcount": 50},
                    ]
                }
            }
        )
        top_albums = TopAlbumsModel.model_validate(
            {
                "topalbums": {
                    "album": [
                        {
                            "name": "OK Computer",
                            "artist": {"name": "Radiohead"},
                            "@attr": {"rank": 1},
                            "playcount": 30,
                            "image": [],
                        },
                    ]
                }
            }
        )
        top_tracks = TopTracksModel.model_validate(
            {
                "toptracks": {
                    "track": [
                        {
                            "name": "Paranoid Android",
                            "artist": {"name": "Radiohead"},
                            "@attr": {"rank": 1},
                            "playcount": 15,
                        },
                    ]
                }
            }
        )

        data = extract_listening_data("Alice", top_artists, top_albums, top_tracks)

        assert data.display_name == "Alice"
        assert data.artists == {"Radiohead", "Bjork"}
        assert data.albums == {("Radiohead", "OK Computer")}
        assert data.tracks == {("Radiohead", "Paranoid Android"): 15}

    def test_handles_none_inputs(self):
        data = extract_listening_data("Bob", None, None, None)
        assert data.artists == set()
        assert data.albums == set()
        assert data.tracks == {}


class TestComputePairOverlap:
    def test_full_overlap(self):
        a = _make_user(
            "A", artists=["X", "Y"], albums=[("X", "Album1")], tracks=[("X", "Song1")]
        )
        b = _make_user(
            "B", artists=["X", "Y"], albums=[("X", "Album1")], tracks=[("X", "Song1")]
        )
        overlap = compute_pair_overlap(a, b)
        assert overlap.shared_artists == {"X", "Y"}
        assert overlap.shared_albums == {("X", "Album1")}
        assert overlap.shared_tracks == {("X", "Song1")}
        assert overlap.total_shared == 4

    def test_no_overlap(self):
        a = _make_user("A", artists=["X"])
        b = _make_user("B", artists=["Y"])
        overlap = compute_pair_overlap(a, b)
        assert overlap.total_shared == 0

    def test_partial_overlap(self):
        a = _make_user("A", artists=["X", "Y", "Z"])
        b = _make_user("B", artists=["Y", "Z", "W"])
        overlap = compute_pair_overlap(a, b)
        assert overlap.shared_artists == {"Y", "Z"}
        assert overlap.total_shared == 2


class TestComputeGroupSummary:
    def test_single_user_no_overlap(self):
        users = [_make_user("A", artists=["X"])]
        summary = compute_group_summary(users)
        assert summary.most_overlapping is None
        assert summary.biggest_outlier is None
        assert summary.user_count == 1

    def test_two_users_with_overlap(self):
        a = _make_user("Alice", artists=["Radiohead", "Bjork", "Portishead"])
        b = _make_user("Bob", artists=["Radiohead", "Bjork", "Tool"])
        summary = compute_group_summary([a, b])
        assert summary.most_overlapping is not None
        assert summary.most_overlapping.total_shared == 2
        assert "Radiohead" in summary.most_overlapping.shared_artists
        assert summary.user_count == 2

    def test_three_users_outlier(self):
        a = _make_user("Alice", artists=["X", "Y", "Z"])
        b = _make_user("Bob", artists=["X", "Y", "W"])
        c = _make_user("Charlie", artists=["Q", "R", "S"])
        summary = compute_group_summary([a, b, c])
        assert summary.biggest_outlier == "Charlie"
        assert summary.most_overlapping.user_a == "Alice"
        assert summary.most_overlapping.user_b == "Bob"

    def test_popular_artists_need_two_listeners(self):
        a = _make_user("A", artists=["X", "Y"])
        b = _make_user("B", artists=["X", "Z"])
        c = _make_user("C", artists=["Z", "W"])
        summary = compute_group_summary([a, b, c])
        popular_names = [name for name, _ in summary.popular_artists]
        assert "X" in popular_names
        assert "Z" in popular_names
        assert "Y" not in popular_names
        assert "W" not in popular_names

    def test_no_overlap_produces_none_most_overlapping(self):
        a = _make_user("A", artists=["X"])
        b = _make_user("B", artists=["Y"])
        summary = compute_group_summary([a, b])
        assert summary.most_overlapping is None

    def test_empty_list(self):
        summary = compute_group_summary([])
        assert summary.most_overlapping is None
        assert summary.biggest_outlier is None
        assert summary.user_count == 0


class TestFormatSummaryText:
    def test_no_overlap_message(self):
        summary = compute_group_summary(
            [
                _make_user("A", artists=["X"]),
                _make_user("B", artists=["Y"]),
            ]
        )
        text = format_summary_text(summary)
        assert "unique taste" in text

    def test_includes_overlap_info(self):
        a = _make_user("Alice", artists=["Radiohead", "Bjork"])
        b = _make_user("Bob", artists=["Radiohead", "Bjork"])
        summary = compute_group_summary([a, b])
        text = format_summary_text(summary)
        assert "Alice" in text
        assert "Bob" in text
        assert "most in common" in text

    def test_includes_outlier(self):
        a = _make_user("Alice", artists=["X", "Y"])
        b = _make_user("Bob", artists=["X", "Y"])
        c = _make_user("Charlie", artists=["Q", "R"])
        summary = compute_group_summary([a, b, c])
        text = format_summary_text(summary)
        assert "Charlie" in text
        assert "outlier" in text

    def test_includes_popular(self):
        a = _make_user("A", artists=["Radiohead", "Bjork"])
        b = _make_user("B", artists=["Radiohead", "Tool"])
        summary = compute_group_summary([a, b])
        text = format_summary_text(summary)
        assert "Radiohead" in text
        assert "Group Favorite" in text
        # Check that usernames are shown
        assert "(A, B)" in text

    def test_popular_tracks_include_youtube_links(self):
        """Popular tracks should have YouTube links in the format"""
        a = _make_user("A", tracks={("Artist A", "Song A"): 5, ("Shared", "Track"): 10})
        b = _make_user("B", tracks={("Artist B", "Song B"): 3, ("Shared", "Track"): 8})
        summary = compute_group_summary([a, b])
        text = format_summary_text(summary)
        # Should contain YouTube link for shared track
        assert "https://www.youtube.com/results?search_query=" in text
        assert "[Shared - Track]" in text


class TestHiddenGem:
    def test_hidden_gem_with_high_playcount(self):
        """Track with only 1 listener and >10 plays should be the hidden gem"""
        a = _make_user(
            "Alice",
            tracks={("Artist A", "Song A"): 15, ("Shared Artist", "Shared Song"): 5},
        )
        b = _make_user("Bob", tracks={("Shared Artist", "Shared Song"): 8})
        summary = compute_group_summary([a, b])
        assert summary.hidden_gem is not None
        user, track, plays = summary.hidden_gem
        assert user == "Alice"
        assert track == "Artist A - Song A"
        assert plays == 15

    def test_no_hidden_gem_when_playcount_too_low(self):
        """Track with <=10 plays should not be hidden gem"""
        a = _make_user("Alice", tracks={("Artist A", "Song A"): 10})
        b = _make_user("Bob", tracks={("Artist B", "Song B"): 5})
        summary = compute_group_summary([a, b])
        assert summary.hidden_gem is None

    def test_hidden_gem_picks_highest_playcount(self):
        """When multiple candidates exist, pick the one with highest playcount"""
        a = _make_user(
            "Alice", tracks={("Artist A", "Song A"): 15, ("Artist B", "Song B"): 20}
        )
        b = _make_user("Bob", tracks={("Artist C", "Song C"): 12})
        summary = compute_group_summary([a, b])
        assert summary.hidden_gem is not None
        user, track, plays = summary.hidden_gem
        assert user == "Alice"
        assert track == "Artist B - Song B"
        assert plays == 20

    def test_no_hidden_gem_when_track_shared(self):
        """Track with 2+ listeners should not be hidden gem even with high plays"""
        a = _make_user("Alice", tracks={("Shared", "Song"): 50})
        b = _make_user("Bob", tracks={("Shared", "Song"): 30})
        summary = compute_group_summary([a, b])
        assert summary.hidden_gem is None

    def test_hidden_gem_shown_in_format(self):
        """Hidden gem should appear in formatted text with YouTube link"""
        a = _make_user("Alice", tracks={("Obscure Band", "Deep Cut"): 25})
        b = _make_user("Bob", tracks={("Popular", "Hit"): 5})
        summary = compute_group_summary([a, b])
        text = format_summary_text(summary)
        assert "hidden gem" in text.lower()
        assert "Alice" in text
        assert "[Obscure Band - Deep Cut]" in text
        assert "https://www.youtube.com/results?search_query=" in text
        assert "on repeat" in text
        assert "25 plays" in text

    def test_no_hidden_gem_in_format_when_none(self):
        """Format should not mention hidden gem when there is none"""
        a = _make_user("Alice", tracks={("Artist", "Song"): 5})
        b = _make_user("Bob", tracks={("Artist", "Song"): 3})
        summary = compute_group_summary([a, b])
        text = format_summary_text(summary)
        assert "hidden gem" not in text.lower()

    def test_hidden_gem_with_single_user(self):
        """Single user with high playcount track should have hidden gem"""
        a = _make_user("Alice", tracks={("Solo", "Track"): 15})
        summary = compute_group_summary([a])
        assert summary.hidden_gem is not None
        user, track, plays = summary.hidden_gem
        assert user == "Alice"
        assert plays == 15

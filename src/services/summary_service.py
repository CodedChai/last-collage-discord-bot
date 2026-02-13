from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Optional
from urllib.parse import quote_plus

from models import TopArtistsModel, TopAlbumsModel, TopTracksModel


@dataclass
class UserListeningData:
    display_name: str
    artists: set[str]
    albums: set[tuple[str, str]]  # (artist, album)
    tracks: dict[tuple[str, str], int]  # (artist, track) -> playcount


@dataclass
class PairOverlap:
    user_a: str
    user_b: str
    shared_artists: set[str]
    shared_albums: set[tuple[str, str]]
    shared_tracks: set[tuple[str, str]]  # Just the track tuples, not playcounts

    @property
    def total_shared(self) -> int:
        return (
            len(self.shared_artists) + len(self.shared_albums) + len(self.shared_tracks)
        )


@dataclass
class GroupSummary:
    most_overlapping: Optional[PairOverlap]
    biggest_outlier: Optional[str]
    popular_artists: list[tuple[str, int]]
    popular_albums: list[tuple[str, int]]
    popular_tracks: list[tuple[str, int]]
    hidden_gem: Optional[tuple[str, str, int]]  # (user, track_name, playcount)
    user_count: int


def extract_listening_data(
    display_name: str,
    top_artists: Optional[TopArtistsModel],
    top_albums: Optional[TopAlbumsModel],
    top_tracks: Optional[TopTracksModel],
) -> UserListeningData:
    artists: set[str] = set()
    albums: set[tuple[str, str]] = set()
    tracks: dict[tuple[str, str], int] = {}

    if top_artists:
        artists = {a.name for a in top_artists.artists}
    if top_albums:
        albums = {(a.artist, a.name) for a in top_albums.albums}
    if top_tracks:
        tracks = {(t.artist, t.name): t.playcount for t in top_tracks.tracks}

    return UserListeningData(
        display_name=display_name,
        artists=artists,
        albums=albums,
        tracks=tracks,
    )


def compute_pair_overlap(a: UserListeningData, b: UserListeningData) -> PairOverlap:
    return PairOverlap(
        user_a=a.display_name,
        user_b=b.display_name,
        shared_artists=a.artists & b.artists,
        shared_albums=a.albums & b.albums,
        shared_tracks=set(a.tracks.keys()) & set(b.tracks.keys()),
    )


def compute_group_summary(users: list[UserListeningData]) -> GroupSummary:
    if not users:
        return GroupSummary(
            most_overlapping=None,
            biggest_outlier=None,
            popular_artists=[],
            popular_albums=[],
            popular_tracks=[],
            hidden_gem=None,
            user_count=0,
        )

    # Compute all pairwise overlaps
    best_overlap: Optional[PairOverlap] = None
    overlap_scores: dict[str, int] = {u.display_name: 0 for u in users}

    for a, b in combinations(users, 2):
        overlap = compute_pair_overlap(a, b)
        if overlap.total_shared > 0:
            overlap_scores[a.display_name] += overlap.total_shared
            overlap_scores[b.display_name] += overlap.total_shared
            if best_overlap is None or overlap.total_shared > best_overlap.total_shared:
                best_overlap = overlap

    # Find biggest outlier (lowest overlap score among 2+ users)
    biggest_outlier: Optional[str] = None
    if len(users) >= 2:
        biggest_outlier = min(overlap_scores, key=lambda k: overlap_scores[k])
        # If everyone has the same score, no meaningful outlier
        if all(v == overlap_scores[biggest_outlier] for v in overlap_scores.values()):
            biggest_outlier = None

    # Popular items: count how many users listen to each
    artist_counter: Counter[str] = Counter()
    album_counter: Counter[str] = Counter()
    track_counter: Counter[str] = Counter()
    track_plays: dict[
        tuple[str, str], tuple[str, int]
    ] = {}  # track -> (user, playcount)

    for u in users:
        for a in u.artists:
            artist_counter[a] += 1
        for a in u.albums:
            album_counter[f"{a[0]} - {a[1]}"] += 1
        for track_tuple, playcount in u.tracks.items():
            track_name = f"{track_tuple[0]} - {track_tuple[1]}"
            track_counter[track_name] += 1
            # Track the user and playcount for hidden gem detection
            if track_tuple not in track_plays:
                track_plays[track_tuple] = (u.display_name, playcount)

    # Only include items with 2+ listeners
    popular_artists = [
        (name, count) for name, count in artist_counter.most_common() if count >= 2
    ]
    popular_albums = [
        (name, count) for name, count in album_counter.most_common() if count >= 2
    ]
    popular_tracks = [
        (name, count) for name, count in track_counter.most_common() if count >= 2
    ]

    # Hidden gem: highest playcount track with only 1 listener and >10 plays
    hidden_gem: Optional[tuple[str, str, int]] = None
    for track_tuple, (user, playcount) in track_plays.items():
        track_name = f"{track_tuple[0]} - {track_tuple[1]}"
        # Only 1 listener and >10 plays
        if track_counter[track_name] == 1 and playcount > 10:
            if hidden_gem is None or playcount > hidden_gem[2]:
                hidden_gem = (user, track_name, playcount)

    return GroupSummary(
        most_overlapping=best_overlap,
        biggest_outlier=biggest_outlier,
        popular_artists=popular_artists,
        popular_albums=popular_albums,
        popular_tracks=popular_tracks,
        hidden_gem=hidden_gem,
        user_count=len(users),
    )


def format_summary_text(summary: GroupSummary) -> str:
    lines: list[str] = []

    if summary.most_overlapping:
        o = summary.most_overlapping
        lines.append(
            f"🎵 **{o.user_a}** and **{o.user_b}** have the most in common "
            f"({o.total_shared} shared)!"
        )
    else:
        lines.append("🎵 Everyone has pretty unique taste — no overlap found!")

    if summary.biggest_outlier:
        lines.append(
            f"🦄 **{summary.biggest_outlier}** is the biggest outlier of the group."
        )

    if summary.popular_artists:
        top = ", ".join(
            f"**{name}** ({count})" for name, count in summary.popular_artists[:5]
        )
        lines.append(f"🏆 group favorite artists: {top}")

    if summary.popular_albums:
        top = ", ".join(
            f"**{name}** ({count})" for name, count in summary.popular_albums[:5]
        )
        lines.append(f"💿 group favorite albums: {top}")

    if summary.popular_tracks:
        formatted_tracks = []
        for name, count in summary.popular_tracks[:5]:
            # name is already in "Artist - Track" format
            youtube_url = f"https://www.youtube.com/results?search_query={quote_plus(name.replace(' - ', ' '))}"
            formatted_tracks.append(f"[{name}]({youtube_url}) ({count})")
        lines.append(f"🎶 group favorite tracks: {', '.join(formatted_tracks)}")

    if summary.hidden_gem:
        user, track_name, playcount = summary.hidden_gem
        # track_name is in "Artist - Track" format
        youtube_url = f"https://www.youtube.com/results?search_query={quote_plus(track_name.replace(' - ', ' '))}"
        lines.append(
            f"💎 hidden gem: **{user}** has [{track_name}]({youtube_url}) on repeat ({playcount} plays)!"
        )

    return "\n".join(lines)

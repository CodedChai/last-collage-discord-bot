from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Optional

from models import TopArtistsModel, TopAlbumsModel, TopTracksModel


@dataclass
class UserListeningData:
    display_name: str
    artists: set[str]
    albums: set[tuple[str, str]]
    tracks: dict[tuple[str, str], int]


@dataclass
class PairOverlap:
    user_a: str
    user_b: str
    shared_artists: set[str]
    shared_albums: set[tuple[str, str]]
    shared_tracks: set[tuple[str, str]]

    @property
    def total_shared(self) -> int:
        return (
            len(self.shared_artists) + len(self.shared_albums) + len(self.shared_tracks)
        )


@dataclass
class GroupSummary:
    most_overlapping: Optional[PairOverlap]
    biggest_outlier: Optional[str]
    popular_artists: list[tuple[str, list[str]]]
    popular_albums: list[tuple[str, list[str]]]
    popular_tracks: list[tuple[str, list[str]]]
    hidden_gem: Optional[tuple[str, str, int]]
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

    best_overlap: Optional[PairOverlap] = None
    overlap_scores: dict[str, int] = {u.display_name: 0 for u in users}

    for a, b in combinations(users, 2):
        overlap = compute_pair_overlap(a, b)
        if overlap.total_shared > 0:
            overlap_scores[a.display_name] += overlap.total_shared
            overlap_scores[b.display_name] += overlap.total_shared
            if best_overlap is None or overlap.total_shared > best_overlap.total_shared:
                best_overlap = overlap

    biggest_outlier: Optional[str] = None
    if len(users) >= 2:
        biggest_outlier = min(overlap_scores, key=lambda k: overlap_scores[k])
        if all(v == overlap_scores[biggest_outlier] for v in overlap_scores.values()):
            biggest_outlier = None

    artist_users: dict[str, list[str]] = {}
    album_users: dict[str, list[str]] = {}
    track_users: dict[str, list[str]] = {}
    track_plays: dict[tuple[str, str], tuple[str, int]] = {}

    for u in users:
        for a in u.artists:
            if a not in artist_users:
                artist_users[a] = []
            artist_users[a].append(u.display_name)

        for a in u.albums:
            album_name = f"{a[0]} - {a[1]}"
            if album_name not in album_users:
                album_users[album_name] = []
            album_users[album_name].append(u.display_name)

        for track_tuple, playcount in u.tracks.items():
            track_name = f"{track_tuple[0]} - {track_tuple[1]}"
            if track_name not in track_users:
                track_users[track_name] = []
            track_users[track_name].append(u.display_name)

            if track_tuple not in track_plays:
                track_plays[track_tuple] = (u.display_name, playcount)

    popular_artists = sorted(
        [
            (name, user_list)
            for name, user_list in artist_users.items()
            if len(user_list) >= 2
        ],
        key=lambda x: len(x[1]),
        reverse=True,
    )
    popular_albums = sorted(
        [
            (name, user_list)
            for name, user_list in album_users.items()
            if len(user_list) >= 2
        ],
        key=lambda x: len(x[1]),
        reverse=True,
    )
    popular_tracks = sorted(
        [
            (name, user_list)
            for name, user_list in track_users.items()
            if len(user_list) >= 2
        ],
        key=lambda x: len(x[1]),
        reverse=True,
    )

    hidden_gem: Optional[tuple[str, str, int]] = None
    for track_tuple, (user, playcount) in track_plays.items():
        track_name = f"{track_tuple[0]} - {track_tuple[1]}"
        if len(track_users.get(track_name, [])) == 1 and playcount > 10:
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

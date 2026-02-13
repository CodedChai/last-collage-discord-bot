import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, AliasPath, field_validator


LASTFM_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{2,15}$")

VALID_PERIODS = {"7day", "1month", "3month", "6month", "12month", "overall"}
VALID_GRID_SIZES = {"dynamic", "2", "3", "4", "5"}


def sanitize_username(username: str) -> str:
    username = username.strip()
    if not LASTFM_USERNAME_PATTERN.match(username):
        raise ValueError(
            "Last.fm username must be 2-15 characters and contain only letters, numbers, hyphens, or underscores."
        )
    return username


# --- Last.fm API response models ---


class ArtistModel(BaseModel):
    name: str
    rank: int = Field(validation_alias=AliasPath("@attr", "rank"))
    playcount: int


class TopArtistsModel(BaseModel):
    artists: List[ArtistModel] = Field(
        validation_alias=AliasPath("topartists", "artist")
    )


class TrackModel(BaseModel):
    name: str
    artist: str = Field(validation_alias=AliasPath("artist", "name"))
    rank: int = Field(validation_alias=AliasPath("@attr", "rank"))
    playcount: int


class TopTracksModel(BaseModel):
    tracks: List[TrackModel] = Field(validation_alias=AliasPath("toptracks", "track"))


class AlbumModel(BaseModel):
    name: str
    artist: str = Field(validation_alias=AliasPath("artist", "name"))
    rank: int = Field(validation_alias=AliasPath("@attr", "rank"))
    playcount: int
    image_url: Optional[str] = Field(default=None, validation_alias="image")

    @field_validator("image_url", mode="before")
    @classmethod
    def extract_image(cls, v):
        if isinstance(v, list):
            for img in reversed(v):
                if img.get("#text"):
                    url = img["#text"]
                    if url.endswith(".png"):
                        url = url[:-4] + ".jpg"
                    return url
        return None


class TopAlbumsModel(BaseModel):
    albums: List[AlbumModel] = Field(validation_alias=AliasPath("topalbums", "album"))


class ArtistModel(BaseModel):
    name: str
    rank: int = Field(validation_alias=AliasPath("@attr", "rank"))
    playcount: int


class TopArtistsModel(BaseModel):
    artists: List[ArtistModel] = Field(
        validation_alias=AliasPath("topartists", "artist")
    )


# --- User input models ---


class CollageRequest(BaseModel):
    username: str
    period: Literal["7day", "1month", "3month", "6month", "12month", "overall"]
    grid_size: Literal["dynamic", "2", "3", "4", "5"]

    @field_validator("username", mode="before")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return sanitize_username(v)


class WeeklyJoinRequest(BaseModel):
    username: str
    guild_id: int
    channel_id: int
    discord_user_id: int

    @field_validator("username", mode="before")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return sanitize_username(v)


# --- Database row models ---


class UserPreference(BaseModel):
    discord_user_id: int
    lastfm_username: str


class WeeklySchedule(BaseModel):
    lastfm_username: str
    guild_id: int
    channel_id: int
    discord_user_id: int

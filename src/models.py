from typing import List, Optional

from pydantic import BaseModel, Field, AliasPath, field_validator


class TrackModel(BaseModel):
    name: str
    artist: str = Field(validation_alias=AliasPath("artist", "name"))
    rank: int = Field(validation_alias=AliasPath("@attr", "rank"))
    playcount: int


class TopTracksModel(BaseModel):
    tracks: List[TrackModel] = Field(
        validation_alias=AliasPath("toptracks", "track")
    )


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
    albums: List[AlbumModel] = Field(
        validation_alias=AliasPath("topalbums", "album")
    )

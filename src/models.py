from typing import List, Optional
from pydantic import BaseModel, Field, AliasPath, field_validator


class TrackModel(BaseModel):
    name: str
    # Reach into artist -> #text
    artist: str = Field(validation_alias=AliasPath("artist", "#text"))
    # Reach into @attr -> rank
    rank: int = Field(validation_alias=AliasPath("@attr", "rank"))
    playcount: int

    # TODO: I think these images are useless
    # We'll calculate this in a validator
    image_url: Optional[str] = None

    @field_validator("image_url", mode="before")
    @classmethod
    def extract_image(cls, v):
        # The 'before' validator receives the raw 'image' list from the JSON
        # 'v' here will be the list of image dicts if we map it correctly
        if isinstance(v, list):
            # Grab the 'large' image URL
            for img in v:
                if img.get("size") == "large":
                    return img.get("#text")
        return None


class WeeklyTrackChartModel(BaseModel):
    tracks: List[TrackModel] = Field(
        validation_alias=AliasPath("weeklytrackchart", "track")
    )

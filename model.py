from pydantic import BaseModel

class Keyframe(BaseModel):
    video_id: str
    frame_index: int
    filename: str

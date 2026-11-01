from dataclasses import dataclass

from common import fields, number
from media import identifier


@dataclass(frozen=True)
class Clip:
    asset: str
    duration: float
    sourceStart: float = 0
    mute: bool = False

    def __post_init__(self):
        identifier(self.asset)
        number(self.duration, 'clip.duration', positive=True)
        number(self.sourceStart, 'clip.sourceStart')
        if not isinstance(self.mute, bool):
            raise ValueError('clip.mute must be boolean.')

    @classmethod
    def parse(cls, value):
        fields(value, ('asset', 'duration'), ('sourceStart', 'mute'))
        return cls(**value)


@dataclass(frozen=True)
class AudioTrack:
    asset: str
    start: float = 0
    volume: float = 1
    loop: bool = False

    def __post_init__(self):
        identifier(self.asset)
        number(self.start, 'audio.start')
        number(self.volume, 'audio.volume')
        if self.volume > 2 or not isinstance(self.loop, bool):
            raise ValueError('Audio volume must be <= 2 and loop must be boolean.')

    @classmethod
    def parse(cls, value):
        fields(value, ('asset',), ('start', 'volume', 'loop'))
        return cls(**value)


@dataclass(frozen=True)
class Timeline:
    width: int
    height: int
    fps: int
    clips: tuple
    audio: tuple

    @property
    def duration(self):
        return sum(clip.duration for clip in self.clips)

    @classmethod
    def parse(cls, value):
        fields(value, ('width', 'height', 'fps', 'clips'), ('audio',))
        for key in ('width', 'height', 'fps'):
            number(value[key], key, positive=True, integer=True)
        if value['width'] % 2 or value['height'] % 2:
            raise ValueError('H.264 output dimensions must be even.')
        if not isinstance(value['clips'], list) or not value['clips']:
            raise ValueError('clips must be a nonempty array.')
        if not isinstance(value.get('audio', []), list):
            raise ValueError('audio must be an array.')
        result = cls(
            width=value['width'], height=value['height'], fps=value['fps'],
            clips=tuple(Clip.parse(clip) for clip in value['clips']),
            audio=tuple(AudioTrack.parse(track) for track in value.get('audio', [])),
        )
        for track in result.audio:
            if track.start >= result.duration:
                raise ValueError('Audio track starts outside the timeline.')
        return result

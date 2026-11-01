from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from common import digest, duration, fields, local_path, probe, read_json, write_json


MEDIA_TOOLS = {
    'image_generate': 'image',
    'text_to_speech': 'audio',
    'video_generate': 'video',
    'music_generate': 'audio',
    'user': None,
}
IMAGE_CODECS = {'png', 'mjpeg', 'webp', 'gif', 'bmp', 'tiff', 'av1'}
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.avif'}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', value):
        raise ValueError('Asset id must contain 1-80 letters, digits, _ or -.')
    return value


@dataclass(frozen=True)
class MediaReceipt:
    id: str
    tool: str
    status: str
    localPath: str

    def __post_init__(self):
        identifier(self.id)
        if not isinstance(self.tool, str) or self.tool not in MEDIA_TOOLS:
            raise ValueError('Unsupported media tool.')
        if self.status != 'completed':
            raise ValueError('Only confirmed successful media can be imported.')
        if not isinstance(self.localPath, str) or not self.localPath.strip():
            raise ValueError('localPath must identify the actual completed file.')

    @classmethod
    def parse(cls, value):
        fields(value, ('id', 'tool', 'status', 'localPath'))
        return cls(**value)


def media_type(path, info):
    streams = info.get('streams', [])
    video = [stream for stream in streams
             if stream.get('codec_type') == 'video'
             and not stream.get('disposition', {}).get('attached_pic')]
    if video:
        if (path.suffix.lower() in IMAGE_SUFFIXES
                and video[0].get('codec_name') in IMAGE_CODECS):
            return 'image'
        return 'video'
    if any(stream.get('codec_type') == 'audio' for stream in streams):
        return 'audio'
    raise ValueError(f'No usable media stream: {path.name}')


def manifest(project):
    path = local_path(project, 'assets.json')
    if not path.exists():
        return {'version': 1, 'assets': []}
    value = read_json(path)
    fields(value, ('version', 'assets'))
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid asset manifest version.')
    if not isinstance(value['assets'], list):
        raise ValueError('Invalid asset manifest.')
    for asset in value['assets']:
        fields(asset, ('id', 'type', 'path', 'tool', 'sha256', 'probe'))
        identifier(asset['id'])
        if not isinstance(asset['type'], str) or asset['type'] not in {
            'image', 'audio', 'video',
        }:
            raise ValueError('Invalid asset media type.')
        if not isinstance(asset['tool'], str) or asset['tool'] not in MEDIA_TOOLS:
            raise ValueError('Invalid asset source tool.')
        if (not isinstance(asset['sha256'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', asset['sha256'])):
            raise ValueError('Invalid asset digest.')
        if not isinstance(asset['probe'], dict):
            raise ValueError('Invalid asset media information.')
        path = local_path(project, asset['path'], exists=True)
        if not path.is_file() or digest(path) != asset['sha256']:
            raise ValueError(f'Asset content has changed: {asset["id"]}')
    ids = [asset['id'] for asset in value['assets']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate asset ids in manifest.')
    return value


def import_media(workspace, project, value):
    receipt = MediaReceipt.parse(value)
    source = local_path(workspace, receipt.localPath, exists=True)
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError('Media input must be a nonempty file.')
    info = probe(source)
    kind = media_type(source, info)
    expected = MEDIA_TOOLS[receipt.tool]
    if expected and kind != expected:
        raise ValueError(f'{receipt.tool} returned {kind}, expected {expected}.')
    if kind != 'image' and duration(info) <= 0:
        raise ValueError('Audio/video duration must be positive.')
    suffix = source.suffix.lower()
    if not re.fullmatch(r'\.[a-z0-9]{1,8}', suffix):
        raise ValueError('Media input requires a normal file extension.')
    target = local_path(project, f'assets/{receipt.id}{suffix}')
    entry = {
        'id': receipt.id, 'type': kind, 'path': str(target.relative_to(project)),
        'tool': receipt.tool, 'sha256': digest(source), 'probe': info,
    }
    current = manifest(project)
    previous = [asset for asset in current['assets'] if asset['id'] == receipt.id]
    if previous:
        if previous[0] != entry:
            raise ValueError(f'Asset id already exists: {receipt.id}')
        return previous[0]
    if target.exists():
        raise ValueError(f'Asset destination already exists: {target.name}')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    write_json(project / 'assets.json', {
        **current, 'assets': [*current['assets'], entry],
    })
    return entry

from pathlib import Path
from fractions import Fraction
import re
import shutil
import tempfile

from common import command, duration, local_path, number, probe
from media import manifest, media_type


def video_duration(info):
    streams = [stream for stream in info.get('streams', [])
               if stream.get('codec_type') == 'video'
               and not stream.get('disposition', {}).get('attached_pic')]
    if not streams:
        raise ValueError('Video stream duration is unavailable.')
    stream = streams[0]
    if 'duration' in stream:
        value = float(stream['duration'])
    elif 'duration_ts' in stream and 'time_base' in stream:
        value = float(int(stream['duration_ts']) * Fraction(stream['time_base']))
    else:
        tagged = stream.get('tags', {}).get('DURATION', '')
        match = re.fullmatch(r'(\d+):(\d{2}):(\d{2}(?:\.\d+)?)', tagged)
        if not match:
            raise ValueError('Video stream duration is unavailable.')
        hours, minutes, seconds = map(float, match.groups())
        value = hours * 3600 + minutes * 60 + seconds
    return number(value, 'video stream duration', positive=True)


def asset_index(project):
    return {asset['id']: asset for asset in manifest(project)['assets']}


def checked_asset(project, assets, asset_id, allowed):
    if asset_id not in assets:
        raise ValueError(f'Unknown asset: {asset_id}')
    entry = assets[asset_id]
    source = local_path(project, entry['path'], exists=True)
    info = probe(source)
    if media_type(source, info) not in allowed:
        raise ValueError(f'Asset {asset_id} has the wrong media type.')
    return source, info


def validate_sources(project, timeline, assets):
    for clip in timeline.clips:
        source, info = checked_asset(
            project, assets, clip.asset, {'image', 'video'},
        )
        if media_type(source, info) == 'video':
            if clip.sourceStart + clip.duration > video_duration(info) + 0.05:
                raise ValueError(f'Clip exceeds source duration: {clip.asset}')
        elif clip.sourceStart:
            raise ValueError('Still images cannot have sourceStart.')
    for track in timeline.audio:
        _, info = checked_asset(project, assets, track.asset, {'audio'})
        if assets[track.asset]['tool'] == 'text_to_speech':
            if track.loop or track.start + duration(info) > timeline.duration + 0.05:
                raise ValueError('Narration must fit the timeline without looping.')


def render_clip(project, clip, timeline, assets, output):
    source, info = checked_asset(project, assets, clip.asset, {'image', 'video'})
    still = media_type(source, info) == 'image'
    input_args = (
        ['-stream_loop', '-1'] if still
        else ['-ss', str(clip.sourceStart)]
    )
    audio = not clip.mute and not still and any(
        stream.get('codec_type') == 'audio' for stream in info['streams']
    )
    silence = [] if audio else [
        '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
    ]
    width, height = timeline.width, timeline.height
    video_filter = (
        f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
        f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,'
        f'fps={timeline.fps},format=yuv420p'
    )
    command([
        'ffmpeg', '-nostdin', '-v', 'error', '-n', *input_args, '-i', source,
        *silence, '-map', '0:v:0', '-map', '0:a:0' if audio else '1:a:0',
        '-t', str(clip.duration), '-vf', video_filter,
        '-af', f'apad,atrim=duration={clip.duration},asetpts=PTS-STARTPTS',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
        '-c:a', 'aac', '-ar', '48000', '-ac', '2', output,
    ], timeout=max(120, int(clip.duration * 30)))


def mix_audio(project, timeline, assets, base, output):
    inputs, filters = [], []
    for index, track in enumerate(timeline.audio, 1):
        source, _ = checked_asset(project, assets, track.asset, {'audio'})
        loop = ['-stream_loop', '-1'] if track.loop else []
        inputs = [*inputs, *loop, '-i', source]
        delay = round(track.start * 1000)
        filters = [*filters, (
            f'[{index}:a:0]aresample=48000,volume={track.volume},'
            f'adelay={delay}:all=1[a{index}]'
        )]
    labels = '[0:a:0]' + ''.join(
        f'[a{i}]' for i in range(1, len(timeline.audio) + 1)
    )
    filters = [*filters, (
        f'{labels}amix=inputs={len(timeline.audio) + 1}:'
        'duration=first:normalize=0,alimiter=limit=0.95:latency=1[mix]'
    )]
    command([
        'ffmpeg', '-nostdin', '-v', 'error', '-n', '-i', base, *inputs,
        '-filter_complex', ';'.join(filters), '-map', '0:v:0', '-map', '[mix]',
        '-c:v', 'copy', '-c:a', 'aac', '-t', str(timeline.duration),
        '-movflags', '+faststart', output,
    ], timeout=max(120, int(timeline.duration * 10)))


def render(project, timeline, output_name='renders/final.mp4'):
    assets = asset_index(project)
    validate_sources(project, timeline, assets)
    output = local_path(project, output_name)
    if output.exists() or output.suffix.lower() != '.mp4':
        raise ValueError('Output must be a new MP4 file.')
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = local_path(project, '.render-work')
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        temporary = Path(directory)
        for index, clip in enumerate(timeline.clips):
            render_clip(
                project, clip, timeline, assets, temporary / f'{index:04d}.mp4',
            )
        concat = temporary / 'segments.txt'
        concat.write_text(''.join(
            f"file '{index:04d}.mp4'\n" for index in range(len(timeline.clips))
        ), encoding='utf-8')
        base = temporary / 'base.mp4'
        command([
            'ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'concat', '-safe', '1',
            '-i', concat, '-c', 'copy', '-movflags', '+faststart', base,
        ], timeout=max(120, int(timeline.duration * 5)))
        final = temporary / 'final.mp4'
        if timeline.audio:
            mix_audio(project, timeline, assets, base, final)
        else:
            shutil.copyfile(base, final)
        with output.open('xb') as destination, final.open('rb') as source:
            shutil.copyfileobj(source, destination)
    return output

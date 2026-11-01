from common import command, digest, duration, local_path, probe
from render import video_duration


def verify(project, output, timeline):
    info = probe(output)
    streams = info.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if not video or not audio:
        raise ValueError('Final video must contain video and audio streams.')
    if (video.get('width'), video.get('height')) != (timeline.width, timeline.height):
        raise ValueError('Final video dimensions differ from the timeline.')
    tolerance = max(0.15, 2 / timeline.fps)
    actual = duration(info)
    if abs(actual - timeline.duration) > tolerance:
        raise ValueError(f'Unexpected video duration: {actual}')
    if abs(video_duration(info) - timeline.duration) > tolerance:
        raise ValueError('Video stream duration differs from the timeline.')
    audio_duration = float(audio.get('duration', 0))
    if abs(audio_duration - timeline.duration) > tolerance:
        raise ValueError(f'Unexpected audio duration: {audio_duration}')
    numerator, denominator = video.get('avg_frame_rate', '0/1').split('/')
    if abs(float(numerator) / float(denominator) - timeline.fps) > 0.01:
        raise ValueError('Unexpected video frame rate.')
    command([
        'ffmpeg', '-nostdin', '-v', 'error', '-i', output,
        '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-',
    ], timeout=max(120, int(actual * 10)))
    frames = local_path(project, 'qa')
    frames.mkdir(exist_ok=True)
    for name, timestamp in (
        ('first', 0), ('middle', actual / 2),
        ('last', max(0, timeline.duration - 1 / timeline.fps)),
    ):
        target = local_path(project, f'qa/{name}.png')
        command([
            'ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(timestamp),
            '-i', output, '-frames:v', '1', target,
        ])
        if not target.is_file() or not target.stat().st_size:
            raise ValueError(f'Missing QA frame: {name}')
    levels = command([
        'ffmpeg', '-nostdin', '-hide_banner', '-i', output, '-vn',
        '-af', 'volumedetect', '-f', 'null', '-',
    ], timeout=max(120, int(actual * 10)))
    return {
        'status': 'technical_checks_passed', 'path': str(output.relative_to(project)),
        'sha256': digest(output), 'duration': actual,
        'audioDuration': audio_duration, 'probe': info,
        'audioLevels': [line for line in levels.stderr.splitlines()
                        if 'mean_volume:' in line or 'max_volume:' in line],
        'frames': ['qa/first.png', 'qa/middle.png', 'qa/last.png'],
        'visualReview': 'pending', 'speechContentReview': 'pending',
    }

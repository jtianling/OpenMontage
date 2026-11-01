import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from common import command, local_path, probe, read_json, write_json
from media import MEDIA_TOOLS, import_media
from quality import verify
from render import render
from timeline import Timeline


SKILL_ROOT = Path(__file__).resolve().parent.parent


def preflight():
    required = ('ffmpeg', 'ffprobe', 'python3')
    binaries = {name: shutil.which(name) for name in required}
    missing = [name for name, path in binaries.items() if not path]
    if missing:
        raise RuntimeError('Missing preinstalled commands: ' + ', '.join(missing))
    result = command(['ffmpeg', '-hide_banner', '-encoders'])
    encoders = {line.split()[1] for line in result.stdout.splitlines()
                if len(line.split()) >= 2}
    if not {'libx264', 'aac'} <= encoders:
        raise RuntimeError('FFmpeg requires libx264 and AAC encoders.')
    return {
        'status': 'local_runtime_ready', 'binaries': binaries,
        'mediaTools': [tool for tool in MEDIA_TOOLS if tool != 'user'],
        'mediaToolAvailability': 'Inspect the current conversation tool schemas.',
        'remotionInitializer': shutil.which('monkeys-video-init'),
        'note': 'Dependency check only. Generation, render and QA remain unverified.',
    }


def project_path(workspace, name, *, exists=True):
    project = local_path(workspace, name, exists=exists)
    if project == workspace or project.is_relative_to(SKILL_ROOT):
        raise ValueError('Use a project subdirectory outside the skill installation.')
    if exists and not project.is_dir():
        raise ValueError('Project must be a directory.')
    return project


def run(args):
    workspace = Path(args.workspace).resolve(strict=True)
    if args.command == 'preflight':
        return preflight()
    if args.command == 'probe':
        return probe(local_path(workspace, args.file, exists=True))
    project = project_path(workspace, args.project, exists=args.command != 'init')
    if args.command == 'init':
        project.mkdir(parents=True, exist_ok=False)
        (project / 'assets').mkdir()
        write_json(project / 'assets.json', {'version': 1, 'assets': []})
        return {'project': str(project.relative_to(workspace))}
    if args.command == 'import-media':
        receipt = read_json(local_path(workspace, args.receipt, exists=True))
        return import_media(workspace, project, receipt)
    timeline = Timeline.parse(read_json(local_path(project, args.timeline, exists=True)))
    if args.command == 'render':
        output = render(project, timeline, args.output)
    else:
        output = local_path(project, args.output, exists=True)
    report = verify(project, output, timeline)
    write_json(local_path(project, 'qa/report.json'), report)
    return report


def parser():
    result = argparse.ArgumentParser(description='OpenMontage local production tools.')
    result.add_argument('--workspace', default='.')
    commands = result.add_subparsers(dest='command', required=True)
    commands.add_parser('preflight')
    init = commands.add_parser('init')
    init.add_argument('project')
    inspect = commands.add_parser('probe')
    inspect.add_argument('file')
    register = commands.add_parser('import-media')
    register.add_argument('project')
    register.add_argument('--receipt', required=True)
    for name in ('render', 'verify'):
        action = commands.add_parser(name)
        action.add_argument('project')
        action.add_argument('--timeline', default='timeline.json')
        action.add_argument('--output', default='renders/final.mp4')
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(run(parser().parse_args()), ensure_ascii=False, allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError, RuntimeError,
            subprocess.SubprocessError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        raise SystemExit(1) from exc

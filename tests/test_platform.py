import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / 'skills/openmontage/scripts/openmontage.py'
sys.path.insert(0, str(SCRIPT.parent))

from common import digest, read_json
from media import MediaReceipt
from timeline import Timeline


class InputTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_remotion_rejects_dangling_output_symlink_before_launch(self):
        with tempfile.TemporaryDirectory() as workspace:
            project = Path(workspace) / 'motion'
            project.mkdir()
            outside = Path(workspace) / 'escaped.mp4'
            (project / 'output.mp4').symlink_to(outside)
            result = subprocess.run([
                'node', str(SCRIPT.parent / 'remotion.mjs'),
                'render', 'motion', 'Explainer', 'output.mp4',
            ], cwd=workspace, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Output already exists', result.stderr)
            self.assertFalse(outside.exists())

    def test_receipts_reject_pending_unknown_tools_and_extra_fields(self):
        receipt = {
            'id': 'image', 'tool': 'image_generate',
            'status': 'completed', 'localPath': 'image.png',
        }
        for change in (
            {'status': 'pending'}, {'tool': 'vendor-image'},
            {'id': '../escape'}, {'localPath': ''}, {'token': 'unexpected'},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                MediaReceipt.parse({**receipt, **change})

    def test_timeline_rejects_invalid_and_ambiguous_inputs(self):
        baseline = {
            'width': 320, 'height': 180, 'fps': 24,
            'clips': [{'asset': 'image', 'duration': 1}],
        }
        for change in (
            {'width': True}, {'width': 321}, {'fps': 0}, {'fps': 24.5},
            {'clips': []}, {'clips': [{'asset': 'image', 'duration': float('nan')}]},
            {'audio': [{'asset': 'voice', 'start': 1}]}, {'extra': 'field'},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                Timeline.parse({**baseline, **change})

    def test_duplicate_json_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'
            path.write_text('{"status":"pending","status":"completed"}')
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
                read_json(path)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class MediaFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='openmontage-test-')
        cls.workspace = Path(cls.temporary.name).resolve()
        cls.generate(['-f', 'lavfi', '-i', 'color=red:s=320x180',
                      '-frames:v', '1', str(cls.workspace / 'image.png')])
        cls.generate(['-f', 'lavfi', '-i', 'color=blue:s=320x180:r=24:d=1',
                      '-f', 'lavfi', '-i', 'sine=frequency=660:duration=1',
                      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                      '-shortest', str(cls.workspace / 'video.mp4')])
        for name, frequency, length in [('voice', 440, 1), ('music', 220, 0.4)]:
            cls.generate(['-f', 'lavfi', '-i',
                          f'sine=frequency={frequency}:duration={length}',
                          str(cls.workspace / f'{name}.wav')])

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @classmethod
    def generate(cls, arguments):
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', *arguments],
                       capture_output=True, check=True, timeout=30)

    def cli(self, *args, expected=0):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), '--workspace', str(self.workspace), *args],
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout if expected == 0 else result.stderr)

    def new_project(self):
        name = f'project-{self._testMethodName}'
        self.cli('init', name)
        return name, self.workspace / name

    def receipt(self, name, tool, source):
        path = self.workspace / f'{name}-receipt.json'
        path.write_text(json.dumps({
            'id': name, 'tool': tool, 'status': 'completed', 'localPath': source,
        }))
        return path.name

    def test_four_media_types_render_with_separate_audio_verification(self):
        name, project = self.new_project()
        for asset, tool, source in (
            ('opening', 'image_generate', 'image.png'),
            ('scene-two', 'video_generate', 'video.mp4'),
            ('voice-one', 'text_to_speech', 'voice.wav'),
            ('music', 'music_generate', 'music.wav'),
        ):
            receipt = self.receipt(asset, tool, source)
            result = self.cli('import-media', name, '--receipt', receipt)
            self.assertEqual(result['tool'], tool)
            self.assertEqual(result['sha256'], digest(self.workspace / source))
        timeline = {
            'width': 320, 'height': 180, 'fps': 24,
            'clips': [{'asset': 'opening', 'duration': 1},
                      {'asset': 'scene-two', 'duration': 1, 'mute': True}],
            'audio': [{'asset': 'voice-one'},
                      {'asset': 'music', 'volume': 0.2, 'loop': True}],
        }
        (project / 'timeline.json').write_text(json.dumps(timeline))
        report = self.cli('render', name)
        self.assertEqual(report['status'], 'technical_checks_passed')
        self.assertAlmostEqual(report['duration'], 2, delta=0.1)
        self.assertAlmostEqual(report['audioDuration'], 2, delta=0.1)
        self.assertEqual(report['visualReview'], 'pending')
        output = project / report['path']
        self.assertEqual(report['sha256'], digest(output))
        for frame in report['frames']:
            self.assertGreater((project / frame).stat().st_size, 0)
        self.assertTrue(any('max_volume:' in value for value in report['audioLevels']))
        self.assert_picture_color(output, 0.2, 'red')
        self.assert_picture_color(output, 1.4, 'blue')
        self.assert_audio_signal(output, 0.2)
        self.assert_audio_signal(output, 1.4)
        refusal = self.cli('render', name, expected=1)
        self.assertIn('new MP4', refusal['error'])

    def assert_picture_color(self, output, timestamp, color):
        result = subprocess.run([
            'ffmpeg', '-v', 'error', '-ss', str(timestamp), '-i', str(output),
            '-frames:v', '1', '-vf', 'scale=1:1', '-pix_fmt', 'rgb24',
            '-f', 'rawvideo', '-',
        ], capture_output=True, check=True, timeout=30)
        red, _, blue = result.stdout[:3]
        self.assertGreater(red if color == 'red' else blue,
                           (blue if color == 'red' else red) + 100)

    def assert_audio_signal(self, output, timestamp):
        result = subprocess.run([
            'ffmpeg', '-v', 'error', '-ss', str(timestamp), '-i', str(output),
            '-t', '0.1', '-vn', '-ac', '1', '-f', 's16le', '-',
        ], capture_output=True, check=True, timeout=30)
        self.assertGreater(len(result.stdout), 100)
        self.assertNotEqual(set(result.stdout), {0})

    def test_pending_or_wrong_media_has_no_project_side_effect(self):
        name, project = self.new_project()
        receipt = self.workspace / 'pending.json'
        receipt.write_text(json.dumps({
            'id': 'pending', 'tool': 'video_generate',
            'status': 'pending', 'localPath': 'not-created.mp4',
        }))
        self.cli('import-media', name, '--receipt', receipt.name, expected=1)
        wrong = self.receipt('wrong', 'image_generate', 'voice.wav')
        self.cli('import-media', name, '--receipt', wrong, expected=1)
        self.assertEqual(read_json(project / 'assets.json')['assets'], [])
        self.assertEqual(list((project / 'assets').iterdir()), [])

    def test_paths_and_changed_assets_are_rejected(self):
        name, project = self.new_project()
        receipt = self.receipt('original', 'image_generate', 'image.png')
        self.cli('import-media', name, '--receipt', receipt)
        (project / 'assets/original.png').write_bytes(b'changed')
        timeline = {'width': 320, 'height': 180, 'fps': 24,
                    'clips': [{'asset': 'original', 'duration': 1}]}
        (project / 'timeline.json').write_text(json.dumps(timeline))
        error = self.cli('render', name, expected=1)
        self.assertIn('changed', error['error'])
        self.cli('probe', '../outside.mp4', expected=1)
        with tempfile.TemporaryDirectory() as outside:
            (self.workspace / 'outside-link').symlink_to(outside, target_is_directory=True)
            self.cli('init', 'outside-link/project', expected=1)
        self.assertFalse((project / 'renders').exists())

    def test_overlong_source_and_output_escape_fail_before_render(self):
        name, project = self.new_project()
        self.cli('import-media', name, '--receipt',
                 self.receipt('video', 'video_generate', 'video.mp4'))
        timeline = {'width': 320, 'height': 180, 'fps': 24,
                    'clips': [{'asset': 'video', 'duration': 3}]}
        (project / 'timeline.json').write_text(json.dumps(timeline))
        self.assertIn('source duration', self.cli('render', name, expected=1)['error'])
        timeline['clips'][0]['duration'] = 1
        (project / 'timeline.json').write_text(json.dumps(timeline))
        self.assertIn('outside', self.cli(
            'render', name, '--output', '../escape.mp4', expected=1,
        )['error'])

    def test_music_with_cover_art_is_imported_as_audio(self):
        name, _ = self.new_project()
        cover = self.workspace / 'cover-art.mp3'
        self.generate([
            '-i', str(self.workspace / 'music.wav'),
            '-i', str(self.workspace / 'image.png'), '-map', '0:a', '-map', '1:v',
            '-c:a', 'libmp3lame', '-c:v', 'png', '-disposition:v', 'attached_pic',
            '-id3v2_version', '3', str(cover),
        ])
        result = self.cli('import-media', name, '--receipt',
                          self.receipt('cover-art', 'music_generate', cover.name))
        self.assertEqual(result['type'], 'audio')

    def test_short_original_audio_does_not_truncate_narration(self):
        name, project = self.new_project()
        source = self.workspace / 'short-original-audio.mp4'
        self.generate([
            '-f', 'lavfi', '-i', 'color=blue:s=320x180:r=24:d=2',
            '-i', str(self.workspace / 'voice.wav'),
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source),
        ])
        narration = self.workspace / 'full-narration.wav'
        self.generate(['-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
                       str(narration)])
        for asset, tool, file in (
            ('short-original', 'video_generate', source.name),
            ('full-narration', 'text_to_speech', narration.name),
        ):
            self.cli('import-media', name, '--receipt', self.receipt(asset, tool, file))
        timeline = {
            'width': 320, 'height': 180, 'fps': 24,
            'clips': [{'asset': 'short-original', 'duration': 2}],
            'audio': [{'asset': 'full-narration'}],
        }
        (project / 'timeline.json').write_text(json.dumps(timeline))
        report = self.cli('render', name)
        self.assertAlmostEqual(report['audioDuration'], 2, delta=0.1)
        self.assert_audio_signal(project / report['path'], 1.7)

    def test_gif_input_can_render(self):
        name, project = self.new_project()
        gif = self.workspace / 'image.gif'
        self.generate(['-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=10:d=0.3',
                       str(gif)])
        self.cli('import-media', name, '--receipt',
                 self.receipt('gif', 'image_generate', gif.name))
        timeline = {'width': 320, 'height': 180, 'fps': 24,
                    'clips': [{'asset': 'gif', 'duration': 1}]}
        (project / 'timeline.json').write_text(json.dumps(timeline))
        self.assertEqual(self.cli('render', name)['status'], 'technical_checks_passed')

    def test_long_audio_cannot_hide_short_video_stream(self):
        name, project = self.new_project()
        source = self.workspace / 'short-video-stream.mp4'
        self.generate([
            '-f', 'lavfi', '-i', 'color=blue:s=320x180:r=24:d=1',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source),
        ])
        self.cli('import-media', name, '--receipt',
                 self.receipt('short-video', 'video_generate', source.name))
        timeline = {'width': 320, 'height': 180, 'fps': 24,
                    'clips': [{'asset': 'short-video', 'duration': 2}]}
        (project / 'timeline.json').write_text(json.dumps(timeline))
        error = self.cli('render', name, expected=1)
        self.assertIn('source duration', error['error'])
        self.assertFalse((project / 'renders').exists())

    def test_webm_stream_duration_tags_are_supported(self):
        name, project = self.new_project()
        source = self.workspace / 'tagged-video.webm'
        self.generate(['-f', 'lavfi', '-i', 'color=blue:s=320x180:r=24:d=1',
                       '-c:v', 'libvpx-vp9', str(source)])
        self.cli('import-media', name, '--receipt',
                 self.receipt('webm', 'video_generate', source.name))
        timeline = {'width': 320, 'height': 180, 'fps': 24,
                    'clips': [{'asset': 'webm', 'duration': 1}]}
        (project / 'timeline.json').write_text(json.dumps(timeline))
        report = self.cli('render', name)
        self.assertAlmostEqual(report['duration'], 1, delta=0.1)


if __name__ == '__main__':
    unittest.main()

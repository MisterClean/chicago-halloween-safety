"""Small checks for the standalone build and source-only publishing guard."""
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = spec_from_file_location(name, ROOT / f'scripts/{name}.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StandaloneBuildTests(unittest.TestCase):
    def test_export_excludes_raw_records_and_preserves_local_config(self):
        build = load_script('build_web')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts = root / 'packages/data/processed'
            page = root / 'apps/web/public'
            raw = root / '.cache/halloween'
            for directory in [artifacts, page, raw]:
                directory.mkdir(parents=True)
            for name in build.FILES:
                (artifacts / name).write_text('{}\n', encoding='utf-8')
            (raw / 'people.csv').write_text('private raw fixture\n', encoding='utf-8')
            (page / 'config.local.js').write_text('custom local configuration\n', encoding='utf-8')
            with patch.object(build, 'ROOT', root), patch.object(sys, 'argv', ['build_web.py', '--dist']):
                build.main()
            export = root / 'apps/web/dist'
            self.assertFalse((export / 'people.csv').exists())
            self.assertFalse((export / '.cache').exists())
            self.assertEqual((page / 'config.local.js').read_text(encoding='utf-8'), 'custom local configuration\n')
            manifest = json.loads((export / 'data/halloween/manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(set(manifest['files']), set(build.FILES))
            for entry in manifest['files'].values():
                self.assertTrue((export / entry['url']).is_file())

    def test_guard_reads_staged_bytes_and_rejects_data(self):
        guard = load_script('check_public_files')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            (root / 'README.md').write_text('safe\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'README.md'], cwd=root, check=True)
            with patch.object(guard, 'ROOT', root):
                guard.main()
            # An unsafe staged version remains unsafe even if the working file is cleaned.
            (root / 'README.md').write_text('/' + 'Users' + '/example/local-file\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'README.md'], cwd=root, check=True)
            (root / 'README.md').write_text('safe working copy\n', encoding='utf-8')
            with patch.object(guard, 'ROOT', root), self.assertRaises(SystemExit):
                guard.main()
            subprocess.run(['git', 'add', 'README.md'], cwd=root, check=True)
            (root / 'records.csv').write_text('data\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'records.csv'], cwd=root, check=True)
            with patch.object(guard, 'ROOT', root), self.assertRaises(SystemExit):
                guard.main()


if __name__ == '__main__':
    unittest.main()

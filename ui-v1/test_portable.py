"""Exercise public checkout layout without copying private or backend files."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from adapter import default_release


class PortableTests(unittest.TestCase):
    def test_public_layout_from_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory(prefix='dataquery-ui-') as scratch:
            root = Path(scratch)
            ui = root / 'ui-v1'
            release = root / 'releases/nl-v3-93'
            ui.mkdir()
            (release / 'evaluation').mkdir(parents=True)
            shutil.copyfile(Path(__file__).with_name('adapter.py'), ui / 'adapter.py')
            source = default_release()
            for relative in ('MANIFEST.json', 'evaluation/decisions.json', 'evaluation/backend_results.json'):
                shutil.copyfile(source / relative, release / relative)
            script = "import sys,json; sys.path.insert(0,sys.argv[1]); from adapter import SavedCases; s=SavedCases(); print(json.dumps({'count':len(s.catalog()),'mode':s.open('STA001')['mode']}))"
            result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', script, str(ui)],
                                    cwd=root, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), {'count':100, 'mode':'saved'})


if __name__ == '__main__':
    unittest.main()

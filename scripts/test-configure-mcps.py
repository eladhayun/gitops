"""Exercise real installer runs without contacting services or using private tokens."""
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

INSTALLER = Path(__file__).with_name('configure-mcps.py')

class TivTaamNamingTests(unittest.TestCase):
    def install(self, path, *args, success=True):
        result = subprocess.run([sys.executable, str(INSTALLER), '--config', str(path), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return tomllib.loads(path.read_text())

    def test_legacy_migration_and_default_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text('model = "keep-model"\n[mcp_servers.other]\ncommand = "keep-command"\n[mcp_servers.tivtaam-mcp]\nurl = "http://legacy.test/mcp"\nenabled_tools = ["get_status"]\ntool_timeout_sec = 480\n')
            for _ in range(2):
                data = self.install(path)
                self.assertNotIn('tivtaam-mcp', data['mcp_servers'])
                entry = data['mcp_servers']['tivtaam']
                self.assertEqual(entry['enabled_tools'], ['get_status'])
                self.assertEqual(entry['tool_timeout_sec'], 480)
                self.assertTrue(entry['http_headers_helper'].endswith(' tivtaam'))
                self.assertEqual(entry['url'], 'http://tivtaam-mcp.tivtaam-mcp.svc.cluster.local:8081/mcp')
                self.assertEqual(data['model'], 'keep-model')
                self.assertEqual(data['mcp_servers']['other'], {'command': 'keep-command'})

    def test_named_install_preserves_disabled_state_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text('[mcp_servers.tivtaam]\nurl = "http://current.test/mcp"\nenabled = false\ndisabled_tools = ["write"]\n')
            first = self.install(path, '--server', 'tivtaam')
            self.assertEqual(self.install(path, '--server', 'tivtaam'), first)
            self.assertFalse(first['mcp_servers']['tivtaam']['enabled'])
            self.assertEqual(first['mcp_servers']['tivtaam']['disabled_tools'], ['write'])
            self.assertNotIn('tivtaam-mcp', first['mcp_servers'])

    def test_conflicting_names_do_not_modify_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            original = '[mcp_servers.tivtaam]\nurl = "http://one.test/mcp"\n[mcp_servers.tivtaam-mcp]\nurl = "http://two.test/mcp"\n'
            path.write_text(original)
            self.install(path, '--server', 'tivtaam', success=False)
            self.assertEqual(path.read_text(), original)

if __name__ == '__main__':
    unittest.main()

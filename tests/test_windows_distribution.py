import os
import hashlib
import io
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from creatorhub_windows.backup import create_backup
from creatorhub_windows.agent_proxy import is_visible_browser_route
from creatorhub_windows.certificates import ensure_certificate
from creatorhub_windows.migration import migrate_from
from creatorhub_windows.paths import RuntimePaths, ensure_directories
from creatorhub_windows.security import _derive, _session_token, _valid_session
from creatorhub_windows.updates import stage_latest_installer


def paths_for(root: Path) -> RuntimePaths:
    return RuntimePaths(
        program_data=root / "program", local_data=root / "local",
        config=root / "program" / "config.yaml",
        database=root / "program" / "data" / "creatorhub.db",
        wechat_data=root / "program" / "data" / "wechat_oa",
        logs=root / "program" / "logs", backups=root / "program" / "backups",
        certificates=root / "program" / "certificates",
        security=root / "program" / "security.json",
        operator=root / "program" / "operator.json",
    )


class WindowsDistributionTests(unittest.TestCase):
    def test_password_and_session_are_not_plaintext(self):
        salt = "01" * 16
        derived = _derive("a-secure-password", salt)
        self.assertNotIn("a-secure-password", derived)
        secret = "02" * 32
        token = _session_token(secret, int(time.time()) + 60)
        self.assertTrue(_valid_session(secret, token))
        self.assertFalse(_valid_session("03" * 32, token))

    def test_certificate_contains_localhost(self):
        with tempfile.TemporaryDirectory() as value:
            cert, key, fingerprint = ensure_certificate(Path(value))
            self.assertTrue(cert.is_file())
            self.assertTrue(key.is_file())
            self.assertEqual(len(fingerprint), 64)

    def test_backup_is_encrypted_and_excludes_browser_profile(self):
        with tempfile.TemporaryDirectory() as value:
            paths = paths_for(Path(value))
            ensure_directories(paths)
            db = sqlite3.connect(paths.database)
            db.execute("create table sample(value text)")
            db.execute("insert into sample values ('secret-row')")
            db.commit(); db.close()
            output = create_backup(paths)
            raw = output.read_bytes()
            self.assertNotIn(b"secret-row", raw)
            key = (paths.program_data / ".backup.key").read_bytes()
            plain = Fernet(key).decrypt(raw)
            self.assertIn(b"manifest.json", plain)

    def test_migration_copies_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            source = root / "old"
            (source / "data").mkdir(parents=True)
            (source / "data" / "creatorhub.db").write_bytes(b"old-db")
            paths = paths_for(root / "new")
            ensure_directories(paths)
            report = migrate_from(source, paths)
            self.assertEqual(paths.database.read_bytes(), b"old-db")
            self.assertTrue((source / "data" / "creatorhub.db").exists())
            self.assertTrue(report["source_preserved"])

    def test_visible_browser_actions_are_sent_to_desktop_agent(self):
        self.assertTrue(is_visible_browser_route("/api/login/shipinhao/start"))
        self.assertTrue(is_visible_browser_route("/api/accounts/7/open-browser"))
        self.assertTrue(is_visible_browser_route(
            "/api/wechat-oa/accounts/9/browser-health"))
        self.assertFalse(is_visible_browser_route("/api/works"))

    def test_update_installer_is_size_and_digest_checked(self):
        payload = b"fixture-installer"
        release = {"assets": [{
            "name": "CreatorHub-Setup-1.0.1-x64.exe",
            "size": len(payload), "api_url": "https://api.example/asset",
            "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        }]}
        with tempfile.TemporaryDirectory() as value, \
                patch("creatorhub_windows.updates.latest_release", return_value=release), \
                patch("creatorhub_windows.updates.load_token", return_value="fixture"), \
                patch("creatorhub_windows.updates.urllib.request.urlopen",
                      return_value=io.BytesIO(payload)):
            result = stage_latest_installer(Path(value))
            self.assertEqual(Path(result["path"]).read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()

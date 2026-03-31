from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import tkinter as tk
import unittest
from urllib.error import URLError
from unittest.mock import patch

from Hidrostatik_Test_Chat import HydrostaticTestApp
from app_metadata import APP_VERSION
from updater import ReleaseAsset, UpdateInfo, _download_asset, fetch_latest_update_info

NEXT_TEST_VERSION = f"{int(APP_VERSION.split('.', 1)[0]) + 1}.0.0"


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self, *_args, **_kwargs) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class UpdaterTests(unittest.TestCase):
    def test_fetch_latest_update_info_filters_project_specific_releases(self) -> None:
        payload = [
            {
                "tag_name": "other-app-v9.9.9",
                "draft": False,
                "prerelease": False,
                "assets": [{"name": "OtherApp-v9.9.9-windows-x64.zip", "browser_download_url": "https://example.com/other.zip", "size": 11}],
                "html_url": "https://example.com/other",
                "body": "other",
                "published_at": "2026-03-01T12:00:00Z",
            },
            {
                "tag_name": f"hidrostatik-test-v{NEXT_TEST_VERSION}",
                "draft": False,
                "prerelease": False,
                "assets": [{"name": f"HidrostatikTest-v{NEXT_TEST_VERSION}-windows-x64.zip", "browser_download_url": "https://example.com/app.zip", "size": 42}],
                "html_url": "https://example.com/app",
                "body": "notes",
                "published_at": "2026-03-30T12:00:00Z",
            },
        ]

        with patch("updater.urlopen", return_value=_FakeResponse(payload)):
            info = fetch_latest_update_info()

        self.assertEqual(info.latest_version, NEXT_TEST_VERSION)
        self.assertTrue(info.update_available)
        self.assertIsNotNone(info.asset)
        self.assertEqual(info.asset.name, f"HidrostatikTest-v{NEXT_TEST_VERSION}-windows-x64.zip")

    def test_fetch_latest_update_info_marks_current_version_up_to_date(self) -> None:
        payload = [
            {
                "tag_name": f"hidrostatik-test-v{APP_VERSION}",
                "draft": False,
                "prerelease": False,
                "assets": [],
                "html_url": "https://example.com/current",
                "body": "notes",
                "published_at": "2026-03-30T12:00:00Z",
            }
        ]

        with patch("updater.urlopen", return_value=_FakeResponse(payload)):
            info = fetch_latest_update_info()

        self.assertEqual(info.latest_version, APP_VERSION)
        self.assertFalse(info.update_available)

    def test_fetch_latest_update_info_falls_back_to_powershell_when_python_tls_fails(self) -> None:
        payload = [
            {
                "tag_name": f"hidrostatik-test-v{NEXT_TEST_VERSION}",
                "draft": False,
                "prerelease": False,
                "assets": [{"name": f"HidrostatikTest-v{NEXT_TEST_VERSION}-windows-x64.zip", "browser_download_url": "https://example.com/app.zip", "size": 42}],
                "html_url": "https://example.com/app",
                "body": "notes",
                "published_at": "2026-03-30T12:00:00Z",
            }
        ]
        powershell_result = subprocess.CompletedProcess(
            args=["powershell"],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

        with patch("updater.urlopen", side_effect=URLError("tls failure")), patch(
            "updater.subprocess.run",
            return_value=powershell_result,
        ):
            info = fetch_latest_update_info()

        self.assertEqual(info.latest_version, NEXT_TEST_VERSION)
        self.assertTrue(info.update_available)

    def test_download_asset_falls_back_to_powershell_when_python_tls_fails(self) -> None:
        asset = ReleaseAsset(
            name=f"HidrostatikTest-v{NEXT_TEST_VERSION}-windows-x64.zip",
            download_url="https://example.com/app.zip",
            size=42,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / asset.name

            def fake_powershell_download(url: str, headers: dict[str, str], target: Path, timeout: int) -> None:
                self.assertEqual(url, asset.download_url)
                self.assertIn("User-Agent", headers)
                self.assertEqual(timeout, 10)
                target.write_bytes(b"zip-data")

            with patch("updater.urlopen", side_effect=URLError("tls failure")), patch(
                "updater._download_via_powershell",
                side_effect=fake_powershell_download,
            ):
                _download_asset(asset, target_path, 10)

            self.assertTrue(target_path.exists())
            self.assertEqual(target_path.read_bytes(), b"zip-data")


class UpdateUiTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk kullanilamiyor: {exc}")
        self.root.withdraw()
        self.app = HydrostaticTestApp(self.root)

    def tearDown(self) -> None:
        self.root.destroy()

    def test_update_result_marks_current_build_as_up_to_date(self) -> None:
        info = UpdateInfo(
            current_version=APP_VERSION,
            latest_version=APP_VERSION,
            tag_name=f"hidrostatik-test-v{APP_VERSION}",
            html_url="https://example.com/current",
            body="notes",
            published_at="2026-03-30T12:00:00Z",
            asset=None,
            update_available=False,
        )

        with patch("Hidrostatik_Test_Chat.messagebox.showinfo") as mocked_showinfo:
            self.app._handle_update_check_result(info, user_requested=True)

        self.assertIn("Guncel surum", self.app.update_status_var.get())
        self.assertIn("daha yeni bir release bulunmadi", self.app.update_detail_var.get())
        mocked_showinfo.assert_called_once()

    def test_update_result_marks_new_release_as_available(self) -> None:
        info = UpdateInfo(
            current_version=APP_VERSION,
            latest_version=NEXT_TEST_VERSION,
            tag_name=f"hidrostatik-test-v{NEXT_TEST_VERSION}",
            html_url="https://example.com/update",
            body="notes",
            published_at="2026-03-30T12:00:00Z",
            asset=ReleaseAsset(
                name=f"HidrostatikTest-v{NEXT_TEST_VERSION}-windows-x64.zip",
                download_url="https://example.com/update.zip",
                size=1024,
            ),
            update_available=True,
        )

        self.app._handle_update_check_result(info, user_requested=True)

        self.assertIn("Yeni surum bulundu", self.app.update_status_var.get())
        self.assertIn(f"HidrostatikTest-v{NEXT_TEST_VERSION}-windows-x64.zip", self.app.update_detail_var.get())


if __name__ == "__main__":
    unittest.main()

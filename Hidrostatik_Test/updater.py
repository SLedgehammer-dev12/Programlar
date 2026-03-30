from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import webbrowser
import zipfile

from app_metadata import (
    APP_VERSION,
    BINARY_NAME,
    GITHUB_OWNER,
    GITHUB_REPO,
    RELEASES_API_URL,
    RELEASES_PAGE_URL,
    RELEASE_ASSET_TEMPLATE,
    RELEASE_TAG_PREFIX,
)

DEFAULT_TIMEOUT_SECONDS = 10


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    tag_name: str
    html_url: str
    body: str
    published_at: str
    asset: ReleaseAsset | None
    update_available: bool


@dataclass(frozen=True)
class RuntimeContext:
    frozen: bool
    can_self_update: bool
    executable_path: Path
    install_dir: Path


def _version_key(version: str) -> tuple[int, ...]:
    parts = version.strip().split(".")
    numeric_parts: list[int] = []
    for part in parts:
        digits = "".join(ch for ch in part if ch.isdigit())
        numeric_parts.append(int(digits) if digits else 0)
    while len(numeric_parts) < 3:
        numeric_parts.append(0)
    return tuple(numeric_parts)


def _version_from_tag(tag_name: str) -> str:
    normalized = tag_name.strip()
    if normalized.startswith(RELEASE_TAG_PREFIX):
        return normalized[len(RELEASE_TAG_PREFIX) :]
    if normalized.startswith("v"):
        return normalized[1:]
    return normalized


def _matches_project_release(release: dict[str, Any]) -> bool:
    tag_name = str(release.get("tag_name", ""))
    if tag_name.startswith(RELEASE_TAG_PREFIX):
        return True
    asset_template_prefix = RELEASE_ASSET_TEMPLATE.split("{version}", 1)[0]
    for asset in release.get("assets", []):
        asset_name = str(asset.get("name", ""))
        if asset_name.startswith(asset_template_prefix) and asset_name.endswith(".zip"):
            return True
    return False


def _extract_asset(release: dict[str, Any], version: str) -> ReleaseAsset | None:
    expected_name = RELEASE_ASSET_TEMPLATE.format(version=version)
    fallback_asset: ReleaseAsset | None = None
    for asset in release.get("assets", []):
        asset_name = str(asset.get("name", ""))
        if not asset_name.lower().endswith(".zip"):
            continue
        release_asset = ReleaseAsset(
            name=asset_name,
            download_url=str(asset.get("browser_download_url", "")),
            size=int(asset.get("size", 0) or 0),
        )
        if asset_name == expected_name:
            return release_asset
        if fallback_asset is None:
            fallback_asset = release_asset
    return fallback_asset


def _select_latest_release(releases: list[dict[str, Any]]) -> dict[str, Any]:
    matching_releases = [
        release
        for release in releases
        if not release.get("draft")
        and not release.get("prerelease")
        and _matches_project_release(release)
    ]
    if not matching_releases:
        raise UpdateError(
            f"{GITHUB_OWNER}/{GITHUB_REPO} icinde bu uygulamaya ait yayin bulunamadi."
        )
    matching_releases.sort(
        key=lambda release: _version_key(_version_from_tag(str(release.get("tag_name", "")))),
        reverse=True,
    )
    return matching_releases[0]


def fetch_latest_update_info(timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> UpdateInfo:
    request = Request(
        RELEASES_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{BINARY_NAME}-updater/{APP_VERSION}",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise UpdateError(f"GitHub release bilgisi okunamadi: HTTP {exc.code}") from exc
    except URLError as exc:
        raise UpdateError("GitHub release servisine ulasilamadi.") from exc
    except json.JSONDecodeError as exc:
        raise UpdateError("GitHub release cevabi okunamadi.") from exc

    if not isinstance(payload, list):
        raise UpdateError("GitHub release cevabi beklenen list formatinda degil.")

    release = _select_latest_release(payload)
    latest_version = _version_from_tag(str(release.get("tag_name", "")))
    latest_asset = _extract_asset(release, latest_version)
    return UpdateInfo(
        current_version=APP_VERSION,
        latest_version=latest_version,
        tag_name=str(release.get("tag_name", "")),
        html_url=str(release.get("html_url", RELEASES_PAGE_URL)),
        body=str(release.get("body", "")),
        published_at=str(release.get("published_at", "")),
        asset=latest_asset,
        update_available=_version_key(latest_version) > _version_key(APP_VERSION),
    )


def get_runtime_context() -> RuntimeContext:
    frozen = bool(getattr(sys, "frozen", False))
    executable_path = Path(sys.executable if frozen else __file__).resolve()
    install_dir = executable_path.parent if frozen else Path(__file__).resolve().parent
    can_self_update = frozen and sys.platform.startswith("win") and executable_path.suffix.lower() == ".exe"
    return RuntimeContext(
        frozen=frozen,
        can_self_update=can_self_update,
        executable_path=executable_path,
        install_dir=install_dir,
    )


def open_release_page(url: str | None = None) -> None:
    webbrowser.open(url or RELEASES_PAGE_URL)


def _download_asset(asset: ReleaseAsset, target_path: Path, timeout_seconds: int) -> None:
    request = Request(
        asset.download_url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": f"{BINARY_NAME}-updater/{APP_VERSION}",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response, target_path.open("wb") as output:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                output.write(chunk)
    except HTTPError as exc:
        raise UpdateError(f"Release paketi indirilemedi: HTTP {exc.code}") from exc
    except URLError as exc:
        raise UpdateError("Release paketi indirilemedi.") from exc


def _find_extracted_app_dir(extract_root: Path) -> Path:
    expected_dir = extract_root / BINARY_NAME
    if expected_dir.exists():
        return expected_dir
    directories = [path for path in extract_root.iterdir() if path.is_dir()]
    if len(directories) == 1:
        return directories[0]
    raise UpdateError("Indirilen paket beklenen uygulama klasorunu icermiyor.")


def _write_update_script(
    working_root: Path,
    stage_dir: Path,
    install_dir: Path,
    executable_path: Path,
    current_pid: int,
) -> Path:
    script_path = working_root / "apply_update.cmd"
    script = f"""@echo off
setlocal
set "APP_PID={current_pid}"
set "STAGE_DIR={stage_dir}"
set "TARGET_DIR={install_dir}"
set "EXE_PATH={executable_path}"

for /L %%I in (1,1,120) do (
    tasklist /FI "PID eq %APP_PID%" | find "%APP_PID%" >nul
    if errorlevel 1 goto apply_update
    timeout /t 1 /nobreak >nul
)

:apply_update
robocopy "%STAGE_DIR%\\{BINARY_NAME}" "%TARGET_DIR%" /E /R:2 /W:1 /NFL /NDL /NP >nul
start "" "%EXE_PATH%"
rmdir /S /Q "%STAGE_DIR%"
del "%~f0"
"""
    script_path.write_text(script, encoding="utf-8", newline="\r\n")
    return script_path


def install_update(update_info: UpdateInfo, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    if not update_info.update_available:
        return "up_to_date"

    if update_info.asset is None:
        open_release_page(update_info.html_url)
        return "browser"

    runtime = get_runtime_context()
    if not runtime.can_self_update:
        open_release_page(update_info.html_url)
        return "browser"

    working_root = Path(tempfile.mkdtemp(prefix="hidrostatik-update-"))
    zip_path = working_root / update_info.asset.name
    extract_root = working_root / "extract"
    extract_root.mkdir(parents=True, exist_ok=True)

    _download_asset(update_info.asset, zip_path, timeout_seconds)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_root)

    extracted_app_dir = _find_extracted_app_dir(extract_root)
    stage_root = working_root / "stage"
    stage_root.mkdir(parents=True, exist_ok=True)
    staged_app_dir = stage_root / BINARY_NAME
    if staged_app_dir.exists():
        raise UpdateError("Gecici update klasoru beklenmedik sekilde dolu.")
    extracted_app_dir.rename(staged_app_dir)

    script_path = _write_update_script(
        working_root=working_root,
        stage_dir=stage_root,
        install_dir=runtime.install_dir,
        executable_path=runtime.executable_path,
        current_pid=os.getpid(),
    )
    subprocess.Popen(["cmd", "/c", "start", "", "/min", str(script_path)], close_fds=True)
    return "self_update"

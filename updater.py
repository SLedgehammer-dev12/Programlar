import os
import json
import re
import tempfile
import shutil
import zipfile
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import quote

GITHUB_API_RELEASES = "https://api.github.com/repos/{repo}/releases/latest"
GITHUB_BRANCH_ZIP = "https://github.com/{repo}/archive/refs/heads/{branch}.zip"
GITHUB_RAW_FILE = "https://raw.githubusercontent.com/{repo}/{branch}/{path}"
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _load_config(log):
    try:
        if os.path.exists(DEFAULT_CONFIG_PATH):
            with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg
    except Exception as e:
        if log:
            log(f"Güncelleme yapılandırması okunamadı: {e}", level="WARNING")
    return {
        "repo": "",
        "asset_name_regex": "(gas[-_ ]?flow[-_ ]?calc).*\\.zip",
        "update_mode": "releases",  # or "branch"
        "branch": "main",
        # Path of a file containing version string (APP_VERSION) for branch mode
        "version_source_path": "",
        "version_regex": "APP_VERSION\\s*=\\s*\"(\\d+\\.\\d+\\.\\d+)\"",
        # Sub-directory inside the zip that contains the app
        "app_subdir_in_zip": "",
        # Files/dirs to exclude when applying update
        "exclude_on_apply": ["config.json", "__pycache__", ".git", "_backups"],
        # Optional GitHub token for private repos (read from env if empty)
        "github_token": "",
    }


def _semver_tuple(v: str):
    # Extract numeric parts like 1.2.3
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", v.strip())
    if not m:
        return (0, 0, 0)
    return tuple(int(x) for x in m.groups())


class Updater:
    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.config = _load_config(self.log)
        self.repo = self.config.get("repo", "")
        self.asset_name_regex = self.config.get("asset_name_regex", "\\.zip$")
        self.update_mode = self.config.get("update_mode", "releases")
        self.branch = self.config.get("branch", "main")
        self.version_source_path = self.config.get("version_source_path", "")
        self.version_regex = self.config.get("version_regex", r"APP_VERSION\s*=\s*\"(\d+\.\d+\.\d+)\"")
        self.app_subdir_in_zip = self.config.get("app_subdir_in_zip", "")
        self.exclude_on_apply = set(self.config.get("exclude_on_apply", []))
        self.github_token = self.config.get("github_token") or os.environ.get("GITHUB_TOKEN") or ""

    def _headers(self, accept: str | None = None):
        h = {"User-Agent": "GasFlowCalc-Updater"}
        if accept:
            h["Accept"] = accept
        if self.github_token:
            h["Authorization"] = f"Bearer {self.github_token}"
        return h

    def check_for_update(self, current_version: str):
        if not self.repo:
            self.log("GitHub repo bilgisi yapılandırmada yok.", level="WARNING")
            return None

        if self.update_mode == "branch":
            if not self.version_source_path:
                self.log("Branch modu için 'version_source_path' gerekli.", level="ERROR")
                return None
            # Fetch version file from branch
            quoted_path = quote(self.version_source_path, safe="/")
            raw_url = GITHUB_RAW_FILE.format(repo=self.repo, branch=self.branch, path=quoted_path)
            try:
                req = Request(raw_url, headers=self._headers())
                with urlopen(req, timeout=10) as resp:
                    content = resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                self.log(f"Sürüm bilgisi alınamadı: {e}", level="ERROR")
                return None

            m = re.search(self.version_regex, content)
            latest_tag = m.group(1) if m else "0.0.0"
            latest = _semver_tuple(latest_tag)
            current = _semver_tuple(current_version)
            has_update = latest > current
            return {
                "has_update": has_update,
                "latest_version": latest_tag,
                "body": f"Branch: {self.branch} (dosya: {self.version_source_path})",
                "assets": [],
            }
        else:
            # Releases mode (default)
            url = GITHUB_API_RELEASES.format(repo=self.repo)
            try:
                req = Request(url, headers=self._headers("application/vnd.github+json"))
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except (URLError, HTTPError) as e:
                self.log(f"GitHub API erişim hatası: {e}", level="ERROR")
                return None
            except Exception as e:
                self.log(f"Bilinmeyen hata: {e}", level="ERROR")
                return None

            latest_tag = data.get("tag_name") or data.get("name") or "0.0.0"
            latest = _semver_tuple(latest_tag)
            current = _semver_tuple(current_version)
            has_update = latest > current
            return {
                "has_update": has_update,
                "latest_version": latest_tag,
                "body": data.get("body", ""),
                "assets": data.get("assets", []),
            }

    def download_latest_asset(self):
        # Requires prior check; choose based on mode
        if not self.repo:
            raise RuntimeError("GitHub repo yapılandırılmadı.")

        if self.update_mode == "branch":
            download_url = GITHUB_BRANCH_ZIP.format(repo=self.repo, branch=self.branch)
            filename = f"{self.repo.split('/')[-1]}-{self.branch}.zip"
            self.log(f"Branch arşivi indiriliyor: {download_url}")
            try:
                req = Request(download_url, headers=self._headers())
                with urlopen(req, timeout=60) as resp:
                    data = resp.read()
            except Exception as e:
                raise RuntimeError(f"İndirme başarısız: {e}")

            tmp_dir = os.path.join(tempfile.gettempdir(), "gas_flow_calc_updates")
            os.makedirs(tmp_dir, exist_ok=True)
            file_path = os.path.join(tmp_dir, filename)
            with open(file_path, "wb") as f:
                f.write(data)
            self.log(f"İndirme tamamlandı: {file_path}")
            return file_path
        else:
            info = self.check_for_update(current_version="0.0.0")
            if not info:
                return None
            assets = info.get("assets", [])
            pattern = re.compile(self.asset_name_regex, re.IGNORECASE)
            chosen = None
            for a in assets:
                name = a.get("name", "")
                if pattern.search(name):
                    chosen = a
                    break
            if not chosen and assets:
                chosen = assets[0]
            if not chosen:
                return None

            browser_download_url = chosen.get("browser_download_url")
            if not browser_download_url:
                return None

            self.log(f"İndirme başlıyor: {chosen.get('name')}")
            try:
                req = Request(browser_download_url, headers=self._headers())
                with urlopen(req, timeout=30) as resp:
                    data = resp.read()
            except Exception as e:
                raise RuntimeError(f"İndirme başarısız: {e}")

            tmp_dir = os.path.join(tempfile.gettempdir(), "gas_flow_calc_updates")
            os.makedirs(tmp_dir, exist_ok=True)
            file_path = os.path.join(tmp_dir, chosen.get("name"))
            with open(file_path, "wb") as f:
                f.write(data)
            self.log(f"İndirme tamamlandı: {file_path}")
            return file_path

    def apply_update_from_zip(self, zip_path: str, target_dir: str):
        if not os.path.isfile(zip_path):
            raise RuntimeError(f"Zip dosyası bulunamadı: {zip_path}")
        if not os.path.isdir(target_dir):
            raise RuntimeError(f"Hedef klasör bulunamadı: {target_dir}")

        self.log(f"Güncelleme uygulanıyor: {zip_path}")

        # 1) Extract zip to temp folder
        tmp_root = os.path.join(tempfile.gettempdir(), "gas_flow_calc_updates", "extract")
        if os.path.isdir(tmp_root):
            try:
                shutil.rmtree(tmp_root)
            except Exception:
                pass
        os.makedirs(tmp_root, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmp_root)

        # detect top-level directory inside zip
        entries = os.listdir(tmp_root)
        extracted_root = tmp_root
        if len(entries) == 1 and os.path.isdir(os.path.join(tmp_root, entries[0])):
            extracted_root = os.path.join(tmp_root, entries[0])

        # 2) Determine source directory to copy from
        source_dir = extracted_root
        if self.app_subdir_in_zip:
            cand = os.path.join(extracted_root, self.app_subdir_in_zip)
            if os.path.isdir(cand):
                source_dir = cand
            else:
                # Try tolerant path for Windows zip naming (spaces, unicode)
                self.log(f"Uyarı: app_subdir_in_zip bulunamadı: {cand}", level="WARNING")

        # 3) Backup current target directory (as sibling folder)
        parent = os.path.dirname(target_dir.rstrip("/\\"))
        base = os.path.basename(target_dir.rstrip("/\\"))
        backup_dir = os.path.join(parent, f"{base}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.log(f"Yedek oluşturuluyor: {backup_dir}")

        def ignore_patterns(src, names):
            ignored = []
            for n in names:
                if n in self.exclude_on_apply:
                    ignored.append(n)
            return set(ignored)

        shutil.copytree(target_dir, backup_dir, ignore=ignore_patterns)

        # 4) Copy new files over target_dir
        self._copy_over(source_dir, target_dir)
        self.log("Güncelleme başarıyla uygulandı. Uygulamayı yeniden başlatmanız önerilir.")
        return {"backup_dir": backup_dir}

    def _copy_over(self, src: str, dst: str):
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            target_root = os.path.join(dst, rel) if rel != os.curdir else dst
            os.makedirs(target_root, exist_ok=True)

            # filter exclusions for dirs
            dirs[:] = [d for d in dirs if d not in self.exclude_on_apply]

            for f in files:
                if f in self.exclude_on_apply:
                    continue
                s = os.path.join(root, f)
                t = os.path.join(target_root, f)
                os.makedirs(os.path.dirname(t), exist_ok=True)
                shutil.copy2(s, t)

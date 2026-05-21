"""Headless browser screenshots (formerly repo-common-take-screenshot.py)."""

import configparser
import json
import os
import re
import time
from os import path
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote, unquote, urljoin, urlparse

import configargparse
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None

DEFAULT_SCREENSHOTS_INI = "screenshots.ini"

_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][-a-zA-Z0-9+.]*:")

# Paths and file: URLs are turned into http://127.0.0.1/... (no file:// scheme).
_LOCAL_HTTP_ORIGIN = "http://127.0.0.1"


def _ensure_http_scheme(url: str) -> str:
    """Use http, never https or file (https is downgraded; file should not reach here)."""
    if url.startswith("https://"):
        return "http://" + url[len("https://") :]
    return url


def _filesystem_target_to_http(fs_path: Path) -> str:
    """Map a filesystem path to an http URL under the local host (no file://)."""
    resolved = fs_path.resolve()
    file_uri = resolved.as_uri()
    parsed = urlparse(file_uri)
    raw_path = unquote(parsed.path)
    if os.name == "nt" and len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    if raw_path.startswith("/"):
        path_q = quote(raw_path, safe="/:@")
        return _LOCAL_HTTP_ORIGIN + path_q
    path_q = quote("/" + raw_path, safe="/:@")
    return _LOCAL_HTTP_ORIGIN + path_q


def _file_url_to_http(raw: str) -> str:
    """Convert a file: URL to http://127.0.0.1/..."""
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "file":
        return raw
    raw_path = unquote(parsed.path)
    if os.name == "nt" and len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    return _filesystem_target_to_http(Path(raw_path))


def apply_base_url(base_url, url_raw):
    """
    Join ``url_raw`` to ``base_url`` when base is set and the URL is still relative.

    Absolute URLs (any ``scheme:`` or protocol-relative ``//``) are returned unchanged.
    Joining uses :func:`urllib.parse.urljoin` (trailing slash on ``base_url`` matters
    for path segments; e.g. ``http://host/app/`` + ``page`` -> ``.../app/page``).
    """
    base_url = (base_url or "").strip()
    url_raw = (url_raw or "").strip()
    if not base_url:
        return url_raw
    if url_raw.startswith("//") or _URL_SCHEME_RE.match(url_raw):
        return url_raw
    return urljoin(base_url, url_raw)


def _looks_like_web_address(s):
    """True if s is probably a http(s) host or host/path without a scheme."""
    if s.startswith("localhost") or s.startswith("127.0.0.1"):
        return True
    return bool(re.match(r"^([\w.-]+\.)+[a-zA-Z]{2,}(/|$)", s))


def normalize_screenshot_url(raw, base_dir=None):
    """
    Return a URL Chrome WebDriver accepts.

    Only **http** is used (never ``file://``). ``https://`` and ``file:`` inputs are
    normalized to ``http://``. Absolute ``/...`` paths and existing file paths become
    ``http://127.0.0.1/...``. Bare hostnames become ``http://host/...``.
    """
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("screenshot url is empty")
    if raw.startswith("//"):
        return _ensure_http_scheme("http:" + raw)
    if _URL_SCHEME_RE.match(raw):
        if raw.lower().startswith("file:"):
            return _file_url_to_http(raw)
        return _ensure_http_scheme(raw)
    if os.path.isabs(raw):
        return _filesystem_target_to_http(Path(raw))
    if base_dir:
        p = Path(base_dir) / raw
        if p.exists():
            return _filesystem_target_to_http(p)
    p_cwd = Path(os.getcwd()) / raw
    if p_cwd.exists():
        return _filesystem_target_to_http(p_cwd)
    if _looks_like_web_address(raw):
        return _ensure_http_scheme("http://" + raw.lstrip("/"))
    raise ValueError(
        "Invalid screenshot url %r: use an http(s):// URL, a path starting with / "
        "(mapped to http://127.0.0.1/...), a hostname, or a relative path that exists "
        "(INI directory or cwd). file:// is not emitted."
        % raw
    )


def set_viewport_size(driver, width, height):
    driver.set_window_size(width, height)
    actual_width = driver.execute_script("return window.innerWidth")
    actual_height = driver.execute_script("return window.innerHeight")
    delta_width = width - actual_width
    delta_height = height - actual_height
    driver.set_window_size(width + delta_width, height + delta_height)


def build_parser():
    p = configargparse.ArgParser()
    p.add(
        "--config",
        "-c",
        default=None,
        metavar="PATH",
        help="INI file listing screenshots (batch mode; not used with NAME URL)",
    )
    p.add("name", nargs="?", default=None, help="Name of the screenshot task")
    p.add("url", nargs="?", default=None, help="http(s):// URL or path (normalized to http)")
    p.add("--width", type=int, help="Viewport width in pixels", default=1024)
    p.add("--height", type=int, help="Viewport height in pixels", default=768)
    p.add("--croptop", type=int, help="Pixels to crop from top", default=0)
    p.add("--cropbottom", type=int, help="Pixels to crop from bottom", default=0)
    p.add(
        "--cropleft",
        type=int,
        help="Pixels to crop from left (e.g. sidebar width)",
        default=0,
    )
    p.add("--cropright", type=int, help="Pixels to crop from right", default=0)
    p.add("--dark", action="store_true", help="Use dark mode preferences")
    p.add(
        "--script",
        type=str,
        action="append",
        dest="scripts",
        default=None,
        metavar="PATH",
        help="Path to Python script defining run(driver); can be repeated",
    )
    p.add(
        "--exec-js",
        type=str,
        action="append",
        dest="exec_js",
        default=None,
        metavar="CODE",
        help="JavaScript to execute in page context; can be repeated",
    )
    p.add(
        "--script-js",
        type=str,
        action="append",
        dest="script_js",
        default=None,
        metavar="PATH",
        help="Path to .js file to execute in page context; can be repeated",
    )
    p.add(
        "--post-script-sleep",
        type=float,
        default=0.5,
        help="Seconds to wait after running scripts (default 0.5)",
    )
    return p


def _split_csv_paths(value):
    if not value or not str(value).strip():
        return []
    return [x.strip() for x in str(value).split(",") if x.strip()]


def _ini_get_int(cp, section, key, fallback):
    if not cp.has_option(section, key):
        return fallback
    return cp.getint(section, key)


def _ini_get_float(cp, section, key, fallback):
    if not cp.has_option(section, key):
        return fallback
    return cp.getfloat(section, key)


def load_screenshot_jobs_from_ini(config_path):
    """
    Load screenshot jobs from an INI file.

    Each section (except built-in DEFAULT) with a ``url`` key defines one job.
    Optional ``[DEFAULT]`` supplies inherited defaults for all sections, including
    ``base_url``. When ``base_url`` is set, each section's ``url`` value without a
    scheme is combined with it via :func:`urllib.parse.urljoin` (sections may
    override ``base_url``). Absolute ``http://`` / ``https://`` URLs are left to
    normalization (https becomes http); ``file:`` is converted to http.

    Per-section keys: url (required), name (default: section name), base_url (optional),
    dir (optional, inherited): directory for PNG output; relative paths are resolved from
    the INI file's directory (absolute paths are used as-is). When unset, ``SCREENSHOT_DIR``
    or the process working directory is used.
    width, height, croptop, cropbottom, cropleft, cropright, dark (true/false),
    post_script_sleep, script (comma-separated paths), script_js (comma-separated paths),
    exec_js (one snippet). Other relative paths use the INI file's directory.
    """
    config_path = path.abspath(config_path)
    if not path.isfile(config_path):
        raise FileNotFoundError("Config not found: %s" % config_path)

    base_dir = path.dirname(config_path)
    cp = configparser.ConfigParser(
        interpolation=configparser.ExtendedInterpolation(),
        default_section=configparser.DEFAULTSECT,
    )
    read = cp.read(config_path, encoding="utf-8")
    if not read:
        raise OSError("Could not read config: %s" % config_path)

    def resolve_path(p):
        p = p.strip()
        if path.isabs(p):
            return p
        return path.normpath(path.join(base_dir, p))

    jobs = []
    for section in cp.sections():
        if "url" not in cp._sections[section]:
            continue
        url_raw = cp.get(section, "url").strip()
        if not url_raw:
            raise ValueError("Empty url in section [%s] of %s" % (section, config_path))
        base_url = cp.get(section, "base_url", fallback="").strip()
        merged = apply_base_url(base_url, url_raw)
        try:
            url = normalize_screenshot_url(merged, base_dir)
        except ValueError as e:
            raise ValueError("Section [%s] in %s: %s" % (section, config_path, e)) from e
        name = cp.get(section, "name", fallback=section).strip() or section

        scripts = [resolve_path(s) for s in _split_csv_paths(cp.get(section, "script", fallback=""))]
        script_js = [
            resolve_path(s) for s in _split_csv_paths(cp.get(section, "script_js", fallback=""))
        ]
        exec_js = []
        if cp.has_option(section, "exec_js"):
            exec_js = [cp.get(section, "exec_js")]

        dark = False
        if cp.has_option(section, "dark"):
            dark = cp.getboolean(section, "dark")

        dir_raw = cp.get(section, "dir", fallback="").strip()
        if dir_raw:
            screenshot_dir = path.abspath(resolve_path(dir_raw))
        else:
            screenshot_dir = None

        job = SimpleNamespace(
            name=name,
            url=url,
            screenshot_dir=screenshot_dir,
            width=_ini_get_int(cp, section, "width", 1024),
            height=_ini_get_int(cp, section, "height", 768),
            croptop=_ini_get_int(cp, section, "croptop", 0),
            cropbottom=_ini_get_int(cp, section, "cropbottom", 0),
            cropleft=_ini_get_int(cp, section, "cropleft", 0),
            cropright=_ini_get_int(cp, section, "cropright", 0),
            dark=dark,
            scripts=scripts or None,
            exec_js=exec_js or None,
            script_js=script_js or None,
            post_script_sleep=_ini_get_float(cp, section, "post_script_sleep", 0.5),
        )
        jobs.append(job)

    if not jobs:
        raise ValueError("No screenshot sections found in %s" % config_path)

    return jobs


def run_scripts(driver, args):
    import importlib.util

    for script_path in args.scripts or []:
        script_path = path.abspath(script_path)
        if not path.isfile(script_path):
            raise FileNotFoundError("Script not found: %s" % script_path)
        spec = importlib.util.spec_from_file_location("screenshot_script", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, "run"):
            raise ValueError("Script %s must define a function run(driver)" % script_path)
        mod.run(driver)
    for code in args.exec_js or []:
        driver.execute_script(code)
    for js_path in args.script_js or []:
        js_path = path.abspath(js_path)
        if not path.isfile(js_path):
            raise FileNotFoundError("JS file not found: %s" % js_path)
        with open(js_path, "r", encoding="utf-8") as f:
            driver.execute_script(f.read())


def _chrome_options_for_size(width, height):
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=%d,%d" % (width, height))
    return chrome_options


def _create_driver(width, height):
    chrome_options = _chrome_options_for_size(width, height)
    if ChromeDriverManager is not None:
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)
    return webdriver.Chrome(options=chrome_options)


def run_capture(driver, args):
    log_prefix = "[%s] " % args.name

    set_viewport_size(driver, args.width, args.height)

    print(log_prefix + "Visiting: " + args.url)
    driver.get(args.url)
    current = driver.current_url
    if current != args.url:
        print(log_prefix + "Current URL (after redirects): " + current)
    try:
        for entry in driver.get_log("performance"):
            try:
                msg = json.loads(entry["message"])["message"]
                if msg.get("method") != "Network.responseReceived":
                    continue
                resp = msg.get("params", {}).get("response", {})
                if resp.get("url") != current and resp.get("url") != args.url:
                    continue
                if (resp.get("mimeType") or "").startswith("text/html"):
                    if resp.get("status") == 404:
                        print(
                            log_prefix + "404 Not Found: " + resp.get("url", args.url)
                        )
                    break
            except (KeyError, json.JSONDecodeError):
                pass
    except Exception:
        pass
    time.sleep(3)

    run_scripts(driver, args)
    if args.post_script_sleep > 0:
        time.sleep(args.post_script_sleep)

    if getattr(args, "screenshot_dir", None):
        screenshot_dir = args.screenshot_dir
    else:
        screenshot_dir = os.getenv("SCREENSHOT_DIR", os.getcwd())
    screenshot_dir = path.abspath(screenshot_dir)
    os.makedirs(screenshot_dir, exist_ok=True)

    filename = f"{args.name}.png"
    filepath = path.join(screenshot_dir, filename)
    driver.save_screenshot(filepath)

    print(log_prefix + "Saved screenshot as: " + path.abspath(filepath))

    if (
        args.croptop > 0
        or args.cropbottom > 0
        or args.cropleft > 0
        or args.cropright > 0
    ):
        img = Image.open(path.join(screenshot_dir, filename))
        w, h = img.size
        img = img.crop(
            (
                args.cropleft,
                args.croptop,
                w - args.cropright,
                h - args.cropbottom,
            )
        )
        img.save(path.join(screenshot_dir, filename))
        print(log_prefix + "Cropped screenshot as: " + path.abspath(filepath))


def run_from_screenshots_ini(config_path):
    jobs = load_screenshot_jobs_from_ini(config_path)
    first = jobs[0]
    driver = _create_driver(first.width, first.height)
    try:
        for job in jobs:
            run_capture(driver, job)
    finally:
        driver.quit()
    return 0


def main(argv=None):
    p = build_parser()
    args = p.parse_args(argv)

    if args.config is not None:
        if args.name is not None or args.url is not None:
            p.error("Do not pass NAME or URL when using --config")
        return run_from_screenshots_ini(args.config)

    if args.name is not None and args.url is not None:
        try:
            args.url = normalize_screenshot_url(args.url, os.getcwd())
        except ValueError as e:
            p.error(str(e))
        driver = _create_driver(args.width, args.height)
        try:
            run_capture(driver, args)
        finally:
            driver.quit()
        return 0

    default_ini = path.join(os.getcwd(), DEFAULT_SCREENSHOTS_INI)
    if path.isfile(default_ini):
        return run_from_screenshots_ini(default_ini)

    p.error(
        "Provide NAME and URL, or --config PATH, or create %s in the current directory"
        % DEFAULT_SCREENSHOTS_INI
    )

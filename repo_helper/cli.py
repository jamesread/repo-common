"""CLI entry point: repo-helper with health and screenshot subcommands."""

import argparse
import sys

_SCREENSHOT_EPILOG = """
Example screenshots.ini:

[DEFAULT]
base_url = http://example.com/app/
dir = screenshots
width = 1024
height = 768
post_script_sleep = 0.5

[home]
# Relative to base_url -> http://example.com/app/
url = .
name = home

[about]
# Path-absolute on the same host -> http://example.com/about
url = /about
width = 1280

[external]
# Full URL ignores base_url (https is normalized to http when loading)
url = http://other.example/status

# script = hooks/one.py, hooks/two.py
# script_js = snippets/extra.js
# exec_js = document.documentElement.scrollTop = 400
# dark = false
# croptop = 0

With base_url in [DEFAULT] (or per section), url values without a scheme are joined
using URL rules (trailing slash on base_url matters). Optional dir= sets the output
folder for PNGs (relative to the INI directory unless absolute). Sections with url=
are one capture each; sections without url= are skipped. Other relative paths use
the INI directory.

With --config or ./screenshots.ini, only the INI supplies options for batch mode.
--width/--script/… on the command line apply only when you pass NAME and URL.
""".strip()


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="repo-helper")
    sub = parser.add_subparsers(dest="command", required=True)

    health_p = sub.add_parser(
        "health",
        help="Run repository health checks (common files, README, GitHub, etc.)",
    )
    health_p.add_argument(
        "--show-skipped",
        action="store_true",
        help="Show skipped tests",
    )

    shot_p = sub.add_parser(
        "screenshot",
        help="Capture headless Chrome screenshot(s) from NAME URL or from screenshots.ini",
        epilog=_SCREENSHOT_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    shot_p.add_argument(
        "--config",
        "-c",
        default=None,
        metavar="PATH",
        help="INI file listing screenshots (not used with NAME and URL)",
    )
    shot_p.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Name of the screenshot task (omit with --config or default screenshots.ini)",
    )
    shot_p.add_argument(
        "url",
        nargs="?",
        default=None,
        help="http(s):// URL or path (normalized to http)",
    )
    shot_p.add_argument(
        "--width", type=int, default=1024, help="Viewport width in pixels"
    )
    shot_p.add_argument(
        "--height", type=int, default=768, help="Viewport height in pixels"
    )
    shot_p.add_argument(
        "--croptop", type=int, default=0, help="Pixels to crop from top"
    )
    shot_p.add_argument(
        "--cropbottom", type=int, default=0, help="Pixels to crop from bottom"
    )
    shot_p.add_argument(
        "--cropleft",
        type=int,
        default=0,
        help="Pixels to crop from left (e.g. sidebar width)",
    )
    shot_p.add_argument(
        "--cropright", type=int, default=0, help="Pixels to crop from right"
    )
    shot_p.add_argument("--dark", action="store_true", help="Use dark mode preferences")
    shot_p.add_argument(
        "--script",
        type=str,
        action="append",
        dest="scripts",
        default=None,
        metavar="PATH",
        help="Path to Python script defining run(driver); can be repeated",
    )
    shot_p.add_argument(
        "--exec-js",
        type=str,
        action="append",
        dest="exec_js",
        default=None,
        metavar="CODE",
        help="JavaScript to execute in page context; can be repeated",
    )
    shot_p.add_argument(
        "--script-js",
        type=str,
        action="append",
        dest="script_js",
        default=None,
        metavar="PATH",
        help="Path to .js file to execute in page context; can be repeated",
    )
    shot_p.add_argument(
        "--post-script-sleep",
        type=float,
        default=0.5,
        help="Seconds to wait after running scripts (default 0.5)",
    )

    args = parser.parse_args(argv)

    if args.command == "health":
        from repo_helper.health import main as health_main

        h_argv = []
        if args.show_skipped:
            h_argv.append("--show-skipped")
        return health_main(h_argv)

    if args.command == "screenshot":
        from repo_helper.screenshot import main as screenshot_main

        if args.config is not None:
            if args.name is not None or args.url is not None:
                parser.error("Do not pass NAME or URL when using --config")
            return screenshot_main(["--config", args.config])
        if args.name is not None and args.url is not None:
            return screenshot_main(_screenshot_argv_from_ns(args))
        if args.name is not None or args.url is not None:
            parser.error("screenshot requires both NAME and URL, or use --config / screenshots.ini")
        return screenshot_main([])

    parser.error("unknown command")
    return 2


def _screenshot_argv_from_ns(args):
    """Build argv list for screenshot.main() (configargparse)."""
    out = [args.name, args.url]
    if args.width != 1024:
        out.extend(["--width", str(args.width)])
    if args.height != 768:
        out.extend(["--height", str(args.height)])
    if args.croptop:
        out.extend(["--croptop", str(args.croptop)])
    if args.cropbottom:
        out.extend(["--cropbottom", str(args.cropbottom)])
    if args.cropleft:
        out.extend(["--cropleft", str(args.cropleft)])
    if args.cropright:
        out.extend(["--cropright", str(args.cropright)])
    if args.dark:
        out.append("--dark")
    for p in args.scripts or []:
        out.extend(["--script", p])
    for code in args.exec_js or []:
        out.extend(["--exec-js", code])
    for p in args.script_js or []:
        out.extend(["--script-js", p])
    if args.post_script_sleep != 0.5:
        out.extend(["--post-script-sleep", str(args.post_script_sleep)])
    return out


if __name__ == "__main__":
    raise SystemExit(main())

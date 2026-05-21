"""Repository health checks (formerly repohealth.py)."""

import json
import os
import pathlib
import re
import subprocess

import configargparse
import yaml


def _default_common_dir():
    return os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
            "common-files",
        )
    )


class TestOutput:
    output = ""
    test_name = ""

    def __init__(self, test_name, show_skipped=False):
        self.test_name = test_name
        self.show_skipped = show_skipped

    def info(self, msg):
        self.output += f"\t {msg}\n"

    def suggest(self, msg):
        self.output += f"\t \033[93mSUGGEST\033[0m: {msg}\n"

    def fail(self, msg):
        print(f"[\033[91mFAILED\033[0m] {self.test_name}: {msg}")
        print(self.output)

    def skip(self, msg):
        if self.show_skipped:
            print(f"[\033[90m SKIP \033[0m] {self.test_name}: {msg}")
            print(self.output)


def check_common_files(show_skipped=False):
    common_dir = os.path.abspath(
        os.getenv("COMMON_DIR", _default_common_dir())
    )

    match_files = pathlib.Path(os.path.join(common_dir)).glob("**/match.yml")

    for match_file in match_files:
        dir_name = os.path.dirname(match_file)

        match_rules = open(match_file, "r").read()
        match_rules = yaml.safe_load(match_rules)

        for filename_rule in match_rules:
            exists = os.path.exists(filename_rule)

            if exists:
                check_common_files_base(dir_name, show_skipped)
                break

    return True


def check_common_files_base(dir_name, show_skipped=False):
    files = pathlib.Path(dir_name).glob("**")

    for comm_file in files:
        output = TestOutput("check_common_files", show_skipped)

        repo_file = pathlib.Path(str(comm_file.absolute()).replace(dir_name, os.getcwd()))

        if dir_name == str(comm_file):
            continue

        output.info(f"repo_file: {repo_file}")
        output.info(f"comm_file: {comm_file}")

        if "match.yml" in repo_file.name:
            output.skip(f"{repo_file.name} skipped becaused it's a match.yml file")
            continue

        if not repo_file.exists():
            output.suggest(f"cp {comm_file} {repo_file}")
            output.fail(f"repo_file {repo_file.name} does not exist")
            continue

        if comm_file.is_dir():
            output.skip(f"dir {comm_file.name}")
            continue

        repo_file_checksum = os.popen(f"sha256sum {repo_file}").read().split()[0]
        comm_file_checksum = os.popen(f"sha256sum {comm_file}").read().split()[0]

        if repo_file_checksum == comm_file_checksum:
            output.info(f"file checksum match, repo: {repo_file}")
            output.info(f"file checksum match, comm: {comm_file}")
        else:
            output.suggest(f"vimdiff {repo_file} {comm_file}")
            output.suggest(f"cp {comm_file} {repo_file}")
            output.fail(f"file checksum does not match {comm_file}")


def get_topics():
    """Return topic names from `gh repo view`, or None if topics cannot be fetched."""
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "repositoryTopics"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    json_text = (result.stdout or "").strip()
    if not json_text:
        return None
    try:
        json_obj = json.loads(json_text)
    except json.JSONDecodeError:
        return None
    topics = json_obj.get("repositoryTopics")
    if topics is None:
        return None
    return [topic["name"] for topic in topics]


def search_readme_for_keywords(search_keywords):
    with open("README.md", "r") as f:
        readme = f.read()

    for line in readme.split("\n"):
        breakpoint_flag = False

        for keyword in search_keywords:
            if keyword in line:
                continue
            else:
                breakpoint_flag = True
                break

        if breakpoint_flag:
            continue

        return line

    return False


def parse_dashed_kv(line):
    line = line.lower()

    res = re.search(r"(\w+)-(\w+)", line, re.IGNORECASE)
    if res is None:
        return "", ""

    groups = res.groups(1)

    if len(groups) == 2:
        return res.group(1), res.group(2)

    return "", ""


def check_maturity_label():
    line = search_readme_for_keywords(["shields.io", "maturity"])

    if line is False:
        return "Maturity shield not found in README.md"

    shield_key, shield_value = parse_dashed_kv(line)

    if shield_key != "maturity":
        return "Shield found, but not a maturity shield"

    topics = get_topics()
    if topics is None:
        return (
            "Cannot fetch GitHub repository topics "
            "(ensure a git remote, gh auth, and this directory is a GitHub clone)"
        )

    selected_topic = ""

    for topic in topics:
        if "maturity" in topic:
            _, selected_topic = parse_dashed_kv(topic)
            break

    if shield_value == "production":
        shield_value = "prod"

    if selected_topic != shield_value:
        return f"Maturity shield value ({shield_value}) does not match topic ({selected_topic})"

    return True


def check_logo_exists():
    if os.path.exists("logo.svg"):
        return True
    return "logo.svg not found"


def check_discord_link_exists():
    line = search_readme_for_keywords(["discord"])

    if line is False:
        return "Discord link not found in README.md"

    if "discord.gg" in line:
        return True
    return "Discord link not found in README.md"


def check_coc_exists():
    if os.path.exists("CODE_OF_CONDUCT.md"):
        return True
    return "CODE_OF_CONDUCT.md not found"


def check_security_exists():
    if os.path.exists("SECURITY.md"):
        return True
    return "SECURITY.md not found"


def check_contributing_guide_exists():
    if os.path.exists("CONTRIBUTING.md"):
        return True
    return "CONTRIBUTING.md not found"


def check_issue_templates_exist():
    if os.path.exists(".github/ISSUE_TEMPLATE/"):
        return True
    return "Issue templates not found"


def check_precommit_exists():
    if os.path.exists(".pre-commit-config.yaml"):
        run_check(check_conventional_commits)
        return True
    return "Pre-commit config not found"


def filename_contains_line(filename, line):
    with open(filename, "r") as f:
        for file_line in f:
            if line in file_line:
                return True
    return False


def check_conventional_commits():
    if filename_contains_line(
        ".pre-commit-config.yaml",
        "repo: https://github.com/compilerla/conventional-pre-commit",
    ):
        return True
    return "Pre-commit config missing conventional commit"


def check_community_health():
    if os.getenv("OFFLINE") is not None:
        return "Offline mode"

    repo_url = os.popen("git remote get-url origin ").read()

    if repo_url is None:
        return "Could not get remote origin"

    repo_url = repo_url.replace(".git", "")

    res = re.search(r"([\-\w]+)\/([\-\w]+)$", repo_url, re.IGNORECASE)
    if res is None:
        return "Could not parse remote origin URL"

    api_url = "repos/" + res.group(1) + "/" + res.group(2) + "/community/profile"

    json_text = os.popen(f"gh api {api_url}").read()
    json_obj = json.loads(json_text)

    if "health_percentage" in json_obj:
        if json_obj["health_percentage"] == 100:
            return True
        return (
            f"Community health is {json_obj['health_percentage']}% "
            f"https://github.com/{res.group(1)}/{res.group(2)}/community"
        )
    return "Community health not found"


def run_check(check):
    res = check()

    if res is not True:
        print(f"[\033[91mFAILED\033[0m] {check.__name__}\t{res}")
    else:
        print(f"[\033[32m  OK  \033[0m] {check.__name__}")


def build_parser():
    parser = configargparse.ArgParser()
    parser.add_argument(
        "--show-skipped",
        action="store_true",
        help="Show skipped tests",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    show_skipped = args.show_skipped

    def check_common_files_cmd():
        return check_common_files(show_skipped)

    check_common_files_cmd.__name__ = "check_common_files"

    checks = [
        check_maturity_label,
        check_logo_exists,
        check_discord_link_exists,
        check_security_exists,
        check_contributing_guide_exists,
        check_precommit_exists,
        check_issue_templates_exist,
        check_community_health,
        check_common_files_cmd,
    ]

    for check in checks:
        run_check(check)

    return 0

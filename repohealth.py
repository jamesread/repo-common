#!/usr/bin/env python

import os
import json
import re
import pathlib
import yaml
import configargparse

parser = configargparse.ArgParser()
parser.add_argument('--show-skipped', action = 'store_true', help = 'Show skipped tests')
global args
args = parser.parse_args()


class TestOutput():
    output = ""
    test_name = ""

    def __init__(self, test_name):
        self.test_name = test_name

    def info(self, msg):
        self.output += f"\t {msg}\n"

    def suggest(self, msg):
        self.output += f"\t \033[93mSUGGEST\033[0m: {msg}\n"

    def fail(self, msg):
        print(f"[\033[91mFAILED\033[0m] {self.test_name}: {msg}")
        print(self.output)

    def skip(self, msg):
        if args.show_skipped:
            print(f"[\033[90m SKIP \033[0m] {self.test_name}: {msg}")
            print(self.output)


def check_common_files():
    common_dir = os.path.abspath(os.getenv('COMMON_DIR', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'common-files')))

    #print(f"[\033[90m INFO \033[0m] check_common_files {common_dir}")

    match_files = pathlib.Path(os.path.join(common_dir)).glob('**/match.yml')

    for match_file in match_files:
        #print(f"\tFound match.yaml file: {match_file}")

        dir_name = os.path.dirname(match_file)

        # open match.yaml
        match_rules = open(match_file, 'r').read()
        match_rules = yaml.safe_load(match_rules)

        #print(f"\tChecking {match_file} to see if it matches")

        for filename_rule in match_rules:
            exists = os.path.exists(filename_rule)

            if exists:
                #print(f"\tMatched filename rule: {filename_rule} in {dir_name}")
                check_common_files_base(dir_name)
                break

    return True


def check_common_files_base(dir_name):
    files = pathlib.Path(dir_name).glob('**')

    #print(f"\t\tChecking common files in {dir_name}")

    for comm_file in files:
        output = TestOutput("check_common_files")

        repo_file = pathlib.Path(str(comm_file.absolute()).replace(dir_name, os.getcwd()))

        if dir_name == str(comm_file):
            continue


        output.info(f"repo_file: {repo_file}")
        output.info(f"comm_file: {comm_file}")

        if "match.yml" in repo_file.name:
            output.skip(f"{repo_file.name} skipped becaused it's a match.yml file")
            continue

        if not repo_file.exists():
            output.fail(f"repo_file {repo_file.name} does not exist")
            continue

        if comm_file.is_dir():
            output.skip(f"dir {comm_file.name}")
            continue

        repo_file_checksum = os.popen(f'sha256sum {repo_file}').read().split()[0]
        comm_file_checksum = os.popen(f'sha256sum {comm_file}').read().split()[0]

        if repo_file_checksum == comm_file_checksum:
            output.info(f"file checksum match, repo: {repo_file}")
            output.info(f"file checksum match, comm: {comm_file}")
        else:
            output.suggest(f"vimdiff {repo_file} {comm_file}")
            output.suggest(f"cp {repo_file} {comm_file}")
            output.fail(f"file checksum does not match {comm_file}")


def get_topics():
    # exec gh command to get topics
    json_text = os.popen('gh repo view --json repositoryTopics').read()

    # parse json to get topics
    json_obj = json.loads(json_text)

    topics = json_obj['repositoryTopics']

    # get values
    topics = [topic['name'] for topic in topics]

    return topics

def search_readme_for_keywords(search_keywords):
    # read README.md file
    with open('README.md', 'r') as f:
        readme = f.read()

    for line in readme.split('\n'):
        breakpoint = False

        for keyword in search_keywords:
            if keyword in line:
                continue
            else:
                breakpoint = True
                break

        if breakpoint:
            continue

        return line

    return False

def parse_dashed_kv(line):
    line = line.lower()

    # img.shields.io/badge/maturity-Beta-orangeedi=0, ine):tr*_*, string: AnyStr, flags: _FlagsType=...) ?!?jedi?!?
    res = re.search(r'(\w+)-(\w+)', line, re.IGNORECASE)

    groups = res.groups(1)

    if len(groups) == 2:
        return res.group(1), res.group(2)

    return "", ""

def check_maturity_label():
    line = search_readme_for_keywords(["shields.io", "maturity"])

    if line == False:
        return "Maturity shield not found in README.md"

    shield_key, shield_value = parse_dashed_kv(line)

    if shield_key != 'maturity':
        return "Shield found, but not a maturity shield"

    selected_topic = ""

    for topic in get_topics():
        if "maturity" in topic:
            _, selected_topic = parse_dashed_kv(topic)
            break


    if shield_value == "production":
        shield_value = "prod"

    if selected_topic != shield_value:
        return f"Maturity shield value ({shield_value}) does not match topic ({selected_topic})"

    return True

def check_logo_exists():
    logo_exists = os.path.exists('logo.svg')

    if logo_exists:
        return True
    else:
        return "logo.svg not found"

def check_discord_link_exists():
    line = search_readme_for_keywords(["discord"])

    if line == False:
        return "Discord link not found in README.md"

    if "discord.gg" in line:
        return True
    else:
        return "Discord link not found in README.md"

def check_coc_exists():
    if os.path.exists('CODE_OF_CONDUCT.md'):
        return True

    return "CODE_OF_CONDUCT.md not found"

def check_security_exists():
    if os.path.exists('SECURITY.md'):
        return True

    return "SECURITY.md not found"

def check_contributing_guide_exists():
    if os.path.exists('CONTRIBUTING.md'):
        return True

    return "CONTRIBUTING.md not found"

def check_issue_templates_exist():
    if os.path.exists('.github/ISSUE_TEMPLATE/'):
        return True

    return "Issue templates not found"

def check_precommit_exists():
    if os.path.exists('.pre-commit-config.yaml'):
        run_check(check_conventional_commits)

        return True

    return "Pre-commit config not found"

def filename_contains_line(filename, line):
    with open(filename, 'r') as f:
        for file_line in f:
            if line in file_line:
                return True

    return False

def check_conventional_commits():
    if filename_contains_line('.pre-commit-config.yaml', 'repo: https://github.com/compilerla/conventional-pre-commit'):
        return True

    return "Pre-commit config missing conventional commit"

def check_community_health():
    if os.getenv("OFFLINE") is not None:
        return "Offline mode"

    repo_url = os.popen('git remote get-url origin ').read()

    if repo_url == None:
        return "Could not get remote origin"

    repo_url = repo_url.replace('.git', '')

    res = re.search(r'([\-\w]+)\/([\-\w]+)$', repo_url, re.IGNORECASE)

    api_url = 'repos/' + res.group(1) + '/' + res.group(2) + '/community/profile'

    json_text = os.popen(f'gh api {api_url}').read()

    json_obj = json.loads(json_text)

    if 'health_percentage' in json_obj:
        if json_obj['health_percentage'] == 100:
            return True
        else:
            return f"Community health is {json_obj['health_percentage']}% https://github.com/{res.group(1)}/{res.group(2)}/community"
    else:
        return "Community health not found"


def run_check(check):
    res = check()

    if res is not True:
        print(f"[\033[91mFAILED\033[0m] {check.__name__}\t{res}")
    else:
        print(f"[\033[32m  OK  \033[0m] {check.__name__}")


checks = [
    check_maturity_label,
    check_logo_exists,
    check_discord_link_exists,
    check_security_exists,
    check_contributing_guide_exists,
    check_precommit_exists,
    check_issue_templates_exist,
    check_community_health,
    check_common_files,
]

for check in checks:
    res = run_check(check)

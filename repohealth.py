#!/usr/bin/env python

import os
import json
import re
import pathlib
import yaml

def check_common_files():
    common_dir = os.path.abspath(os.getenv('COMMON_DIR', 'common'))

    print(f"[\033[90m INFO \033[0m] check_common_files {common_dir} \t{res}")

    match_files = pathlib.Path(os.path.join(common_dir)).glob('**/match.yml')

    for match_file in match_files:
        print(f"\tFound match.yaml file: {match_file}")

        dir_name = os.path.dirname(match_file)

        # open match.yaml
        match_rules = open(match_file, 'r').read()
        match_rules = yaml.safe_load(match_rules)

        print(f"\tChecking {match_file} to see if it matches")

        for filename_rule in match_rules:
            exists = os.path.exists(filename_rule)

            if exists:
                print(f"\tMatched filename rule: {filename_rule} in {dir_name}")
                check_common_files_base(dir_name)
                break

    return True


def check_common_files_base(dir_name):
    files = pathlib.Path(dir_name).glob('**')

    print(f"\t\tChecking common files in {dir_name}")

    for file in files:
        if not file.exists():
            print(f"\t\t[\033[91mFAILED\033[0m] {file} does not exist")
            continue

        if file.is_dir():
            print(f"\t\t[\033[90m SKIP \033[0m] dir {file.name}")
            continue

        if "match.yml" in file.name:
            print(f"\t\t[\033[90m SKIP \033[0m] cfg {file.name}")
            continue

        repo_filename = os.path.abspath(file)
        common_filename = os.path.abspath(os.path.join(dir_name, file))

        repo_file_checksum = os.popen(f'sha256sum {repo_filename}').read().split()[0]
        common_file_checksum = os.popen(f'sha256sum {common_filename}').read().split()[0]


        if repo_file_checksum == common_file_checksum:
            print(f"\t\t[\033[32m  OK  \033[0m] file checksum match: {repo_filename}")
        else:
            print(f"\t\t[\033[91mFAILED\033[0m] file checksum does not match")
            print(f"\t\t[\033[91mFAILED\033[0m] repo_filename: {repo_filename}")
            print(f"\t\t[\033[91mFAILED\033[0m] common_filename: {common_filename}")
            print(f"\t\t[\033[91mFAILED\033[0m] vimdiff {repo_filename} {common_filename}")


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
        return True

    return "Pre-commit config not found"

def check_community_health():
    if os.getenv("OFFLINE") != "":
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
    res = check()

    if res != True:
        print(f"[\033[91mFAILED\033[0m] {check.__name__}\t{res}")
    else:
        print(f"[\033[32m  OK  \033[0m] {check.__name__}")

#!/usr/bin/python3

# File format for files in the <patch_dir> directory, by line
# Note: All files must use the same length commit SHA, so commits
# in upstream-commits.txt will exactly string match the commits in
# jira-commits-map.txt and upstream-repo-map.txt
#
# upstream-commits.txt:
# <at_least_12_digits_of_commit_sha><space_or_EOL>
#
# default-jira.txt:
# RHEL-<issue_nr><space_or_EOL>
#
# jira-commits-map.txt:
# Once a line has set at least one issue, future lines don't need to.
# If a line doesn't include any issues, the issues from the last line
# that included some will be used.
# <at_least_12_digits_of_commit_sha>[<space>RHEL-<issue_nr>][...]
#
# upstream-repo-map.txt:
# <at_least_12_digits_of_commit_sha><space><upstream_repo_text>
#

import sys
import os
import re
import subprocess

def get_cmd_output(cmd):
    try:
        output = subprocess.run(cmd, text=True, capture_output=True, \
                                check=True).stdout
    except subprocess.CalledProcessError as err:
        print("Command failed")
        print(" ".join(err.cmd))
        print("Return Code:", err.returncode)
        print(err.stderr)
        sys.exit(1)
    return output

usage_str = f"Usage: {sys.argv[0]} <patch_dir> [<src_repo>] [<dest_repo>]"

if len(sys.argv) < 2 or len(sys.argv) > 4:
    print(usage_str)
    sys.exit(1)

dirs = []

for dir_arg in sys.argv[1:]:
    dir_arg = os.path.normpath(dir_arg)
    if not os.path.isdir(dir_arg):
        print("Err:", dir_arg, "doesn't exist or isn't a directory")
        sys.exit(1)
    dirs.append(dir_arg)

patch_dir = dirs[0]

in_git_dir = True
if subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
    in_git_dir = False

if len(dirs) > 1:
    src_git = ["git", "-C", dirs[1]]
else:
    if in_git_dir:
        src_git = ["git"]
    else:
        print("Err: not in a git repository, and no repository specified")
        sys.exit(1)

if len(dirs) > 2:
    dest_git = ["git", "-C", dirs[2]]
else:
    if in_git_dir:
        dest_git = ["git"]
    else:
        dest_git = src_git

if len(dirs) > 1 and subprocess.run(src_git + ["rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
    print("Err: the specified src_repo directory is not in a git repository")
    sys.exit(1)

if len(dirs) > 2 and subprocess.run(dest_git + ["rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
    print("Err: the specifcied dest_repo directory is not in a git repository")
    sys.exit(1)

user_name = get_cmd_output(dest_git + ["config", "--get", "user.name"]).rstrip()
user_email = get_cmd_output(dest_git + ["config", "--get", "user.email"]).rstrip()

commits_path = os.path.join(patch_dir, "upstream-commits.txt")
default_jira_path = os.path.join(patch_dir, "default-jira.txt")
jira_map_path = os.path.join(patch_dir, "jira-commits-map.txt")
upstream_map_path = os.path.join(patch_dir, "upstream-repo-map.txt")

if not os.path.isfile(commits_path):
    print("Err:", commits_file, "doesn't exist")
    sys.exit(1)

skip_pattern = re.compile(r'^\s*(?:#|$)')
def_jira_pattern = re.compile(r'^\s*(RHEL-[0-9]+)(?:\s|$)')

if not os.path.isfile(default_jira_path):
    print("Err:", default_jira_path, "doesn't exist")
    sys.exit(1)

line_nr = 0
def_jira = []
with open(default_jira_path) as default_jira_file:
    for line in default_jira_file:
        line_nr += 1
        line = line.rstrip()
        if skip_pattern.match(line):
            continue
        result = def_jira_pattern.match(line)
        if result == None:
            print(f'{default_jira_path}: invalid line at {line_nr}: "{line}"')
            continue
        def_jira.append(result.group(1))

jira_commit_pattern = re.compile(r'^\s*([0-9a-f]{12,40})((?:\s+RHEL-[0-9]+)*)\s*(?:#|$)')
jira_pattern = re.compile(r'RHEL-[0-9]+')

line_nr = 0
jira_map = {}
curr_issues = []
if os.path.isfile(jira_map_path):
    with open(jira_map_path) as jira_map_file:
        for line in jira_map_file:
            line_nr += 1
            line = line.rstrip()
            if skip_pattern.match(line):
                continue
            result = jira_commit_pattern.match(line)
            if result == None:
                print(f'{jira_map_path}: invalid line at {line_nr}: "{line}"')
                continue
            jira_commit = result.group(1)
            issue_match = result.group(2)
            if issue_match != "":
                curr_issues = jira_pattern.findall(issue_match)
            elif curr_issues == []:
                print(f'{jirs_map_path}: bad line at {line_nr}. No issuess listed here or previously')
                continue
            jira_map[jira_commit] = curr_issues

upstream_pattern = re.compile(r'^\s*([0-9a-f]{12,40})(?:\s+([^\s#][^#]*?))?\s*(?:#|$)')

line_nr = 0
upstream_map = {}
curr_upstream = None
if os.path.isfile(upstream_map_path):
    with open(upstream_map_path) as upstream_map_file:
        for line in upstream_map_file:
            line_nr += 1
            line = line.rstrip()
            if skip_pattern.match(line):
                continue
            result = upstream_pattern.match(line)
            if result == None:
                print(f'{upstream_map_path}: invalid line at {line_nr}: "{line}"')
                continue
            upstream_commit = result.group(1)
            if result.group(2) != None:
                curr_upstream = result.group(2)
            if curr_upstream == None:
                print(f'{upstream_map_path}: bad line at {line_nr}. No upstream listed here or previously')
                continue
            upstream_map[upstream_commit] = curr_upstream

commit_pattern = re.compile(r'^\s*([0-9a-f]{12,40})(?:\s|$)')

patch_nr = 0
line_nr = 0
with open(commits_path) as commits_file:
    for line in commits_file:
        line_nr += 1
        line = line.rstrip()
        if skip_pattern.match(line):
            continue
        result = commit_pattern.match(line)
        if result == None:
            print(f'{commits_path}: invalid line at {line_nr}: "{line}"')
            continue
        patch_nr += 1
        commit_id = result.group(1)
        [subject, file_base] = get_cmd_output(src_git + ["show", commit_id, "-s", "--pretty=format:%s%n%f"]).rstrip().split("\n")
        file_path = os.path.join(patch_dir, f"{patch_nr:04}-{file_base[:52]}.patch")
        patch_data = f"From: {user_name} <{user_email}>\n"
        patch_data += f"Subject: {subject}\n\n"
        if commit_id in jira_map:
            jiras = jira_map[commit_id]
            del jira_map[commit_id]
        else:
            jiras = def_jira
        for jira in jiras:
            patch_data += f"JIRA: https://issues.redhat.com/browse/{jira}\n"
        if commit_id in upstream_map:
            patch_data += f"Upstream Status: {upstream_map[commit_id]}\n\n"
            del upstream_map[commit_id]
        else:
            patch_data += f"Upstream Status: kernel/git/torvalds/linux.git\n\n"
        patch_data += get_cmd_output(src_git + ["show", commit_id, "-s"])
        patch_data += f"\nSigned-off-by: {user_name} <{user_email}>\n\n"
        patch_data += get_cmd_output(src_git + ["show", commit_id, "--pretty=format:"])
        with open(file_path, 'w') as patch_file:
            patch_file.write(patch_data)

for commit_id in upstream_map:
    print(f"Warning: unused commit id {commit_id} in {upstream_map_path}")
for commit_id in jira_map:
    print(f"Warning: unused commit id {commit_id} in {jira_map_path}")

#!/usr/bin/python3

# File format for files in the <patch_dir> directory, by line
# Note: All files must use the same length commit SHA, so commits
# in upstream-commits.txt will exactly string match the commits in
# bz-commits-map.txt and dm-commits.txt
#
# upstream-commits.txt:
# <at_least_12_digits_of_commit_sha><space_or_EOL>
#
# default-bz.txt:
# <7_digit_bugzilla_nr><space_or_EOL>
#
# bz-commits-map.txt:
# Once a line has set at least one bz, future lines don't need to.
# If a line doesn't include any bzs, the bzs from the last line
# that included some will be used.
# <at_least_12_digits_of_commit_sha>[<space><7_digit_bugzilla_nr>][...]
#
# dm-commits.txt:
# <at_least_12_digits_of_commit_sha><space_or_EOL>
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
default_bz_path = os.path.join(patch_dir, "default-bz.txt")
bzs_map_path = os.path.join(patch_dir, "bz-commits-map.txt")
dm_commits_path = os.path.join(patch_dir, "dm-commits.txt")

if not os.path.isfile(commits_path):
    print("Err:", commits_file, "doesn't exist")
    sys.exit(1)

skip_pattern = re.compile(r'^\s*(?:#|$)')
def_bz_pattern = re.compile(r'^\s*([0-9]{7})(?:\s|$)')

if not os.path.isfile(default_bz_path):
    print("Err:", default_bz, "doesn't exist")
    sys.exit(1)

line_nr = 0
def_bzs = []
with open(default_bz_path) as default_bz_file:
    for line in default_bz_file:
        line_nr += 1
        line = line.rstrip()
        if skip_pattern.match(line):
            continue
        result = def_bz_pattern.match(line)
        if result == None:
            print(f'{default_bz_path}: invalid line at {line_nr}: "{line}"')
            continue
        def_bzs.append(result.group(1))

bzs_commit_pattern = re.compile(r'^\s*([0-9a-f]{12,40})((?:\s+[0-9]{7})*)\s*(?:#|$)')
bzs_pattern = re.compile(r'[0-9]{7}')

line_nr = 0
bzs_map = {}
curr_bzs = []
if os.path.isfile(bzs_map_path):
    with open(bzs_map_path) as bzs_map_file:
        for line in bzs_map_file:
            line_nr += 1
            line = line.rstrip()
            if skip_pattern.match(line):
                continue
            result = bzs_commit_pattern.match(line)
            if result == None:
                print(f'{bzs_map_path}: invalid line at {line_nr}: "{line}"')
                continue
            bz_commit = result.group(1)
            bug_match = result.group(2)
            if bug_match != "":
                curr_bzs = bzs_pattern.findall(bug_match)
            elif curr_bzs == []:
                print(f'{bzs_map_path}: bad line at {line_nr}. No bugs listed here or previously')
                continue
            bzs_map[bz_commit] = curr_bzs

commit_pattern = re.compile(r'^\s*([0-9a-f]{12,40})(?:\s|$)')

line_nr = 0
dm_commits = set()
if os.path.isfile(dm_commits_path):
    with open(dm_commits_path) as dm_commits_file:
        for line in dm_commits_file:
            line_nr += 1
            line = line.rstrip()
            if skip_pattern.match(line):
                continue
            result = commit_pattern.match(line)
            if result == None:
                print(f'{dm_commits_path}: invalid line at {line_nr}: "{line}"')
                continue
            dm_commits.add(result.group(1))

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
        if commit_id in bzs_map:
            bugs = bzs_map[commit_id]
            del bzs_map[commit_id]
        else:
            bugs = def_bzs
        for bz in bugs:
            patch_data += f"Bugzilla: https://bugzilla.redhat.com/{bz}\n"
        if commit_id in dm_commits:
            patch_data += f"Upstream Status: kernel/git/device-mapper/linux-dm.git\n\n"
            dm_commits.remove(commit_id)
        else:
            patch_data += f"Upstream Status: kernel/git/torvalds/linux.git\n\n"
        patch_data += get_cmd_output(src_git + ["show", commit_id, "-s"])
        patch_data += f"\nSigned-off-by: {user_name} <{user_email}>\n\n"
        patch_data += get_cmd_output(src_git + ["show", commit_id, "--pretty=format:"])
        with open(file_path, 'w') as patch_file:
            patch_file.write(patch_data)

for commit_id in dm_commits:
    print(f"Warning: unused commit id {commit_id} in {dm_commits_path}")
for commit_id in bzs_map:
    print(f"Warning: unused commit id {commit_id} in {bzs_map_path}")

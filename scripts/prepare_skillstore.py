import json
import os
from os.path import exists, join, dirname

from ovos_skills_manager import SkillEntry
from ovos_utils.bracket_expansion import expand_options

branch = "dev"
repo = "skill-ovos-fallback-unknown"
author = "OpenVoiceOS"

url = f"https://github.com/{author}/{repo}@{branch}"

skill = SkillEntry.from_github_url(url)
tmp_skills = "/tmp/osm_installed_skills"
skill_folder = f"{tmp_skills}/{skill.uuid}"

base_dir = dirname(dirname(__file__))

readme = join(base_dir, "README.md")
jsonf = join(base_dir, "skill.json")
skill_code = join(base_dir, "__init__.py")

res_folder = join(base_dir, "locale", "en-us")


def read_samples(path):
    samples = []
    with open(path) as fi:
        for _ in fi.read().split("\n"):
            if _ and not _.strip().startswith("#"):
                samples += expand_options(_)
    return samples


samples = []
for root, folders, files in os.walk(res_folder):
    for f in files:
        if f.endswith(".intent"):
            samples += read_samples(join(root, f))
skill._data["examples"] = list(set(samples))

if not exists(readme):
    with open(readme, "w") as f:
        f.write(skill.generate_readme())

if not exists(jsonf):
    data = skill.json
    data["desktopFile"] = False
else:
    with open(jsonf) as f:
        data = json.load(f)

# set dev branch
data["branch"] = "dev"

with open(jsonf, "w") as f:
    json.dump(data, f, indent=4)

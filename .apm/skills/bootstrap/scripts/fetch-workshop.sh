#!/bin/sh
# Fetches a Workshop template and the in-project SDKs it uses from a release
# tag into .workshop/ of the current directory, naming the workshop after it.
#
# Usage: fetch-workshop.sh TAG TEMPLATE
#   TAG       a workshop-v* release tag, such as workshop-v0.1.0
#   TEMPLATE  a file name under assets/workshops/ without .yaml, such as
#             claude-code
set -eu

if [ $# -ne 2 ]; then
  echo "usage: fetch-workshop.sh TAG TEMPLATE" >&2
  exit 2
fi
tag=$1
template=$2
assets="https://raw.githubusercontent.com/mertalpt/agent-collections/$tag/.apm/skills/bootstrap/assets"

# Workshop's naming rules: a lowercase letter, then lowercase letters and
# digits with single hyphens between them, up to 40 characters.
name=$(basename "$PWD")
if ! printf '%s\n' "$name" | grep -Eq '^[a-z][a-z0-9]*(-[a-z0-9]+)*$' \
  || [ ${#name} -gt 40 ]; then
  echo "error: '$name' is not a valid workshop name; rename the directory" >&2
  exit 1
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/template.yaml" "$assets/workshops/$template.yaml"
sed "s/^name: .*/name: $name/" "$tmp/template.yaml" > "$tmp/workshop.yaml"

# Each in-project SDK in assets/sdks/ is a sdk.yaml and a setup-base hook.
sdks=$(sed -n 's/^ *- name: project-\([a-z0-9-]*\) *$/\1/p' "$tmp/template.yaml")
for sdk in $sdks; do
  mkdir -p "$tmp/sdks/$sdk/hooks"
  curl -fsSL -o "$tmp/sdks/$sdk/sdk.yaml" "$assets/sdks/$sdk/sdk.yaml"
  curl -fsSL -o "$tmp/sdks/$sdk/hooks/setup-base" "$assets/sdks/$sdk/hooks/setup-base"
done

for path in "$name.yaml" $sdks; do
  if [ -e ".workshop/$path" ]; then
    echo "error: .workshop/$path already exists" >&2
    exit 1
  fi
done

mkdir -p .workshop
for sdk in $sdks; do
  mv "$tmp/sdks/$sdk" ".workshop/$sdk"
done
mv "$tmp/workshop.yaml" ".workshop/$name.yaml"
echo "Created .workshop/$name.yaml and in-project SDKs:" $sdks

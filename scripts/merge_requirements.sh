#!/usr/bin/env bash

# A script that finds the union of 2 sets of requirements.
#
# Usage:
# merge_requirements $MAIN $SUB
#
# This merges requirements prioritising the specifications in $MAIN over $SUB

function sanitise() {
   tr '[:upper:]' '[:lower:]' < ${1} | grep -ioE '[0-9a-z\\-\\_]+[>=<]{1}' | tr -d ">=<"
}

main=$1
sub=$2

if [ ! -f "$main" ] || [ ! -f "$sub" ]; then
  echo 'Expected both files to exist.'
  exit 1
fi

for module in $(( sanitise "$main" ; sanitise "$sub" ) | uniq); do
  dependency=$(grep -ioE "^$module.*" "$main")
  if [ -z "$dependency" ]; then
    dependency=$(grep -ioE "^$module.*" "$sub")
  fi
  [[  -n "$dependency" ]] && echo "$dependency"
done
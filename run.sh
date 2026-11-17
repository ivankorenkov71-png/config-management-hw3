#!/bin/sh

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
exec python3 "$project_dir/src/assembler.py" "$@"

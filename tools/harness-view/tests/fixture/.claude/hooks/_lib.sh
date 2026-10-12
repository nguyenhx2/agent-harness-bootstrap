#!/bin/sh
# Shared helpers. Not registered: every hook sources it with
#   . "$(dirname "$0")/_lib.sh"
deny() { echo "$1" >&2; exit 2; }

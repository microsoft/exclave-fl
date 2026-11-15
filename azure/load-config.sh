# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# Loads azure/config.env and checks it. Source it, don't run it.

CVM_FL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"   # $0: zsh
export CVM_FL_DIR

if [ ! -f "$CVM_FL_DIR/config.env" ]; then
  echo "error: $CVM_FL_DIR/config.env not found. Copy config.env.example to config.env and fill it in." >&2
  return 1
fi

set -a
. "$CVM_FL_DIR/config.env"
set +a

case "$DNS_PREFIX" in
  "") ;;
  site*|[!a-z]*|*[!a-z0-9-]*)
    echo "error: DNS_PREFIX=\"$DNS_PREFIX\" in $CVM_FL_DIR/config.env: use lowercase letters, digits and hyphens," \
         "start with a letter, and do not start with \"site\" (prepare.sh treats site* folders as clients)" >&2
    return 1 ;;
esac

#!/bin/sh
# Start as root just long enough to make sure the hub's data folder belongs to the hub's
# own user: a host folder mounted at /data, or a volume an older setup made as root,
# otherwise stops it with "unable to open database file". Then run the hub as that user.
# Started as another user already (compose `user:`), it leaves everything as it is.
set -e
dir="${HUB_DATA_DIR:-/data}"
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$dir"
    find "$dir" ! -user hub -exec chown hub:hub {} +
    exec setpriv --reuid=hub --regid=hub --init-groups "$@"
fi
exec "$@"

#!/usr/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

set -e

if [ x$1 == x ]; then
    release="test/26_Alpha"
else
    release=$1
fi

if [ x$2 == x ]; then
    dest="$SCRIPT_DIR/$release"
else
    dest="$2/$release"
fi

# Make sure every directory is present, even if it is empty
for arch in "x86_64" "i686" "armv7hl" "aarch64" "ppc64" "ppc64le"; do
    mkdir -p $dest/override/$arch/sources $dest/override/$arch/os
done

if [ "$release" == "rawhide" ]; then
    # Remove the generated archful SRPMs to save space, since they change
    # constantly on rawhide
    find $dest -name "*override*.src.rpm" -exec rm {} \;
fi

# Generate or update all of the repodata
for arch in "x86_64" "i686" "armv7hl" "aarch64" "ppc64" "ppc64le"; do
    createrepo_c $dest/override/$arch/sources
    createrepo_c $dest/override/$arch/os
done

# Set the group ownership to the modularity-wg group
chgrp -R 189842 $dest

# Any changes made in these directories should also set this group
find $dest -type d -exec chmod g+s {} \;

rsync -avh --delete-before -e ssh  $dest/ fedorapeople.org:/project/modularity/repos/fedora/gencore-override/$release

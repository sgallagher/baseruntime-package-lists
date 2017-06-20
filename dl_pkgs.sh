#!/usr/bin/bash

PROCESSORS=$(/usr/bin/getconf _NPROCESSORS_ONLN)

if [ x$1 == x ]; then
    echo "No NVR file provided"
    exit 1
else
    nvrfile=$(realpath $1)
fi

if [ x$2 == x ]; then
    release="test/26_Alpha"
else
    release=$2
fi


for arch in "x86_64" "i686" "armv7hl" "aarch64" "ppc64" "ppc64le"; do
    mkdir -p repo/$release/override/$arch/os repo/$release/override/$arch/sources
    pushd repo/$release/override/$arch/os/
    cat $nvrfile | xargs --max-procs=$PROCESSORS -I NVR \
        koji download-build --arch=noarch --arch=$arch NVR
    popd
    pushd repo/$release/override/$arch/sources/
    cat $nvrfile | xargs --max-procs=$PROCESSORS -I NVR \
        koji download-build --arch=src NVR
    popd
done

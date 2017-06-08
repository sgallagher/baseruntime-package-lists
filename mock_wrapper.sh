#!/usr/bin/bash
# Usage: ./mock_wrapper.sh <version> <NVR file>

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

set -e
PROCESSORS=$(/usr/bin/getconf _NPROCESSORS_ONLN)

RELEASEVER=$1
VERNUM=$RELEASEVER
if [ "$RELEASEVER" == "rawhide" ]; then
    VERNUM=27
fi

tmp_cfg=`mktemp`
cat > $tmp_cfg << EOF

config_opts['root'] = 'fedora-$RELEASEVER-srpm'
config_opts['target_arch'] = 'x86_64'
config_opts['legal_host_arches'] = ('x86_64')
config_opts['chroot_setup_cmd'] = 'install bash fedora-release fedpkg gnupg2 git-core redhat-rpm-config rpm-build shadow-utils gawk koji glibc-minimal-langpack rpmdevtools'
config_opts['dist'] = 'fc$VERNUM'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['releasever'] = '$VERNUM'
config_opts['package_manager'] = 'dnf'
config_opts['use_bootstrap_container'] = False

config_opts['yum.conf'] = """
[main]
keepcache=1
debuglevel=2
reposdir=/dev/null
logfile=/var/log/yum.log
retries=20
obsoletes=1
gpgcheck=0
assumeyes=1
syslog_ident=mock
syslog_device=
install_weak_deps=0
metadata_expire=0
mdpolicy=group:primary
best=1

# repos

[fedora]
name=fedora
metalink=https://mirrors.fedoraproject.org/metalink?repo=fedora-$RELEASEVER&arch=\$basearch
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-$VERNUM-primary
gpgcheck=1

[updates]
name=updates
metalink=https://mirrors.fedoraproject.org/metalink?repo=updates-released-f$RELEASEVER&arch=\$basearch
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-$VERNUM-primary
gpgcheck=1
"""

EOF

# Compare and replace if it has changed
if ! diff -q $tmp_cfg $SCRIPT_DIR/fedora-$RELEASEVER-multiarch.cfg ; then
    mv $tmp_cfg $tmp_cfg $SCRIPT_DIR/fedora-$RELEASEVER-multiarch.cfg
fi

mock -r $SCRIPT_DIR/fedora-$RELEASEVER-multiarch.cfg init
mock -r $SCRIPT_DIR/fedora-$RELEASEVER-multiarch.cfg --chroot "mkdir -p /opt/srpm/output"
mock -r $SCRIPT_DIR/fedora-$RELEASEVER-multiarch.cfg --copyin $SCRIPT_DIR/recreate_srpm.sh \
                                           /opt/srpm/recreate_srpm.sh
mock -r $SCRIPT_DIR/fedora-$RELEASEVER-multiarch.cfg --copyin $SCRIPT_DIR/get_package_hashes.py \
                                           /opt/srpm/get_package_hashes.py
mock -r $SCRIPT_DIR/fedora-$RELEASEVER-multiarch.cfg --copyin $2 \
                                           /opt/srpm/srpms.txt
mock -r $SCRIPT_DIR/fedora-$RELEASEVER-multiarch.cfg --cwd=/opt/srpm/output --chroot \
    "cat /opt/srpm/srpms.txt | xargs --max-procs=$PROCESSORS -I NVR \
    /opt/srpm/recreate_srpm.sh NVR"
rm -Rf ./output
mock -r $SCRIPT_DIR/fedora-$RELEASEVER-multiarch.cfg --copyout /opt/srpm/output ./output


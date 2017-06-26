# Generating Base Runtime Lists

This repository provides a series of BASH and Python tools for creating and
updating lists and dist-git hashes for modules in the Fedora Project.

## Setup
Storage requirements:
* You may need up to 20GiB of free space for the repository data

These tools require the following pre-requisites:
* bash
* python 2
* python 3
* rsync
* mock
* depchase (See below)

To hack on these tools, you may also need:
* argbash

The user that will be downloading the RPM repos to work with must have the
`mock` package installed on their system and be a member of the 'mock' group.
This can be accomplished by:
```
dnf install mock
usermod -a -G mock <yourloginname>
```

The user that will be operating on the override repositories must be a member
of the `modularity-wg` group in the Fedora Account system, that your SSH keys
are properly set up for use with Fedora infrastructure and also that you have
an identical group present in `/etc/group` such as:
```
modularity-wg:x:189842:<yourloginname>
```
This is so the sync tools can ensure that the files on Fedora People are
accessible to all members of the modularity-wg team. When you add this, log out
of your current session and back in to have the new group take effect.

## Legend/Glossary
I will use the following terms or variables in this document:

`<release>`: The path on disk representing a Fedora release or pre-release.
For example: Fedora 25 would be `25`, but Fedora 26 Beta would be
`test/26_beta`.

`<arch>`: The processor architecture, such as `x86_64` or `aarch64`.

### Installing depchase

```
$ git clone https://github.com/fedora-modularity/depchase.git
$ cd depchase
$ python3 setup.py install --user
```
This will install the `depchase` command as `~/.local/bin/depchase`

You may wish to add this to your default PATH variable in `~/.bashrc` by doing:
```
$ echo "export PATH=$PATH:$HOME/.local/bin" >> ~/.bashrc
```

## Preparing the local repository data

Depchase (a tool we use for processing the data) requires local copies of the
repository metadata against which to operate. This repository provides some
convenient tools for retrieving this data.

### Syncing the existing repositories

Use the `download_repo.sh` tool located in the root of this repository to
retrieve the repository metadata and override repositories.

For example:

```
./download_repo --release=26 \
                --milestone=Beta \
                --archful-srpm-file=./archful-srpms.txt \
                --arch=aarch64 \
                --arch=armv7hl \
                --arch=i686 \
                --arch=ppc64 \
                --arch=ppc64le \
                --arch=x86_64 \
                --overrides
```

This will download the frozen Fedora 26 Beta repository metadata, the overrides
repository for that milestone and will automatically regenerate those SRPMs that
are known to have arch-specific `BuildRequires` and merge them locally to the
repo metadata. The packages will be stored in the `repo/test/26_beta/` path
relative to the root of this repository.

This process may take a long time, as it will transfer approximately 3GiB of
data per architecture to the local system. This tool uses rsync, so subsequent
calls to it will only download updated information (plus regenerating the
archful SRPMs).

### Adding content to the override repositories

Copy any binary (or noarch) RPMs for inclusion into
`repo/<release>/override/<arch>/os`. For source RPMs, copy them to the
`repo/<release>/override/<arch>/sources` path. Run
`./repo/rsync-push.sh [<release>]` to automatically update the repo metadata and
rsync the contents to the fedorapeople repository.

There is a helper utility in the root of the git repository called `dl_pkgs.sh`.
This utility must be called with one argument: a path to a file containing one
package NVR or Koji build-id per line. If it is an NVR, the package must be an
official build in Koji. For a build-id, a scratch-build may work (but is
untested). This tool should be used to prep the override repository whenever a
content change is made to the module metadata, to keep the lists up-to-date.

Once completed, running `./repo/rsync-push.sh [<release>]` will update the
fedorapeople repository.

## Dealing with SRPMs with arch-specific BuildRequires
Some packages have differing BuildRequires depending on which platform is being
built. In these cases, in order to have the list generation find the right
values, we need to pull down those SRPMs and regenerate them for every
architecture that we process.

There is a helper utility in the root of the git repository called
`mock_wrapper.sh` which takes a single argument: a list of NVRs of official Koji
builds that should be regenerated. It will construct a mock buildroot with
limited packages (to reduce the risk that the output could be different
depending on the packages available in the host system), check out each of the
requested SRPM packages and regenerate them on each architecture. It will then
drop them into a directory `./output` (clobbering any existing content!) relative
to the working directory that was executed.

Once that content is present, you can run `./populate_srpm_repo.sh [<release>]`
from the root of the git repository, which will move all of the `./output`
contents into the `repo/` hierarchy, after which you can follow the "Pushing to
the override repositories" instructions above.

This functionality is automatically run whenever the `download_repo.sh` script
is invoked with the `--with-archful-srpm-file` argument.

## How to generate package lists
Ensure that the contents of `toplevel-binary-packages.txt` and `hints.txt` in
each of the `data/Fedora/$VERSION[_$MILESTONE]/$MODULE/$ARCH` directories is correct.
These files must be present for each architecture to be processed.

`toplevel-binary-packages.txt` contains the set of package names that the base
runtime must contain in order to provide the requisite APIs.

`hints.txt` is a manually-curated set of packages that is used to resolve
ambiguities in dependencies. For example, the `glibc` package
`Requires: glibc-langpack` and many packages may `Provides: glibc-langpack`, so
we include `glibc-minimal-langpack` in the hints.txt to resolve this decision.


Then call `generate_module_lists.sh` like so:

```
./generate_module_lists.sh --version 26 \
                           --milestone=Beta \
                           --module=base-runtime \
                           --arch=aarch64 \
	                   --arch=armv7hl \
                           --arch=i686 \
                           --arch=ppc64 \
                           --arch=ppc64le \
                           --arch=x86_64
```

This will produce a set of files in the
`data/Fedora/$VERSION[_$MILESTONE]/$MODULE/$ARCH` directories named:
* runtime-binary-packages-full.txt
* runtime-binary-packages-short.txt
* runtime-source-packages-full.txt
* runtime-source-packages-short.txt
* runtime-hashes.txt
* selfhosting-binary-packages-full.txt
* selfhosting-binary-packages-short.txt
* selfhosting-source-packages-full.txt
* selfhosting-source-packages-short.txt

## How to update module hashes
After generating the package lists, there will be a file called
`runtime-hashes.txt` in the data directory. We will use this package to
identify changes between the current version of the module in dist-git and the
updated data.

__Note: it is recommended _not_ to operate directly on the dist-git version of
the modulemd, since the tool does not retain file ordering, formatting or any
comments.__

First, reflow the modulemd into a "standard" form understood by PyYAML. This
will make the later diff easier to view (since things may be moved around by
the PyYAML data dumper).
```
./parse_modulemd.py --modulemd=/path/to/base-runtime/base-runtime.yaml \
                    reflow_modulemd --output_file=./base-runtime-orig.yaml
```

Then we can update this modulemd with the new data:
```
./parse_modulemd.py --modulemd=./base-runtime-orig.yaml \
                    update_module_hashes \
                    --hash-file=/path/to/runtime-hashes.txt \
                    --output_file=./base-runtime.yaml
```
(Also, you can run this multiple times safely against the runtime-hashes.txt
for each architecture you care about so to make sure to pull in any updates to
packages that exist only on a subset of architectures.)

Then you can do a `diff` between `./base-runtime-orig.yaml` and
`./base-runtime.yaml` and manually merge changes to the dist-git modulemd.

As noted above, it is best to do this by hand so that you can identify places
where the changes might not be as desired.

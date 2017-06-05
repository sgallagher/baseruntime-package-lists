#!/bin/bash
#
# If modifications are made to the following template, run
# `argbash -o ./download_repo.sh ./download_repo.sh`
# which will update the generated code.
# ARG_OPTIONAL_SINGLE([release],[],[Which Fedora release?],[26])
# ARG_OPTIONAL_SINGLE([milestone],[],[Which release milestone? Alpha, Beta or GA],[GA])
# ARG_OPTIONAL_SINGLE([repo-path],[],[Base directory for storing the repodata],[.])
# ARG_OPTIONAL_REPEATED([arch],[],[Which CPU architecture(s)?],[])
# ARG_OPTIONAL_BOOLEAN([updates],[],[Whether to also download the latest updates repodata])
# ARG_OPTIONAL_BOOLEAN([clobber],[],[Whether to remove the existing repodata and download it fresh],[on])
# ARG_HELP([Download the RPM repodata for the requested Fedora version and milestone])
# ARGBASH_GO()
# needed because of Argbash --> m4_ignore([
### START OF CODE GENERATED BY Argbash v2.4.0 one line above ###
# Argbash is a bash code generator used to get arguments parsing right.
# Argbash is FREE SOFTWARE, see https://argbash.io for more info

die()
{
	local _ret=$2
	test -n "$_ret" || _ret=1
	test "$_PRINT_HELP" = yes && print_help >&2
	echo "$1" >&2
	exit ${_ret}
}

begins_with_short_option()
{
	local first_option all_short_options
	all_short_options='h'
	first_option="${1:0:1}"
	test "$all_short_options" = "${all_short_options/$first_option/}" && return 1 || return 0
}



# THE DEFAULTS INITIALIZATION - OPTIONALS
_arg_release="26"
_arg_milestone="GA"
_arg_repo_path="."
_arg_arch=()
_arg_updates=off
_arg_clobber=on

print_help ()
{
	echo "Download the RPM repodata for the requested Fedora version and milestone"
	printf 'Usage: %s [--release <arg>] [--milestone <arg>] [--repo-path <arg>] [--arch <arg>] [--(no-)updates] [--(no-)clobber] [-h|--help]\n' "$0"
	printf "\t%s\n" "--release: Which Fedora release? (default: '"26"')"
	printf "\t%s\n" "--milestone: Which release milestone? Alpha, Beta or GA (default: '"GA"')"
	printf "\t%s\n" "--repo-path: Base directory for storing the repodata (default: '"."')"
	printf "\t%s\n" "--arch: Which CPU architecture(s)? (empty by default)"
	printf "\t%s\n" "--updates,--no-updates: Whether to also download the latest updates repodata (off by default)"
	printf "\t%s\n" "--clobber,--no-clobber: Whether to remove the existing repodata and download it fresh (on by default)"
	printf "\t%s\n" "-h,--help: Prints help"
}

# THE PARSING ITSELF
while test $# -gt 0
do
	_key="$1"
	case "$_key" in
		--release|--release=*)
			_val="${_key##--release=}"
			if test "$_val" = "$_key"
			then
				test $# -lt 2 && die "Missing value for the optional argument '$_key'." 1
				_val="$2"
				shift
			fi
			_arg_release="$_val"
			;;
		--milestone|--milestone=*)
			_val="${_key##--milestone=}"
			if test "$_val" = "$_key"
			then
				test $# -lt 2 && die "Missing value for the optional argument '$_key'." 1
				_val="$2"
				shift
			fi
			_arg_milestone="$_val"
			;;
		--repo-path|--repo-path=*)
			_val="${_key##--repo-path=}"
			if test "$_val" = "$_key"
			then
				test $# -lt 2 && die "Missing value for the optional argument '$_key'." 1
				_val="$2"
				shift
			fi
			_arg_repo_path="$_val"
			;;
		--arch|--arch=*)
			_val="${_key##--arch=}"
			if test "$_val" = "$_key"
			then
				test $# -lt 2 && die "Missing value for the optional argument '$_key'." 1
				_val="$2"
				shift
			fi
			_arg_arch+=("$_val")
			;;
		--no-updates|--updates)
			_arg_updates="on"
			test "${1:0:5}" = "--no-" && _arg_updates="off"
			;;
		--no-clobber|--clobber)
			_arg_clobber="on"
			test "${1:0:5}" = "--no-" && _arg_clobber="off"
			;;
		-h*|--help)
			print_help
			exit 0
			;;
		*)
			_PRINT_HELP=yes die "FATAL ERROR: Got an unexpected argument '$1'" 1
			;;
	esac
	shift
done

# OTHER STUFF GENERATED BY Argbash

### END OF CODE GENERATED BY Argbash (sortof) ### ])
# [ <-- needed because of Argbash

pushd () {
    command pushd "$@" > /dev/null
}

popd () {
    command popd "$@" > /dev/null
}

function is_secondary_arch()
{
    arch=$1
    version=$2

    if [ $arch == "x86_64" ]; then
        return 0
    fi

    if [ $arch == "armhfp" -a $version -ge 20 ]; then
        return 0
    fi

    if [ $arch == "i386" -a $version -le 25 ]; then
        return 0
    fi

    # All other architectures are alternative
    return 1
}

alt_arch_base="rsync://mirrors.kernel.org/fedora-secondary/releases"
primary_arch_base="rsync://mirrors.kernel.org/fedora/releases"

version=$_arg_release
milestone=$_arg_milestone

if [ $_arg_release == "Rawhide" ]; then
    alt_arch_base="rsync://mirrors.kernel.org/fedora-secondary/development/rawhide/Everything/"
    primary_arch_base="rsync://mirrors.kernel.org/fedora/development/rawhide/Everything/"

    print_milestone="Rawhide"
    version_path="rawhide"

    # This is a hack; fix it later to auto-detect
    # We need to do this to ensure that we set up the right primary and
    # alternative architectures
    version=27
else
    print_milestone=$_arg_milestone
    if [ $milestone == "GA" ]; then
        version_path="$version"
    else
        version_path="test/${version}_${milestone}"
    fi
fi

# The Source RPMs always come from the primary path
source_uri="${primary_arch_base}/${version_path}/Everything/source/tree/repodata/"

dest_sources="${_arg_repo_path}/repo/${version_path}/frozen/sources/repodata"
mkdir -p $dest_sources
# rsync the source RPM repodata from mirrors.kernel.org
echo "Downloading source RPM repodata from $source_uri"
rsync -azh --no-motd --delete-before $source_uri $dest_sources

for arch in ${_arg_arch[@]}; do
    basearch=$(./get_basearch $arch)

    # The primary and alternative architectures are stored separately
    is_secondary_arch $basearch $version
    sec_arch=$?
    if [ $sec_arch -eq 1 ]; then
        binary_uri="${alt_arch_base}/${version_path}/Everything/$basearch/os/repodata/"
    else
        binary_uri="${primary_arch_base}/${version_path}/Everything/$basearch/os/repodata/"
    fi

    dest_binaries="repo/${version_path}/frozen/$basearch/repodata"
    mkdir -p $dest_binaries

    # rsync the binary RPM repodata from mirrors.kernel.org
    echo "Downloading binary RPM repodata from $binary_uri"
    rsync -azh --no-motd --delete-before $binary_uri $dest_binaries

    # Pull down the current override repository repodata from
    # fedorapeople
    # This does not pull down the full contents, so if recreation
    # or modification of the repository is necessary, it must be
    # retrieved separately
    override_base="rsync://fedorapeople.org/project/modularity/repos/fedora/gencore-override/${version_path}/$basearch"
    override_source_uri="${override_base}/sources/repodata/"
    override_binary_uri="${override_base}/os/repodata/"

    dest_override=${_arg_repo_path}/repo/${version_path}/override/$basearch
    dest_override_sources=${dest_override}/sources/repodata
    dest_override_binaries=${dest_override}/os/repodata
    mkdir -p $dest_override_sources $dest_override_binaries

    echo "Downloading override source RPM repodata from $override_source_uri"
    rsync -azh --no-motd --delete-before \
        ${override_source_uri} ${dest_override_sources}

    echo "Downloading override binary RPM repodata from $override_binary_uri"
    rsync -azh --no-motd --delete-before \
        ${override_binary_uri} ${dest_override_binaries}
done

# ] <-- needed because of Argbash

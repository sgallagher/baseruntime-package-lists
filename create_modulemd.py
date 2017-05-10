#!/usr/bin/python2

import os
import sys
import click
import modulemd
import koji
import re

from collections import namedtuple
from multiprocessing import Process, JoinableQueue

NUM_PROCS = os.sysconf("SC_NPROCESSORS_ONLN")

ModuleContext = namedtuple("ModuleContext",
                           [
                               'arch',
                               'os',
                               'version',
                               'milestone',
                               'module',
                               'module_license',
                               'module_desc',
                               'module_deps',
                               'module_build_deps',
                               'community',
                               'docs',
                               'tracker',
                               'modulemd_file',
                               'bootstrap_modulemd_file',
                           ])

def _get_package_name_dict(shortfile, fullfile):
    with open(shortfile) as f:
        short_names = f.read().splitlines()
    with open(fullfile) as f:
        full_names = f.read().splitlines()
    pkg_name_dict = {k: v for k, v in zip(
        short_names, full_names)}

    return pkg_name_dict

def _populate_modulemd(module_ctx,
                       module_exclusive_packages,
                       include_module_bootstrap):
    mod_md = modulemd.ModuleMetadata()
    mod_md.name = str(module_ctx.module)
    mod_md.description = str(module_ctx.module_desc)
    for lic in module_ctx.module_license:
        mod_md.add_module_license(str(lic))
    mod_md.community = str(module_ctx.community)
    mod_md.documentation = str(module_ctx.docs)
    mod_md.tracker = str(module_ctx.tracker)

    # All modules require base runtime
    mod_md.add_requires("base-runtime", "master")
    for req in module_ctx.module_deps:
        mod_md.add_requires(str(req), "master")

    # All modules build-require bootstrap
    mod_md.add_buildrequires("bootstrap", "master")
    for req in module_ctx.module_build_deps:
        mod_md.add_buildrequires(str(req), "master")
    if include_module_bootstrap:
        mod_md.add_buildrequires("%s-bootstrap" % str(module_ctx.module),
                                 "master")

    nvr_re = re.compile("\d+\:(.*).src$")
    nvr_values = list()
    for srpm_name, srpm_nvr in module_exclusive_packages.items():
        match = nvr_re.match(srpm_nvr)
        if match:
            nvr_values.append(match.group(1))
        else:
            raise IOError("NVR [%s] didnt parse" % srpm_nvr)

    ks = koji.ClientSession('https://koji.fedoraproject.org/kojihub')
    ks.multicall = True
    for srpm_nvr in nvr_values:
        ks.getBuild(srpm_nvr)
    ret = ks.multiCall(strict=True)
    ks.multicall = True
    task_nvrs = []
    for i in range(len(nvr_values)):
        if ret[i][0] is not None:
            if ret[i][0]['task_id'] is not None:
                ks.getTaskInfo(ret[i][0]['task_id'], request=True)
                task_nvrs.append(nvr_values[i])
            else:
                print("WARNING: no task ID for %s" % nvrs[i])
        else:
            print("WARNING: no task ID for %s" % nvrs[i])

    ret = ks.multiCall(strict=True)

    deps = dict()
    commit_re = re.compile("([^\/]+?):([a-f0-9]{40})")
    for i in range(len(task_nvrs)):
        match = commit_re.search(koji.taskLabel(ret[i][0]))
        if match:
            deps[match.group(1)] = match.group(2)
        else:
            raise IOError("Task [%s] didnt parse" % (
                koji.taskLabel(ret[i][0])))

    for name in sorted(deps, key=deps.get):
        mod_md.components.add_rpm(name,
                                  "Automatically generated",
                                  ref=deps[name])

    return mod_md

def create_modulemd_worker(arch_queue):
    while True:
        try:
            module_ctx = arch_queue.get()
            if module_ctx is None:
                break

            print("Arch: %s" % module_ctx.arch)

            if module_ctx.os == 'Rawhide':
                br_base_path = "./data/Rawhide/base-runtime/%s/" % (
                                module_ctx.arch)
                module_base_path = "./data/Rawhide/%s/%s/" % (
                                    module_ctx.module,
                                    module_ctx.arch)

            elif module_ctx.milestone:
                br_base_path = "./data/%s/%d_%s/base-runtime/%s/" % (
                                module_ctx.os,
                                module_ctx.version,
                                module_ctx.milestone,
                                module_ctx.arch)
                module_base_path = "./data/%s/%d_%s/%s/%s/" % (
                                    module_ctx.os,
                                    module_ctx.version,
                                    module_ctx.milestone,
                                    module_ctx.module,
                                    module_ctx.arch)
            else:
                br_base_path = "./data/%s/%d/base-runtime/%s/" % (
                                module_ctx.os,
                                module_ctx.version,
                                module_ctx.arch)
                module_base_path = "./data/%s/%d/%s/%s/" % (
                                    module_ctx.os,
                                    module_ctx.version,
                                    module_ctx.module,
                                    module_ctx.arch)

            modulemd_file = "%s/%s" % (module_base_path,
                                       module_ctx.modulemd_file)
            bootstrap_modulemd_file = "%s/%s" % (module_base_path,
                                                 module_ctx.bootstrap_modulemd_file)

            # Read in the base runtime SRPMs into a dictionary of short->full names
            base_runtime_packages = _get_package_name_dict(
                "%s/runtime-source-packages-short.txt" % br_base_path,
                "%s/runtime-source-packages-full.txt" % br_base_path
            )

            # Read in the bootstrap SRPMs into a dictionary of short->full names
            bootstrap_packages = _get_package_name_dict(
                "%s/selfhosting-source-packages-short.txt" % br_base_path,
                "%s/selfhosting-source-packages-full.txt" % br_base_path
            )

            # Read in the module SRPMs into a dictionary of short->full names
            module_packages = _get_package_name_dict(
                "%s/runtime-source-packages-short.txt" % module_base_path,
                "%s/runtime-source-packages-full.txt" % module_base_path
            )

            # Read in the module bootstrap SRPMs into a dictionary of
            # short->full names
            module_bootstrap_packages = _get_package_name_dict(
                "%s/selfhosting-source-packages-short.txt" % module_base_path,
                "%s/selfhosting-source-packages-full.txt" % module_base_path
            )

            # Get the runtime packages needed only by the module
            module_exclusive_packages = {
                    short:full for short,full
                    in module_packages.items()
                    if short not in base_runtime_packages
                }

            # Get the self-hosting packages needed only by the module
            module_bootstrap_exclusive_packages = {
                    short:full for short, full
                    in module_bootstrap_packages.items()
                    if short not in bootstrap_packages
                }
            include_module_bootstrap = \
                len(module_bootstrap_exclusive_packages) > 0

            # Create the modulemd file for the module

            # Main section
            mod_md = _populate_modulemd(
                module_ctx, module_exclusive_packages,
                include_module_bootstrap)

            mod_md.dump(modulemd_file)

            # Create the modulemd file for the module-bootstrap if needed
            if include_module_bootstrap:
                mod_bs_ctx = ModuleContext(
                    arch=module_ctx.arch,
                    os=module_ctx.os,
                    version=module_ctx.version,
                    milestone=module_ctx.milestone,
                    module="%s-bootstrap" % module_ctx.module,
                    module_license=module_ctx.module_license,
                    module_desc="Bootstrap module for %s" % module_ctx.module,
                    module_deps=["bootstrap",],
                    module_build_deps=[],
                    community=module_ctx.community,
                    docs=module_ctx.docs,
                    tracker=module_ctx.tracker,
                    modulemd_file=module_ctx.modulemd_file,
                    bootstrap_modulemd_file=module_ctx.bootstrap_modulemd_file)
                mod_bs_md = _populate_modulemd(mod_bs_ctx,
                                               module_bootstrap_exclusive_packages,
                                               False)
                mod_bs_md.dump(bootstrap_modulemd_file)


        except Exception as e:
            print("Encountered an exception while processing %s: %s" % (
                   module_ctx.arch, e))
            arch_queue.task_done()
            raise

        arch_queue.task_done()

@click.command()
@click.option('--os', default='Fedora', show_default=True,
              help='What OS to process? ("Fedora", "Rawhide")')
@click.option('--version', required=True, type=int,
              help='What OS version to process?')
@click.option('--milestone', default=None,
              help='If processing a prerelease, which one?')
@click.option('--module', required=True,
              help='Name of the module to generate modulemd')
@click.option('--module-license', default=["MIT",], multiple=True,
              show_default=True,
              help='License(s) of the module')
@click.option('--module-desc', default="",
              help='Name of the module to generate modulemd')
@click.option('--module-deps', default=[], multiple=True,
              help='Other modules that this module depends on at runtime '
                   '(base-runtime is always assumed to be required)')
@click.option('--module-build-deps', default=[], multiple=True,
              help='Other modules that this module depends on to build '
                   '(bootstrap is always assumed to be required)')
@click.option('--community',
              default="https://fedoraproject.org/wiki/BaseRuntime",
              show_default = True,
              help="A link to the upstream community for this module")
@click.option('--docs',
              default="https://github.com/fedora-modularity/base-runtime",
              show_default = True,
              help="A link to the upstream documentation for this module")
@click.option('--tracker',
              default="https://github.com/fedora-modularity/base-runtime/issues",
              show_default = True,
              help="A link to the upstream bug tracker for this module")
@click.option('--modulemd-file', default=None, type=str,
              help="A file name for the modulemd output for the module. "
                   "It is always written to the data "
                   "directory (Default: modulename.yaml")
@click.option('--bootstrap-modulemd-file', default=None, type=str,
              help="A file name for the modulemd output for the bootstrap "
                   "module if needed. It is always written to the data "
                   "directory (Default: modulename-bootstrap.yaml")
def main(os, version, milestone,
         module, module_license, module_desc,
         module_deps, module_build_deps,
         community, docs, tracker,
         modulemd_file, bootstrap_modulemd_file):
    arch_queue = JoinableQueue()

    arches = ('x86_64', 'aarch64', 'i686', 'armv7hl', 'ppc64', 'ppc64le')

    if not modulemd_file:
        modulemd_file = "%s.yaml" % module

    if not bootstrap_modulemd_file:
        bootstrap_modulemd_file = "%s-bootstrap.yaml" % module

    processes = []
    # Create parallel processes for each architecture,  up to the limit of
    # processors on the system.
    for i in range(min(NUM_PROCS, len(arches))):
            worker = Process(target=create_modulemd_worker,
                             args=(arch_queue,))
            worker.daemon = True
            worker.start()
            processes.append(worker)

    # Enqueue all of the architectures
    for arch in arches:
        module_ctx = ModuleContext(arch=arch,
                                   os=os,
                                   version=version,
                                   milestone=milestone,
                                   module=module,
                                   module_license=module_license,
                                   module_desc=module_desc,
                                   module_deps=module_deps,
                                   module_build_deps=module_build_deps,
                                   community=community,
                                   docs=docs,
                                   tracker=tracker,
                                   modulemd_file=modulemd_file,
                                   bootstrap_modulemd_file=bootstrap_modulemd_file)
        arch_queue.put(module_ctx)

    # Wait for all the magic to happen
    arch_queue.join();

    # Terminate worker processes
    for i in range(min(NUM_PROCS, len(arches))):
        arch_queue.put(None);
    for worker in processes:
        worker.join()

if __name__ == "__main__":
    main()


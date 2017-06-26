#!/usr/bin/python3

import click
from os.path import basename
from pdc_client import PDCClient
import yaml
from datetime import date
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def get_modulemd(module_name, stream):
    """
    Check if module and stream are built successfully on PDC server
    """
    pdc_server = "https://pdc.fedoraproject.org/rest_api/v1/unreleasedvariants"
    #Using develop=True to not authenticate to the server
    pdc_session = PDCClient(pdc_server, ssl_verify=True, develop=True)
    pdc_query = dict(
        variant_id = module_name,
        variant_version = stream,
        fields="modulemd",
        ordering="variant_release",
        #active=True returns only succesful builds
        active = True,
    )
    try:
        mod_info = pdc_session(**pdc_query)
    except Exception as ex:
        raise IOError("Could not query PDC server for %s (stream: %s) - %s" % (
                       module_name, stream, ex))
    if not mod_info or "results" not in mod_info.keys() or not mod_info["results"]:
        raise IOError("%s (stream: %s) is not available on PDC" % (
                       module_name, stream))
    return yaml.load(mod_info["results"][-1]["modulemd"], Loader=Loader)

def _get_module_build_deps(name, ref, modulemd=None):
    if not modulemd:
        modulemd = get_modulemd(name, ref)
    try:
        module_deps = modulemd['data']['dependencies']['buildrequires']
    except KeyError:
        # This module has no dependencies
        return {}

    return module_deps

def _get_module_deps(name, ref, modulemd=None):
    if not modulemd:
        modulemd = get_modulemd(name, ref)
    try:
        module_deps = modulemd['data']['dependencies']['requires']
    except KeyError:
        # This module has no dependencies
        return {}

    return module_deps

def _get_recursive_module_deps(deps, name, ref):
    if name in deps and deps[name] == ref:
        return
    if name in deps and not deps['name'] == ref:
        raise TypeError("Conflicting refs for {}".format(name))

    deps[name] = ref

    module_deps = _get_module_deps(name, ref)

    for depname, depref in module_deps.items():
        _get_recursive_module_deps(deps, depname, depref)

@click.group()
@click.option('--module', default='base-runtime',
              help='The module to get the API from')
@click.option('--modulemd', default=None,
              help='Path to module metadata YAML on the local filesystem')
@click.option('--ref', default='f26',
              help='The ref of the module to retrieve')
@click.pass_context
def cli(ctx, module, modulemd, ref):
    if modulemd:
        with open(modulemd, 'r') as modulemd_file:
            ctx.obj["modulemd"] = yaml.load(open(modulemd, 'r'))
        try:
            ctx.obj["name"] = ctx.obj["modulemd"]['data']['name']
        except KeyError:
            # If the modulemd doesn't list the name, assume that the
            # filename does
            ctx.obj["name"] = basename(modulemd).rsplit('.', 1)[0]
    else:
        ctx.obj["modulemd"] = get_modulemd(module, ref)
        ctx.obj["name"] = module
    ctx.obj["ref"] = ref

@cli.command()
@click.pass_context
def get_api(ctx):
    for rpm in sorted(ctx.obj["modulemd"]['data']['api']['rpms']):
        print(rpm)

@cli.command()
@click.pass_context
def get_name(ctx):
    print(ctx.obj['name'])

@cli.command()
@click.option('--recursive/--no-recursive', default=True,
              help='Whether to get all of the dependencies of dependencies')
@click.pass_context
def get_deps(ctx, recursive):
    deps = _get_module_deps(ctx.obj["name"],
                            ctx.obj["ref"],
                            ctx.obj["modulemd"])

    if recursive:
        for depname, depref in deps.items():
            _get_recursive_module_deps(deps, depname, depref)

    for dep in sorted(deps):
        print("{}:{}".format(dep,deps[dep]))

@cli.command()
@click.pass_context
def get_build_deps(ctx):
    deps = _get_module_build_deps(ctx.obj["name"],
                                  ctx.obj["ref"],
                                  ctx.obj["modulemd"])

    # Get all the runtime dependencies for these build-deps
    for depname, depref in deps.items():
            _get_recursive_module_deps(deps, depname, depref)

    for dep in sorted(deps):
        print("{}:{}".format(dep,deps[dep]))

@cli.command()
@click.pass_context
def get_component_rpms(ctx):
    modulemd = ctx.obj["modulemd"]

    for pkg in modulemd['data']['components']['rpms'].keys():
        print(pkg)

@cli.command()
@click.pass_context
@click.argument('hash-file', nargs=1, type=click.File('r'))
@click.argument('output-file', nargs=1, type=click.File('w', atomic=True))
def update_module_hashes(ctx, hash_file, output_file):
    """
    Update the hashes in a modulemd

    The HASH_FILE must be in the format <pkgname>#<dist-git hash>, one per line
    """
    datestamp = date.today().isoformat()

    current_pkgs = []
    for line in hash_file:
        (pkgname, githash) = line.rstrip().split('#')
        current_pkgs.append(pkgname)
        try:
            old_hash = ctx.obj['modulemd']['data']['components']['rpms'][pkgname]['ref']
        except KeyError as e:
            print("DEBUG: Adding {}".format(e))
            # This package doesn't exist yet. Create it.
            ctx.obj['modulemd']['data']['components']['rpms'][pkgname] = dict(
                ref=githash,
                rationale="Added by Base Runtime tools on {}".format(datestamp)
                )
            old_hash = ctx.obj['modulemd']['data']['components']['rpms'][pkgname]['ref']

        if old_hash == githash:
            continue

        ctx.obj['modulemd']['data']['components']['rpms'][pkgname]['rationale'] = \
            "Autogenerated by Base Runtime tools on {}".format(datestamp)
        ctx.obj['modulemd']['data']['components']['rpms'][pkgname]['ref'] = \
            githash

    for pkg in ctx.obj['modulemd']['data']['components']['rpms'].keys():
        if pkg not in current_pkgs:
            print("DEBUG: {} in original modulemd but not in hash-file".format(pkg))

    output_file.write(yaml.dump(ctx.obj['modulemd'],
                                Dumper=Dumper,
                                default_flow_style=False))


@cli.command()
@click.argument('output-file', nargs=1, type=click.File('w', atomic=True))
def reflow_modulemd(hash_file, output_file):
    """
    Read in a modulemd and write it back out with standard PyYAML ordering and
    layout.
    """
    modulemd = yaml.load(hash_file, Loader=Loader)

    output_file.write(
        yaml.dump(
            modulemd,
            Dumper=Dumper,
            default_flow_style=False
        )
    )


def main():
    cli(obj={})


if __name__ == "__main__":
    main()

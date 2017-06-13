#!/usr/bin/python3

import click
from pdc_client import PDCClient
import yaml
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
        ctx.obj["modulemd"] = yaml.load(open(modulemd, 'r'))
        ctx.obj["name"] = ctx.obj["modulemd"]['data']['name']
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

def main():
    cli(obj={})


if __name__ == "__main__":
    main()

import os
import shutil
import requests
import zipfile
import StringIO

from paver.easy import *

def _install(folder):
    '''install plugin to qgis'''
    src = os.path.join(os.path.dirname(__file__), 'plugin', 'mapboxglplugin')
    dst = os.path.join(os.path.expanduser('~'),  folder, 'python', 'plugins', 'mapboxglplugin')
    shutil.rmtree(dst, True)
    shutil.copytree(src, dst)
    src = os.path.join(os.path.dirname(__file__), 'mapboxgl', 'mapboxgl.py')
    shutil.copy2(src, dst)
    src = os.path.join(os.path.dirname(__file__), 'mapboxgl', 'sampleapp')
    dst = os.path.join(os.path.expanduser('~'),  folder, 'python', 'plugins', 'mapboxglplugin', 'sampleapp')
    shutil.rmtree(dst, True)
    shutil.copytree(src, dst)

@task
def install(options):
    _install(".qgis2")

@task
def installdev(options):
    _install(".qgis-dev")

@task
def install3(options):
    _install(".qgis3")

@task
def setup(options):
    path = os.path.abspath("./ol-mapbox-style")
    if os.path.exists(path):
        shutil.rmtree(path)
    r = requests.get("https://api.github.com/repos/boundlessgeo/ol-mapbox-style/releases")
    zipurl = r.json()[0]["zipball_url"]
    r = requests.get(zipurl, stream=True)
    z = zipfile.ZipFile(StringIO.StringIO(r.content))
    z.extractall(path=path)
    subfolder = os.listdir(path)[0]
    shutil.copy2(os.path.join(path, subfolder, "dist", "olms.js"), "./mapboxgl/sampleapp/olms.js")
    shutil.rmtree(path)

@task
def install_devtools():
    """Install development tools
    """
    try:
        import pip
    except:
        error('FATAL: Unable to import pip, please install it first!')
        sys.exit(1)

    pip.main(['install', '-r', 'requirements-dev.txt'])


@task
@consume_args
def pep8(args):
    """Check code for PEP8 violations
    """
    try:
        import pep8
    except:
        error('pep8 not found! Run "paver install_devtools".')
        sys.exit(1)

    # Errors to ignore
    ignore = ['E203', 'E121', 'E122', 'E123', 'E124', 'E125', 'E126', 'E127',
        'E128', 'E402']
    styleguide = pep8.StyleGuide(ignore=ignore,
                                 exclude=['*/ext-libs/*', '*/ext-src/*'],
                                 repeat=True, max_line_length=79,
                                 parse_argv=args)
    styleguide.input_dir(options.plugin.source_dir)
    info('===== PEP8 SUMMARY =====')
    styleguide.options.report.print_statistics()


@task
@consume_args
def autopep8(args):
    """Format code according to PEP8
    """
    try:
        import autopep8
    except:
        error('autopep8 not found! Run "paver install_devtools".')
        sys.exit(1)

    if any(x not in args for x in ['-i', '--in-place']):
        args.append('-i')

    args.append('--ignore=E261,E265,E402,E501')
    args.insert(0, 'dummy')

    cmd_args = autopep8.parse_args(args)

    excludes = ('ext-lib', 'ext-src')
    for p in options.plugin.source_dir.walk():
        if any(exclude in p for exclude in excludes):
            continue

        if p.fnmatch('*.py'):
            autopep8.fix_file(p, options=cmd_args)


@task
@consume_args
def pylint(args):
    """Check code for errors and coding standard violations
    """
    try:
        from pylint import lint
    except:
        error('pylint not found! Run "paver install_devtools".')
        sys.exit(1)

    if not 'rcfile' in args:
        args.append('--rcfile=pylintrc')

    args.append(options.plugin.source_dir)
    lint.Run(args)

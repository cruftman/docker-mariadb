#!/usr/bin/env python3

import sys
import os
import re
import argparse
import shutil
##import tarfile
##import tempfile
import string
import types


class Template(string.Template):
    pattern = r"""
    (?ai)(?P<delimiter>@)(?:
        (?P<escaped>@)   |
        (?:(?P<braced>(?P<named>[_a-z][_a-z0-9]*))@)    |
        (?P<invalid>)
    )"""
    delimiter = '@'


class ConfigError(Exception): pass

class ConfigChecker:
    def __init__(self, filename='-', **kw):
        self.filename = filename
        self.required = set(kw.get('required', ())) | set(('contexts',))

    def _check_isa(self, value, types, name):
        if not isinstance(value, types):
            if not isinstance(types, tuple):
                expected = types.__name__
            elif len(types) > 1:
                expected = [t.__name__ for t in types]
                expected = ', '.join(expected[:-1]) + ' or ' + expected[-1]
            elif len(types) == 1:
                expected = t[0].__name__
            actual = repr(value)
            if len(actual) > 40:   # prefer short messages
                actual = type(value).__name__
            raise ConfigError("%s: %s must be of type %s, %s is not allowed" %
                              (self.filename, name, expected, actual))
        return True

    def _check_files(self, files, name):
        self._check_isa(files, dict, name)
        for infile, outfile in files.items():
            self._check_isa(infile, str, "any key in " + name)
            self._check_isa(outfile, str, name + ("['%s']" % infile))
            if os.path.isabs(outfile):
                raise ConfigError(("%s: %s['%s'] must be a relative " +
                                   "path, '%s' is absolute") %
                                  (self.filename, name, infile, outfile))

    def _check_subst(self, subst, name):
        self._check_isa(subst, dict, name)
        for k, v in subst.items():
            self._check_isa(k, str, "any key in " + name)
            if not re.match(r'^[_a-z][_a-z0-9]*$', k, re.I | re.A):
                raise ConfigError(("%s: any key in %s must be an " +
                                   "identifier, '%s' is not") %
                                  (self.filename, name, k))

    def _check_dir(self, dir, name):
        self._check_isa(dir, str, name)

    def check_context(self, context, index):
        c_i = 'contexts[%d]' % index
        self._check_isa(context, dict, c_i)
        for k in ('dir', 'files', 'subst'):
            if k not in context:
                raise ConfigError("%s: missing key '%s' in %s" %
                                  (self.filename, k, c_i))
        self._check_files(context['files'], c_i + "['files']")
        self._check_subst(context['subst'], c_i + "['subst']")
        self._check_dir(context['dir'], c_i + "['dir']")

    def check_contexts(self, contexts):
        self._check_isa(contexts, (list, tuple), "contexts")
        for index, context in enumerate(contexts):
            self.check_context(context, index)
        return True

    def check_required(self, config):
        for key in self.required:
            if key not in config:
                raise ConfigError("%s: missing required variable '%s'"
                                  % (self.filename, key))
        return True

    def check_global(self, config):
        if 'files' in config:
            self._check_files(config['files'], 'files')
        if 'subst' in config:
            self._check_subst(config['subst'], 'subst')
        if 'dir' in config:
            self._check_dir(config['dir'], 'dir')

    def check(self, config):
        self.check_required(config)
        self.check_global(config)
        self.check_contexts(config['contexts'])
        return True


class ConfigParser:
    # Internal variables, not interesting, not a part of config
    internal = ['__builtins__']
    defaults = {'files': dict(), 'subst': dict(), 'dir': '.'}

    def __init__(self, filename='-'):
        self.filename = filename

    def qualify_name(self, name):
        return name not in self.internal

    def qualify_value(self, value):
        if isinstance(value, (types.FunctionType, types.ModuleType)):
            return False
        return True

    def qualify_variable(self, name, value):
        return self.qualify_name(name) and self.qualify_value(value)

    def cleanup(self, config):
        return {k: v for k, v in config.items() if self.qualify_variable(k, v)}

    def parse(self, content):
        config = dict(self.defaults)
        exec(compile(content, self.filename, 'exec'), config)
        return self.cleanup(config)


class Config(dict):
    @classmethod
    def from_string(cls, string, filename=None):
        config = ConfigParser(filename).parse(string)
        ConfigChecker(filename).check(config)
        return cls(config, filename)

    @classmethod
    def from_file(cls, file, mode='r', *args, **kw):
        """Read config from a file. Return new Config instance."""
        filename = file if isinstance(file, str) else file.name
        if isinstance(file, str):
            with open(filename, mode, *args, **kw) as file:
                source = file.read()
        else:
            source = file.read()
        return cls.from_string(source, filename)

    def __init__(self, config, filename=None):
        super().__init__(config)
        self.filename = filename

    def copy(self):
        return self.__class__(super().copy(), self.filename)


class Updater:
    def __init__(self, config, **kw):
        self.config = config
        self._init_attrs(kw)
        # self._init_dict(config)

    def run(self):
        self._update_dir(self.config)
        if self.delete:
            self._delete_dirs(self.config['contexts'])
        self._update_dirs(self.config['contexts'])
        return 0

    def _get_destdir(self, destdir):
        if not os.path.isabs(destdir):
            destdir = os.path.join(self.outdir, destdir)
        return destdir

    def _delete_dirs(self, contexts):
        for context in contexts:
            self._delete_dir(context)

    def _update_dirs(self, contexts):
        for context in contexts:
            self._update_dir(context)

    def _delete_dir(self, context):
        destdir = self._get_destdir(context['dir'])
        if os.path.exists(destdir):
            if not self.quiet:
                print("deleting directory: %s" % destdir)
            shutil.rmtree(destdir)

    def _update_dir(self, context):
        if not self.quiet:
            print("updating directory: %s" % context['dir'])
        self._update_files(context)

    def _update_files(self, context):
        for infile, outfile in context['files'].items():
            self._update_file(context, infile, outfile)

    def _update_file(self, context, infile, outfile):
        if not os.path.isabs(infile):
            infile = os.path.join(self.indir, infile)
        if not os.path.isabs(outfile):
            destdir = self._get_destdir(context['dir'])
            outfile = os.path.join(destdir, outfile)
        if os.path.normpath(infile) == os.path.normpath(outfile):
            f = os.path.normpath(infile)
            raise RuntimeError("can't use '%s' as both, input and output" % f)
        outdir = os.path.dirname(outfile)
        if not os.path.exists(outdir):
            os.makedirs(outdir, mode=0o755)
        with open(infile, 'r') as ifp:
            with open(outfile, 'w') as ofp:
                if not self.quiet:
                    print("  %s -> %s" % (infile, outfile))
                ofp.write(Template(ifp.read()).substitute(context['subst']))
        shutil.copymode(infile, outfile)

    def _init_attrs(self, kw):
        self.indir = kw.get('indir', '.')
        self.outdir = kw.get('outdir', '.')
        self.delete = kw.get('delete', False)
        self.quiet = kw.get('quiet', False)


class App:
    @classmethod
    def create_argparser(cls):
        here = os.path.dirname(__file__)
        config = os.path.join(here, 'config.py')
        description = 'Regenerate files in docker context directories'
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument('--config', '-c',
                            metavar='FILE',
                            dest='config_file',
                            type=argparse.FileType('r'),
                            help='config file', default=config)
        parser.add_argument('--delete',
                            dest='delete',
                            action='store_true',
                            help='delete existing context direcotries')
        parser.add_argument('--indir', '-i',
                            dest='indir',
                            metavar='DIR',
                            default='.',
                            help='Input directory, defaults to "."')
        parser.add_argument('--quiet', '-q',
                            dest='quiet',
                            action='store_true',
                            help='Do not print messages')
        parser.add_argument('--outdir', '-o',
                            dest='outdir',
                            metavar='DIR',
                            default='.',
                            help='Output directory, defaults to "."')
        return parser

    def __init__(self):
        self.argparser = self.create_argparser()

    def run(self):
        self.args = self.argparser.parse_args()
        try:
            config = Config.from_file(self.args.config_file)
        except ConfigError as e:
            sys.stderr.write("error: %s\n" % str(e))
            return 1
        finally:
            self.args.config_file.close()
        return Updater(config, **vars(self.args)).run()


if __name__ == '__main__':
    sys.exit(App().run())

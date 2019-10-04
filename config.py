import itertools

__version__ = '0.1.1'

def xrepr(arg):
    if isinstance(arg, str):
        return "'%s'" % arg
    else:
        return repr(arg)


def get_generated_warning():
    return """\
#############################################################################
# NOTE: FILE GENERATED AUTOMATICALLY, DO NOT EDIT!!!
#############################################################################
"""


def get_params(db, os):
    """Configuration parameters for mariadb with their default values"""
    return dict()


def get_env_defaults_str(db, os):
    items = get_params(db, os).items()
    return '\n'.join(("DEFAULT_%s=%s" % (k, xrepr(v)) for k, v in items))


def get_env_settings_str(db, os):
    params = list(get_params(db, os))
    return '\n'.join(('%s=${%s-$DEFAULT_%s}' % (k, k, k) for k in params))


def get_docker_args_str(db, os):
    items = get_params(db, os).items()
    if len(items) == 0: return ''
    return '\n'.join(('ARG %s=%s' % (k, xrepr(v)) for k, v in items))


def get_docker_env_str(db, os):
    params = list(get_params(db, os))
    if len(params) == 0: return ''
    return 'ENV ' + ' \\\n    '.join(('%s=$%s' % (k, k) for k in params))


def get_context_dir(db, os, sep='/'):
    return sep.join([x for x in [db, os] if x is not None])


def get_tag(db=None, os=None, sep='-'):
    return sep.join([x for x in [db, os] if x is not None])


def get_tag_aliases(db, os):
    aliases = []
    maj = db.split('.')[0]
    # group of existing db versions with same major version
    mg = [v for v in dbs() if v.split('.')[0] == maj]

    if db == mg[-1]:
        aliases.append(get_tag(maj, os))

    if oses()[-1] == os:
        aliases.append(get_tag(db, None))

    if dbs()[-1] == db:
        aliases.append(get_tag(None, os))

    if db == mg[-1] and oses()[-1] == os:
        aliases.append(get_tag(maj, None))

    if dbs()[-1] == db and oses()[-1] == os:
        aliases.append(get_tag('latest'))

    return aliases


def get_tags(db, os):
    return [get_tag(db, os)] + get_tag_aliases(db, os)


def get_context_files(db, os):
    return {'Dockerfile.in': 'Dockerfile',
            'hooks/build.in': 'hooks/build',
            'README.md.in': 'README.md'}


def get_microbadges_str_for_tag(tag):
    name = 'cruftman/mariadb:%(tag)s' % locals()
    url1 = 'https://images.microbadger.com/badges'
    url2 = 'https://microbadger.com/images/%(name)s' % locals()
    return "\n".join([
        '[![](%(url1)s/version/%(name)s.svg)](%(url2)s "%(name)s")' % locals(),
        '[![](%(url1)s/image/%(name)s.svg)](%(url2)s "Docker image size")' % locals(),
        '[![](%(url1)s/commit/%(name)s.svg)](%(url2)s "Source code")' % locals()
  ])


def get_microbadges_str_for_tags(tags):
    return '- ' + "\n- ".join(reversed([get_microbadges_str_for_tag(tag) for tag in tags]))


def get_microbadges_str(matrix):
    #seen = set([])
    lines = []
    for (db, os) in reversed(matrix):
        lines.append("")
        lines.append("### %s" % get_tag(db, os))
        lines.append("")
        tag = get_tag(db, os)
        lines.append(get_microbadges_str_for_tag(tag))
        aliases = get_tag_aliases(db, os)
        if aliases:
            lines.append("")
            lines.append("- **aliases**: %s" % ', '.join(aliases))
            lines.append("")
        #tags = get_tags(db, os)
        #lines.append(get_microbadges_str_for_tags(tags))
    return "\n".join(lines)


def get_circle_job_name(db, os):
    return "build_%s_%s" % (db.replace('.','_'), os)


def get_circle_jobs_str(matrix):
    jobs = []
    for m in matrix:
        db, os = m
        s = "\n  ".join([
            "%s:" % get_circle_job_name(db, os),
            "  <<: *executor",
            "  environment:",
            "    <<: *env_common",
            "    DOCKERFILE_PATH: %s" % get_context_dir(db, os),
            "    IMAGE_NAME: cruftman/mariadb:%s" % get_tag(db, os),
            "    DOCKER_TAG: %s" % (','.join(get_tags(db, os))),
            "  <<: *build_steps"
            ])
        jobs.append(s)
    return "\n\n  ".join(jobs)


def get_circle_workflow_jobs_str(matrix):
    lines = []
    for (db, os) in matrix:
        lines.append("- %s:" % get_circle_job_name(db, os))
        lines.append("    context: cruftman-docker")
    return "\n      ".join(lines)


def get_common_subst():
    matrix = get_matrix()
    return dict({ 'MICROBADGES' : get_microbadges_str(matrix),
                  'GENERATED_WARNING' : get_generated_warning(),
                  'VERSION': __version__ })


def get_context_subst(db, os):
    return dict(get_common_subst(), **dict({
            'MARIADB_ENV_DEFAULTS': get_env_defaults_str(db, os),
            'MARIADB_ENV_SETTINGS': get_env_settings_str(db, os),
            'DOCKER_FROM_TAG': get_tag(db, os),
            'DOCKER_MARIADB_ARGS': get_docker_args_str(db, os),
            'DOCKER_MARIADB_ENV': get_docker_env_str(db, os)
        }, **get_params(db, os)))


def get_global_subst():
    matrix = get_matrix()
    return dict(get_common_subst(), **dict({
            'CIRCLE_JOBS': get_circle_jobs_str(matrix),
            'CIRCLE_WORKFLOW_JOBS': get_circle_workflow_jobs_str(matrix)
        }))


def get_context(db, os):
    return {'dir': get_context_dir(db, os),
            'files': get_context_files(db, os),
            'subst': get_context_subst(db, os)}


def is_excluded(t):
    return len(set([t[:1], t]) & set(exclusions())) > 0


def get_matrix():
    return [t for t in itertools.product(dbs(), oses()) if not is_excluded(t)]


def get_contexts():
    return [get_context(db, os) for (db, os) in get_matrix()]


# Keep this list sorted (from the oldest version to the latest version)!
def dbs():
    return [ '10.3', '10.4' ]


# Keep this list sorted (from the oldest version to the latest version)!
def oses():
    return [ 'bionic' ]


def exclusions():
    return [
    ]

contexts = get_contexts()
files = { '.circleci/config.yml.in': '.circleci/config.yml',
          '.circleci/upload.in': '.circleci/upload',
          'README.md.in': 'README.md' }
subst = get_global_subst()

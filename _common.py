import sys
import subprocess


def info(msg):
    sys.stdout.write('* {}\n'.format(msg))
    sys.stdout.flush()


def error(msg):
    sys.stderr.write('* {}\n'.format(msg))
    sys.stderr.flush()
    sys.exit(1)


def run_command(cmd, env=None):
    try:
        subprocess.check_call(cmd, env=env)
    except subprocess.CalledProcessError:
        error('Command failed: {}'.format(' '.join(cmd)))

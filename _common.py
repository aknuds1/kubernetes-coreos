import sys


def info(msg):
    sys.stdout.write('* {}\n'.format(msg))
    sys.stdout.flush()


def error(msg):
    sys.stderr.write('* {}\n'.format(msg))
    sys.stderr.flush()
    sys.exit(1)

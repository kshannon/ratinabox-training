"""nbstripout, but silent when git closes the pipe.

Why this exists
---------------
`.gitattributes` runs every `.ipynb` through nbstripout as a git clean filter, so
anything git reads (`git status`, `git diff`, a git-aware shell prompt) spawns a
filter process per notebook.

If the reader goes away before the filter finishes writing, the filter's stdout
closes. Python sets SIGPIPE to SIG_IGN, so instead of dying quietly the write
raises BrokenPipeError and nbstripout dumps a traceback straight into the
terminal. It looks like a crash. Nothing is actually wrong, and the notebook is
never damaged, but the noise is alarming and it fires at unpredictable moments.

The usual trigger here is the Starship prompt: it runs git status on every prompt
and kills it at `command_timeout`. Big notebooks (stored figure outputs) make the
filter slow enough to get killed part way through.

Restoring the default SIGPIPE disposition makes this process behave like any
other Unix stream filter: if the consumer stops reading, exit quietly.

Usage
-----
Installed as the clean filter (see README). Equivalent to `python -m nbstripout`
in every other respect, so it can be swapped back out at any time:

    git config filter.nbstripout.clean \\
        "<path-to-python> -m nbstripout"
"""

import signal
import sys

# Must happen before any writing. SIG_DFL means the kernel terminates us on a
# closed pipe rather than raising BrokenPipeError in Python.
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    # No SIGPIPE on Windows, and it cannot be set off the main thread.
    pass

from nbstripout._nbstripout import main  # noqa: E402  (import after signal setup)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # Belt and braces: if the pipe breaks somewhere Python still surfaces as
        # an exception, exit the way a filter should instead of printing a trace.
        try:
            sys.stderr.close()
        finally:
            sys.exit(0)

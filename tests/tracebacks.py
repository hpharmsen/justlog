"""Echte tracebacks met de bestandspaden van drie gemelde productiefouten.

De frames komen uit electudetranslate #00089, #00092 en #00093. Ze staan hier
vastgelegd omdat issues naar `closed/` verhuizen en een vast pad naar een
issue-map dus verloopt; zonder deze fixture is het bewijs voor de
frame-selectie niet herhaalbaar te controleren.

De tracebacks worden echt opgewekt, niet als tekst nagebouwd: `compile()` neemt
een willekeurige bestandsnaam aan, dus een geketende reeks gecompileerde
functies levert een traceback op waar `traceback.extract_tb` net zo overheen
loopt als in productie. Een tekstuele fixture zou de extractie zelf overslaan,
en dat is precies het stuk dat we testen.
"""
from __future__ import annotations

HEROKU_LIB = '/app/.heroku/python/lib/python3.13/site-packages'

# (bestandspad, functienaam), van buiten naar binnen.
TB_00089 = [
    (f'{HEROKU_LIB}/django/core/handlers/base.py', '_get_response'),
    (f'{HEROKU_LIB}/django/contrib/auth/decorators.py', '_view_wrapper'),
    (f'{HEROKU_LIB}/django/utils/functional.py', '_setup'),
    (f'{HEROKU_LIB}/django/contrib/auth/middleware.py', 'get_user'),
    (f'{HEROKU_LIB}/django/db/backends/base/base.py', 'ensure_connection'),
    (f'{HEROKU_LIB}/django/db/backends/base/base.py', 'connect'),
    (f'{HEROKU_LIB}/django/db/backends/postgresql/base.py', 'get_new_connection'),
    (f'{HEROKU_LIB}/psycopg2/__init__.py', 'connect'),
]
MSG_00089 = ('connection to server at "cah8ha8ra8h8i7.cluster-czz5s0kz4scl.eu-west-1.rds.amazonaws.com" '
             '(34.253.23.204), port 5432 failed: FATAL: too many connections for role "uaclmp4r0m67pj"')

TB_00092 = [
    ('/app/apps/automate/management/commands/run_translation_worker.py', 'handle'),
    ('/app/apps/automate/management/commands/run_translation_worker.py', '_recover_stale_sessions'),
    (f'{HEROKU_LIB}/django/db/models/query.py', '__iter__'),
    (f'{HEROKU_LIB}/django/db/models/sql/compiler.py', 'execute_sql'),
    (f'{HEROKU_LIB}/django/db/backends/base/base.py', 'ensure_connection'),
    (f'{HEROKU_LIB}/django/db/backends/postgresql/base.py', 'get_new_connection'),
    (f'{HEROKU_LIB}/psycopg2/__init__.py', 'connect'),
]
MSG_00092 = ('connection to server at "cah8ha8ra8h8i7.cluster-czz5s0kz4scl.eu-west-1.rds.amazonaws.com" '
             '(34.253.23.204), port 5432 failed: Connection refused\n'
             '\tIs the server running on that host and accepting TCP/IP connections?')

TB_00093 = [
    ('/app/apps/automate/management/commands/run_translation_worker.py', 'handle'),
    ('/app/apps/automate/management/commands/run_translation_worker.py', '_recover_stale_sessions'),
    (f'{HEROKU_LIB}/django/db/models/query.py', '__iter__'),
    (f'{HEROKU_LIB}/django/db/models/sql/compiler.py', 'execute_sql'),
    (f'{HEROKU_LIB}/django/db/backends/utils.py', 'execute'),
    (f'{HEROKU_LIB}/django/db/backends/utils.py', '_execute'),
]
MSG_00093 = 'SSL SYSCALL error: EOF detected'


def _compiled(filename: str, func: str, body: str, namespace: dict):
    """Een functie met een opgegeven bestandsnaam, zonder tussenliggend frame.

    De aangeroepen functie komt uit de globals van de gecompileerde code, niet
    uit een lambda eromheen: elke lambda zou een extra frame uit dit bestand in
    de traceback zetten, en dit bestand telt als eigen code.
    """
    code = compile(f'def {func}():\n    {body}\n', filename, 'exec')
    exec(code, namespace)
    return namespace[func]


def exc_info_for(frames: list[tuple[str, str]], exc: BaseException):
    """`exc_info`-tuple met een echte traceback door precies `frames`.

    De traceback bevat uitsluitend de opgegeven frames. Het frame van deze
    functie zelf wordt eraf gehaald met `tb_next`, anders zou `tests/` als
    eigen code meetellen en zou de traceback van #00089 geen zuiver
    library-geval meer zijn.
    """
    import sys

    filename, func = frames[-1]
    call = _compiled(filename, func, 'raise _exc', {'_exc': exc})
    for filename, func in reversed(frames[:-1]):
        call = _compiled(filename, func, '_next()', {'_next': call})

    try:
        call()
    except BaseException:
        exc_type, exc_value, tb = sys.exc_info()
        return exc_type, exc_value, tb.tb_next
    raise AssertionError('exception is niet doorgekomen')

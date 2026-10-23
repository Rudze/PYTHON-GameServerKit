"""The gameplay modules. Importing a module registers its messages (@handler): to add one, write
server/modules/my_module.py and import it here (see doc/*/extending.md)."""
from server.modules import character, chat, movement   # noqa: F401
from server.modules.inventory import handlers   # noqa: F401

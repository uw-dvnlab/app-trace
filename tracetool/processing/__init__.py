import os
import pkgutil
import importlib

# Automatically import all modules in this package to trigger registration
# Exclude channel_utils to avoid circular import with utils.signal_processing
package_dir = os.path.dirname(__file__)
for _, module_name, _ in pkgutil.iter_modules([package_dir]):
    if module_name not in ("base", "registry", "channel_utils", "__init__"):
        importlib.import_module(f".{module_name}", __name__)

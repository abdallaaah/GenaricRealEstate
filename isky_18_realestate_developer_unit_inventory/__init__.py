from . import models
from . import wizard

# Phase 7: the config-parameter rename used by migrations/18.0.1.1/pre-migrate.py
from .hooks import rename_config_parameters

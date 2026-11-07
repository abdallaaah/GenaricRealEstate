from . import models
from . import wizard
from . import controllers

# #49: the stage-xmlid adoption used by migrations/18.0.1.1/pre-migrate.py
from .hooks import adopt_legacy_stage_xmlids

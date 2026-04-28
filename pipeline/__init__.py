"""Public API for the M&A extraction pipeline package."""

import sys
from types import ModuleType

from . import core as _core
from .core import *  # noqa: F401,F403


def __getattr__(name):
    return getattr(_core, name)


class _PipelineModule(ModuleType):
    def __setattr__(self, name, value):
        if hasattr(_core, name):
            setattr(_core, name, value)
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _PipelineModule

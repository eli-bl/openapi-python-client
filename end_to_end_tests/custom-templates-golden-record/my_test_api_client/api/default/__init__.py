"""Contains methods for accessing the API Endpoints"""

import types

from . import get_common_parameters, get_models_allof, post_common_parameters, reserved_parameters


class DefaultEndpoints:
    @classmethod
    def get_common_parameters(cls) -> types.ModuleType:
        return get_common_parameters

    @classmethod
    def post_common_parameters(cls) -> types.ModuleType:
        return post_common_parameters

    @classmethod
    def reserved_parameters(cls) -> types.ModuleType:
        return reserved_parameters

    @classmethod
    def get_models_allof(cls) -> types.ModuleType:
        return get_models_allof

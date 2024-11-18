from __future__ import annotations

from itertools import chain
from typing import Any, ClassVar, cast

from attr import define, evolve

from openapi_python_client.parser.properties.has_named_class import HasNamedClass
from openapi_python_client.schema.openapi_schema_pydantic.reference import Reference
from openapi_python_client.schema.openapi_schema_pydantic.schema import Schema

from ... import Config
from ... import schema as oai
from ...utils import PythonIdentifier
from ..errors import ParseError, PropertyError
from .protocol import PropertyProtocol, Value
from .schemas import Schemas


@define
class UnionProperty(PropertyProtocol):
    """A property representing a Union (anyOf) of other properties"""

    name: str
    required: bool
    default: Value | None
    python_name: PythonIdentifier
    description: str | None
    example: str | None
    inner_properties: list[PropertyProtocol]
    template: ClassVar[str] = "union_property.py.jinja"

    @classmethod
    def build(
        cls, *, data: oai.Schema, name: str, required: bool, schemas: Schemas, parent_name: str, config: Config
    ) -> tuple[UnionProperty | PropertyError, Schemas]:
        """
        Create a `UnionProperty` the right way.

        Args:
            data: The `Schema` describing the `UnionProperty`.
            name: The name of the property where it appears in the OpenAPI document.
            required: Whether this property is required where it's being used.
            schemas: The `Schemas` so far describing existing classes / references.
            parent_name: The name of the thing which holds this property (used for renaming inner classes).
            config: User-defined config values for modifying inner properties.

        Returns:
            `(result, schemas)` where `schemas` is the updated version of the input `schemas` and `result` is the
                constructed `UnionProperty` or a `PropertyError` describing what went wrong.
        """
        from . import property_from_data

        type_list_data = []
        if isinstance(data.type, list) and not (data.anyOf or data.oneOf):
            # The schema specifies "type:" with a list of allowable types. If there is *not* also an "anyOf"
            # or "oneOf", then we should treat that as a shorthand for a oneOf where each variant is just
            # a single "type:". For example:
            #   {"type": ["string", "int"]} becomes
            #   {"oneOf": [{"type": "string"}, {"type": "int"}]}
            # However, if there *is* also an "anyOf" or "oneOf" list, then the information from "type:" is
            # redundant since every allowable variant type is already fully described in the list.
            for _type in data.type:
                type_list_data.append(data.model_copy(update={"type": _type, "default": None}))
                # Here we're copying properties from the top-level union schema that might apply to one
                # of the type variants, like "format" for a string. But we don't copy "default" because
                # default values will be handled at the top level by the UnionProperty.

        def process_items(
            use_original_name_for: oai.Schema | oai.Reference | None = None,
        ) -> tuple[list[PropertyProtocol] | PropertyError, Schemas]:
            props: list[PropertyProtocol] = []
            new_schemas = schemas
            schemas_with_classes: list[oai.Schema | oai.Reference] = []
            for i, sub_prop_data in enumerate(chain(data.anyOf, data.oneOf, type_list_data)):
                sub_prop_name = name if sub_prop_data is use_original_name_for else f"{name}_type_{i}"
                sub_prop, new_schemas = property_from_data(
                    name=sub_prop_name,
                    required=True,
                    data=sub_prop_data,
                    schemas=new_schemas,
                    parent_name=parent_name,
                    config=config,
                )
                if isinstance(sub_prop, PropertyError):
                    return PropertyError(detail=f"Invalid property in union {name}", data=sub_prop_data), new_schemas
                if isinstance(sub_prop, HasNamedClass):
                    schemas_with_classes.append(sub_prop_data)
                props.append(sub_prop)

            if (not use_original_name_for) and len(schemas_with_classes) == 1:
                # An example of this scenario is a oneOf where one of the variants is an inline enum or
                # model, and the other is a simple value like null. If the name of the union property is
                # "foo" then it's desirable for the enum or model class to be named "Foo", not "FooType1".
                # So, we'll do a second pass where we tell ourselves to use the original property name
                # for that item instead of "{name}_type_{i}".
                # This only makes a functional difference if the variant was an inline schema, because
                # we wouldn't be generating a class otherwise, but even if it wasn't inline this will
                # save on pointlessly long variable names inside from_dict/to_dict.
                return process_items(use_original_name_for=schemas_with_classes[0])

            return props, new_schemas

        sub_properties, schemas = process_items()
        if isinstance(sub_properties, PropertyError):
            return sub_properties, schemas

        def flatten_union_properties(sub_properties: list[PropertyProtocol]) -> list[PropertyProtocol]:
            flattened = []
            for sub_prop in sub_properties:
                if isinstance(sub_prop, UnionProperty):
                    flattened.extend(flatten_union_properties(sub_prop.inner_properties))
                else:
                    flattened.append(sub_prop)
            return flattened

        sub_properties = flatten_union_properties(sub_properties)

        prop = UnionProperty(
            name=name,
            required=required,
            default=None,
            inner_properties=sub_properties,
            python_name=PythonIdentifier(value=name, prefix=config.field_prefix),
            description=data.description,
            example=data.example,
        )
        default_or_error = prop.convert_value(data.default)
        if isinstance(default_or_error, PropertyError):
            default_or_error.data = data
            return default_or_error, schemas
        prop = evolve(prop, default=default_or_error)
        return prop, schemas

    def convert_value(self, value: Any) -> Value | None | PropertyError:
        if value is None or isinstance(value, Value):
            return None
        value_or_error: Value | PropertyError | None = PropertyError(
            detail=f"Invalid default value for union {self.name}"
        )
        for sub_prop in self.inner_properties:
            value_or_error = sub_prop.convert_value(value)
            if not isinstance(value_or_error, PropertyError):
                return value_or_error
        return value_or_error

    def _get_inner_type_strings(self, json: bool, multipart: bool) -> set[str]:
        return {
            p.get_type_string(no_optional=True, json=json, multipart=multipart, quoted=not p.is_base_type)
            for p in self.inner_properties
        }

    @staticmethod
    def _get_type_string_from_inner_type_strings(inner_types: set[str]) -> str:
        if len(inner_types) == 1:
            return inner_types.pop()
        return f"Union[{', '.join(sorted(inner_types))}]"

    def get_base_type_string(self, *, quoted: bool = False) -> str:
        return self._get_type_string_from_inner_type_strings(self._get_inner_type_strings(json=False, multipart=False))

    def get_base_json_type_string(self, *, quoted: bool = False) -> str:
        return self._get_type_string_from_inner_type_strings(self._get_inner_type_strings(json=True, multipart=False))

    def get_type_strings_in_union(self, *, no_optional: bool = False, json: bool, multipart: bool) -> set[str]:
        """
        Get the set of all the types that should appear within the `Union` representing this property.

        This function is called from the union property macros, thus the public visibility.

        Args:
            no_optional: Do not include `None` or `Unset` in this set.
            json: If True, this returns the JSON types, not the Python types, of this property.
            multipart: If True, this returns the multipart types, not the Python types, of this property.

        Returns:
            A set of strings containing the types that should appear within `Union`.
        """
        type_strings = self._get_inner_type_strings(json=json, multipart=multipart)
        if no_optional:
            return type_strings
        if not self.required:
            type_strings.add("Unset")
        return type_strings

    def get_type_string(
        self,
        no_optional: bool = False,
        json: bool = False,
        *,
        multipart: bool = False,
        quoted: bool = False,
    ) -> str:
        """
        Get a string representation of type that should be used when declaring this property.
        This implementation differs slightly from `Property.get_type_string` in order to collapse
        nested union types.
        """
        type_strings_in_union = self.get_type_strings_in_union(no_optional=no_optional, json=json, multipart=multipart)
        return self._get_type_string_from_inner_type_strings(type_strings_in_union)

    def get_imports(self, *, prefix: str) -> set[str]:
        """
        Get a set of import strings that should be included when this property is used somewhere

        Args:
            prefix: A prefix to put before any relative (local) module names. This should be the number of . to get
            back to the root of the generated client.
        """
        imports = super().get_imports(prefix=prefix)
        for inner_prop in self.inner_properties:
            imports.update(inner_prop.get_imports(prefix=prefix))
        imports.add("from typing import cast, Union")
        return imports

    def get_lazy_imports(self, *, prefix: str) -> set[str]:
        lazy_imports = super().get_lazy_imports(prefix=prefix)
        for inner_prop in self.inner_properties:
            lazy_imports.update(inner_prop.get_lazy_imports(prefix=prefix))
        return lazy_imports

    def validate_location(self, location: oai.ParameterLocation) -> ParseError | None:
        """Returns an error if this type of property is not allowed in the given location"""
        from ..properties import Property

        for inner_prop in self.inner_properties:
            if evolve(cast(Property, inner_prop), required=self.required).validate_location(location) is not None:
                return ParseError(detail=f"{self.get_type_string()} is not allowed in {location}")
        return None

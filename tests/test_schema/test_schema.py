from openapi_python_client.schema import DataType, Schema


def test_nullable_with_simple_type():
    schema = Schema.model_validate_json('{"type": "string", "nullable": true}')
    assert schema.type == [DataType.STRING, DataType.NULL]


def test_nullable_with_allof():
    schema = Schema.model_validate_json('{"allOf": [{"type": "string"}], "nullable": true}')
    assert schema.oneOf == [Schema(type=DataType.NULL), Schema(allOf=[Schema(type=DataType.STRING)])]
    assert schema.allOf == []


def test_constant_bool():
    schema = Schema.model_validate_json('{"type":"boolean", "enum":[true], "const":true, "default":true}')
    assert schema.const is True


def test_nullable_with_type_list():
    schema = Schema.model_validate_json('{"type": ["string", "number"], "nullable": true}')
    assert schema.type == [DataType.STRING, DataType.NUMBER, DataType.NULL]


def test_nullable_with_any_of():
    schema = Schema.model_validate_json('{"anyOf": [{"type": "string"}], "nullable": true}')
    assert schema.anyOf == [Schema(type=DataType.STRING), Schema(type=DataType.NULL)]


def test_nullable_with_one_of():
    schema = Schema.model_validate_json('{"oneOf": [{"type": "string"}], "nullable": true}')
    assert schema.oneOf == [Schema(type=DataType.STRING), Schema(type=DataType.NULL)]


def test_exclusive_minimum_as_boolean():
    schema = Schema.model_validate_json('{"minimum": 10, "exclusiveMinimum": true}')
    assert schema.exclusiveMinimum == 10
    assert schema.minimum is None


def test_exclusive_maximum_as_boolean():
    schema = Schema.model_validate_json('{"maximum": 100, "exclusiveMaximum": true}')
    assert schema.exclusiveMaximum == 100
    assert schema.maximum is None


def test_exclusive_minimum_as_number():
    schema = Schema.model_validate_json('{"exclusiveMinimum": 5}')
    assert schema.exclusiveMinimum == 5
    assert schema.minimum is None


def test_exclusive_maximum_as_number():
    schema = Schema.model_validate_json('{"exclusiveMaximum": 50}')
    assert schema.exclusiveMaximum == 50
    assert schema.maximum is None


def test_exclusive_minimum_as_false_boolean():
    schema = Schema.model_validate_json('{"minimum": 10, "exclusiveMinimum": false}')
    assert schema.exclusiveMinimum is None
    assert schema.minimum == 10


def test_exclusive_maximum_as_false_boolean():
    schema = Schema.model_validate_json('{"maximum": 100, "exclusiveMaximum": false}')
    assert schema.exclusiveMaximum is None
    assert schema.maximum == 100

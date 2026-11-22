import pytest
from pydantic import ValidationError
from retail.model import Decision


def test_provider_schema_requires_presentation_fields():
    assert {"action", "format", "depth"} <= set(Decision.model_json_schema()["required"])


def test_preference_cannot_silently_default_an_omitted_depth():
    with pytest.raises(ValidationError):
        Decision.model_validate({"action": "preference", "format": "bullets"})
    assert Decision(action="preference", format="bullets", depth="concise").depth == "concise"
    assert Decision(action="query", sql="SELECT COUNT(*) FROM products").action == "query"

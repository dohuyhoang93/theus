import json
import collections.abc


class TheusEncoder(json.JSONEncoder):
    """
    Standard JSON Encoder for Theus structures.
    Usage: json.dumps(data, cls=TheusEncoder)
    """

    def default(self, obj):
        # 1. SupervisorProxy (via Mapping or explicit check)
        # Note: SupervisorProxy implements Mapping, but json doesn't use it by default.
        # We check for .to_dict() or cast to dict.
        if hasattr(obj, "to_dict"):
            return obj.to_dict()

        # 2. General Mapping fallback (if not handled by standard encoder)
        if isinstance(obj, collections.abc.Mapping):
            return dict(obj)

        return super().default(obj)


# Helper for Pydantic v1/v2 if needed in future
def get_pydantic_config():
    """
    Returns the config dict for Pydantic models to support Theus proxies.
    Usage: model_config = get_pydantic_config()
    """
    return {"from_attributes": True}

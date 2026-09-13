from config.providers import PROVIDER_REGISTRY
from config.models import MODEL_REGISTRY
from config.limits import PROVIDER_LIMITS


class ProviderRegistry:

    def __init__(self):
        self.providers = PROVIDER_REGISTRY
        self.models = MODEL_REGISTRY
        self.limits = PROVIDER_LIMITS

    def enabled_providers(self):
        return {
            provider_id: provider
            for provider_id, provider in self.providers.items()
            if provider.get("enabled", False)
        }

    def get_provider(self, provider_id):
        return self.providers.get(provider_id)

    def get_models(self, provider_id):
        return self.models.get(provider_id, {})

    def get_limits(self, provider_id):
        return self.limits.get(provider_id)

    def validate(self):

        required = {
            "gemini",
            "cloudflare",
            "mistral",
        }

        registered = set(self.providers.keys())

        missing = required - registered

        if missing:
            raise RuntimeError(
                f"Missing providers: {sorted(missing)}"
            )

        return True
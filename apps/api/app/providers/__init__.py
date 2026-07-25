"""Model-provider adapters.

Deliberately free of imports. Re-exporting the factory here meant importing *any*
module in this package pulled in the whole adapter chain, which becomes a cycle now
that the fabrication validators live in `app.analysis` and raise `ProviderError`.
Import `get_provider` and `get_provider_candidates` from `app.providers.factory`.
"""

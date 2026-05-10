"""Pure assistant evidence policies.

Domain helpers shape deterministic evidence payloads from already-loaded
contracts. They deliberately avoid repositories, runtimes, and other injected
dependencies so application modules remain the only place that talks to read
models.
"""

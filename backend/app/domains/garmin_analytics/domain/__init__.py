"""Pure Garmin analytics calculations.

Domain modules transform already-loaded biometric records into read models. They
must stay free of FastAPI, SQLite, cache, filesystem, and environment access.
"""

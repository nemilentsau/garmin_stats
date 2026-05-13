"""Storage schema composition for the application process.

SQLite setup lives in ``app.infra.database``; table ownership lives beside the
storage adapters that read and write those tables. This module is the bootstrap
composition point that creates the complete schema without making infra depend
on product domains.
"""

from app.core.profile.schema import init_profile_schema
from app.domains.artifacts.schema import init_artifact_schema
from app.domains.assistant.schema import init_assistant_schema
from app.domains.experiments.schema import init_experiment_schema
from app.domains.garmin_sync.schema import init_garmin_sync_schema
from app.domains.journal.schema import init_journal_schema
from app.domains.programs.schema import init_program_schema
from app.domains.routines.schema import init_routine_schema
from app.infra import database


def init_storage() -> None:
    """Initialize shared SQLite settings and every owned storage schema."""
    database.init_db()
    with database._connect() as con, con:
        init_garmin_sync_schema(con)
        init_profile_schema(con)
        init_assistant_schema(con)
        init_artifact_schema(con)
        init_routine_schema(con)
        init_journal_schema(con)
        init_experiment_schema(con)
        init_program_schema(con)

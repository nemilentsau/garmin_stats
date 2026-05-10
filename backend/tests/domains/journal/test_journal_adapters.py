"""Journal adapter tests for SQLite persistence and check-in caching."""

import app.domains.journal.adapters as journal_db
from app.domains.journal.contracts import DailyCheckIn, Note
from app.infra import cache


class TestJournalAdapter:
    def test_daily_checkin_and_note_survive_round_trip(self):
        journal_db.save_daily_checkin(
            DailyCheckIn(
                id="checkin-2026-01-15",
                date="2026-01-15",
                energy=4,
                notes="Felt solid",
            )
        )
        journal_db.save_note(
            Note(
                id="note-1",
                date="2026-01-15",
                category="nutrition",
                title="Dinner",
                content="More carbs than usual",
            )
        )

        checkins = journal_db.load_daily_checkins("2026-01-15")
        notes = journal_db.load_notes("2026-01-15")

        assert len(checkins) == 1
        assert checkins[0].energy == 4
        assert len(notes) == 1
        assert notes[0].title == "Dinner"

    def test_recent_checkins_return_tail_in_ascending_order(self):
        for i in range(10):
            date = f"2026-03-{i + 1:02d}"
            journal_db.save_daily_checkin(DailyCheckIn(id=f"checkin-{i}", date=date))

        result = journal_db.load_daily_checkins(last_n=3)

        assert len(result) == 3
        assert result[0].date == "2026-03-08"
        assert result[1].date == "2026-03-09"
        assert result[2].date == "2026-03-10"

    def test_full_checkin_load_is_cached_until_save_evicts_only_checkins_key(self):
        cache.put(cache.DAILY_METRICS, ["sentinel"], cache.generation())

        journal_db.save_daily_checkin(DailyCheckIn(id="c-1", date="2026-03-01", energy=3))

        first = journal_db.load_daily_checkins()
        assert cache.get(cache.DAILY_CHECKINS) is first

        journal_db.save_daily_checkin(DailyCheckIn(id="c-2", date="2026-03-02", energy=4))

        assert cache.get(cache.DAILY_CHECKINS) is None
        assert cache.get(cache.DAILY_METRICS) == ["sentinel"]
        second = journal_db.load_daily_checkins()
        assert {c.id for c in second} == {"c-1", "c-2"}

    def test_filtered_checkin_loads_bypass_cache(self):
        journal_db.save_daily_checkin(DailyCheckIn(id="c-1", date="2026-03-01"))

        journal_db.load_daily_checkins(date="2026-03-01")
        journal_db.load_daily_checkins(last_n=1)

        assert cache.get(cache.DAILY_CHECKINS) is None

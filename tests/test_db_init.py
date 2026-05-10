"""Tests for DB initialisation and schema correctness."""

from sqlalchemy import inspect

from app.db.database import init_db


class TestDBInit:
    def test_all_expected_tables_created(self, db_engine):
        inspector = inspect(db_engine)
        tables = set(inspector.get_table_names())
        expected = {
            "tickets",
            "audit_events",
            "contacts",
            "diagnostics",
            "sla_states",
            "replay_guard",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_init_db_is_idempotent(self, db_engine):
        init_db(engine=db_engine)   # second call must not raise
        inspector = inspect(db_engine)
        assert "tickets" in set(inspector.get_table_names())

    def test_tickets_has_tenant_id_column(self, db_engine):
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("tickets")}
        assert "tenant_id" in columns

    def test_tickets_has_sla_deadline_columns(self, db_engine):
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("tickets")}
        assert "sla_deadline_response" in columns
        assert "sla_deadline_resolution" in columns
        assert "sla_breached" in columns

    def test_audit_events_has_hash_chain_columns(self, db_engine):
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("audit_events")}
        assert "previous_hash" in columns
        assert "current_hash" in columns

    def test_audit_events_has_tenant_id_column(self, db_engine):
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("audit_events")}
        assert "tenant_id" in columns

    def test_diagnostics_has_classification_column(self, db_engine):
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("diagnostics")}
        assert "classification" in columns

    def test_diagnostics_has_tenant_id_column(self, db_engine):
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("diagnostics")}
        assert "tenant_id" in columns

    def test_sla_states_has_tenant_id_column(self, db_engine):
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("sla_states")}
        assert "tenant_id" in columns

    def test_replay_guard_has_event_id_column(self, db_engine):
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("replay_guard")}
        assert "event_id" in columns

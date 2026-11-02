"""Regression test for the production asyncpg.exceptions.DataError:

    invalid input for query argument $9: 2729585502 (value out of int32 range)

network_rx_bytes/network_tx_bytes are cumulative counters from Linux agents and
routinely exceed PostgreSQL's signed INT4 maximum (2147483647) on a long-lived
interface. The fix is model/models/monitoring.py using BigInteger explicitly
instead of letting SQLAlchemy infer Integer from `int | None`.
"""

INT32_MAX = 2147483647
PRODUCTION_FAILING_VALUE = 2729585502  # the exact value from the reported error


def test_performance_metric_network_columns_are_bigint_in_metadata():
    from ssc_core.models.monitoring import PerformanceMetric

    rx = PerformanceMetric.__table__.c.network_rx_bytes
    tx = PerformanceMetric.__table__.c.network_tx_bytes

    assert rx.type.__class__.__name__ == "BigInteger"
    assert tx.type.__class__.__name__ == "BigInteger"


def test_performance_metric_network_columns_compile_to_bigint_on_postgres():
    from sqlalchemy.dialects import postgresql

    from ssc_core.models.monitoring import PerformanceMetric

    rx = PerformanceMetric.__table__.c.network_rx_bytes
    tx = PerformanceMetric.__table__.c.network_tx_bytes

    assert rx.type.compile(dialect=postgresql.dialect()) == "BIGINT"
    assert tx.type.compile(dialect=postgresql.dialect()) == "BIGINT"


def test_production_overflow_value_exceeds_int32_but_fits_bigint():
    from sqlalchemy.dialects import postgresql

    from ssc_core.models.monitoring import PerformanceMetric

    assert PRODUCTION_FAILING_VALUE > INT32_MAX

    rx = PerformanceMetric.__table__.c.network_rx_bytes
    bind_processor = rx.type.dialect_impl(postgresql.dialect()).bind_processor(
        postgresql.dialect()
    )
    # BigInteger has no bind processor that would narrow/validate the value —
    # it's passed straight through to asyncpg, which is exactly what makes the
    # BIGINT column (not a Python-side check) the actual fix.
    value = bind_processor(PRODUCTION_FAILING_VALUE) if bind_processor else PRODUCTION_FAILING_VALUE
    assert value == PRODUCTION_FAILING_VALUE


def test_performance_metric_round_trips_value_above_int32_max():
    import uuid
    from datetime import datetime, timezone

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from ssc_core.db import Base
    from ssc_core.models.monitoring import PerformanceMetric
    from ssc_core.models.server import Server

    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            server = Server(
                id=uuid.uuid4(),
                name="test-server",
                hostname_or_ip="test.example.com",
                registered_at=datetime.now(timezone.utc),
            )
            session.add(server)
            session.flush()

            metric = PerformanceMetric(
                id=uuid.uuid4(),
                server_id=server.id,
                recorded_at=datetime.now(timezone.utc),
                network_rx_bytes=PRODUCTION_FAILING_VALUE,
                network_tx_bytes=PRODUCTION_FAILING_VALUE + 1,
            )
            session.add(metric)
            session.commit()

            fetched = session.get(PerformanceMetric, metric.id)
            assert fetched.network_rx_bytes == PRODUCTION_FAILING_VALUE
            assert fetched.network_tx_bytes == PRODUCTION_FAILING_VALUE + 1
    finally:
        engine.dispose()

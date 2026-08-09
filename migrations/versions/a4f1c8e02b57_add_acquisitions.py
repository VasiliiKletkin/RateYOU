"""unify sources: acquisition_sources + acquisitions, absorb referrals

A source is "where a user came from" in either shape: a campaign tag from
the `/start` deep link (`?start=habr`) or a person who shared their /refer
link (`?start=<telegram_id>`). Two tables: a source dictionary
(`acquisition_sources`, with `referrer_id` set for person-sources) and a
one-row-per-user link (`acquisitions`, with the referral-reward lifecycle
in `rewarded_at`).

The old `referrals` table is absorbed: every referrer becomes a
person-source (code = their telegram_id), every referral row becomes an
acquisition link carrying its `rewarded_at`. **Runs against real prod
data** — the backfill below moves it, then drops `referrals`. Downgrade
reconstructs `referrals` from the unified tables (with fresh row ids —
the original UUIDs are not preserved, nothing references them).

Existing non-referred users get no backfill: nobody knows where they came
from, and a missing row reads as "organic" in the funnel report.

Revision ID: a4f1c8e02b57
Revises: f7d2a4c9b6e1
Create Date: 2026-08-09 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4f1c8e02b57"
down_revision: Union[str, Sequence[str], None] = "f7d2a4c9b6e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "acquisition_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("referrer_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["referrer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_acquisition_sources_code"),
        "acquisition_sources",
        ["code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_acquisition_sources_referrer_id"),
        "acquisition_sources",
        ["referrer_id"],
    )
    op.create_table(
        "acquisitions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["acquisition_sources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(op.f("ix_acquisitions_source_id"), "acquisitions", ["source_id"])

    # ── Absorb `referrals` ────────────────────────────────────────────────
    # One person-source per distinct referrer; code = telegram_id, which is
    # exactly what their /refer deep link carries.
    op.execute(
        "INSERT INTO acquisition_sources (id, code, referrer_id, created_at) "
        "SELECT gen_random_uuid(), u.telegram_id::text, u.id, now() "
        "FROM (SELECT DISTINCT referrer_id FROM referrals) r "
        "JOIN users u ON u.id = r.referrer_id"
    )
    # Every referral becomes the referee's acquisition link, reward state
    # included. `referee_id` was UNIQUE, so the PK on user_id holds.
    op.execute(
        "INSERT INTO acquisitions (user_id, source_id, created_at, rewarded_at) "
        "SELECT ref.referee_id, s.id, ref.created_at, ref.rewarded_at "
        "FROM referrals ref "
        "JOIN acquisition_sources s ON s.referrer_id = ref.referrer_id"
    )
    op.drop_table("referrals")


def downgrade() -> None:
    op.create_table(
        "referrals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("referrer_id", sa.Uuid(), nullable=False),
        sa.Column("referee_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["referrer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referee_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referee_id"),
    )
    op.create_index(op.f("ix_referrals_referrer_id"), "referrals", ["referrer_id"])
    op.execute(
        "INSERT INTO referrals (id, referrer_id, referee_id, created_at, rewarded_at) "
        "SELECT gen_random_uuid(), s.referrer_id, a.user_id, a.created_at, a.rewarded_at "
        "FROM acquisitions a "
        "JOIN acquisition_sources s ON s.id = a.source_id "
        "WHERE s.referrer_id IS NOT NULL"
    )
    op.drop_index(op.f("ix_acquisitions_source_id"), table_name="acquisitions")
    op.drop_table("acquisitions")
    op.drop_index(
        op.f("ix_acquisition_sources_referrer_id"), table_name="acquisition_sources"
    )
    op.drop_index(op.f("ix_acquisition_sources_code"), table_name="acquisition_sources")
    op.drop_table("acquisition_sources")

"""initial schema

Single migration that materializes the current ORM state. Hand-cleaned from
autogenerate output to drop unrelated PostGIS Tiger geocoder tables that
ship with the postgis/postgis image.

Revision ID: b1e692424df8
Revises:
Create Date: 2026-05-13 01:34:45.855898

"""

from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "b1e692424df8"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostGIS is needed by `profiles.location` (Geography Point, SRID 4326).
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "role", sa.Enum("USER", "ADMIN", name="role"), nullable=False
        ),
        sa.Column("is_banned", sa.Boolean(), nullable=False),
        sa.Column("ban_reason", sa.String(length=500), nullable=True),
        sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "language",
            sa.Enum(
                "EN", "RU", "ES", "PT", "DE", "FR", "IT", "TR", "UK", "PL",
                "AR", "FA", "ID", "VI", "ZH", "HI", "BN", "AM", "UZ", "KO",
                "JA", "TH",
                name="language",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=True
    )

    op.create_table(
        "profile_score_summaries",
        sa.Column("rated_id", sa.Uuid(), nullable=False),
        sa.Column("average_score", sa.Double(), nullable=False),
        sa.Column("rating_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["rated_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("rated_id"),
    )

    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column(
            "gender",
            sa.Enum("MALE", "FEMALE", name="gender"),
            nullable=False,
        ),
        sa.Column("bio", sa.String(length=500), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeogFromText",
                name="geography",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # idx_profiles_location is auto-created by geoalchemy2 when the
    # Geography column is added — no explicit op.create_index needed.
    op.create_index(
        op.f("ix_profiles_owner_id"), "profiles", ["owner_id"], unique=True
    )

    op.create_table(
        "ratings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rater_id", sa.Uuid(), nullable=False),
        sa.Column("rated_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["rated_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["rater_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rater_id", "rated_id", name="uq_ratings_rater_rated"
        ),
    )
    op.create_index(
        op.f("ix_ratings_rated_id"), "ratings", ["rated_id"], unique=False
    )
    op.create_index(
        op.f("ix_ratings_rater_id"), "ratings", ["rater_id"], unique=False
    )

    op.create_table(
        "referrals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("referrer_id", sa.Uuid(), nullable=False),
        sa.Column("referee_id", sa.Uuid(), nullable=False),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["referee_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["referrer_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referee_id"),
    )
    op.create_index(
        op.f("ix_referrals_referrer_id"),
        "referrals",
        ["referrer_id"],
        unique=False,
    )

    op.create_table(
        "search_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "gender_preference",
            sa.Enum("MALE", "FEMALE", "ANY", name="genderpreference"),
            nullable=False,
        ),
        sa.Column("min_rating", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payer_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column(
            "provider",
            sa.Enum("TELEGRAM_STARS", name="provider"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "PAID", "FAILED", "REFUNDED", name="status"
            ),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["payer_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transactions_payer_id"),
        "transactions",
        ["payer_id"],
        unique=False,
    )

    op.create_table(
        "profile_photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.String(length=500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "position", name="uq_profile_photos_position"
        ),
    )
    op.create_index(
        op.f("ix_profile_photos_profile_id"),
        "profile_photos",
        ["profile_id"],
        unique=False,
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tier",
            sa.Enum(
                "BRONZE", "SILVER", "GOLD", "BONUS", name="tier"
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum("PURCHASE", "BONUS", name="subscriptionsource"),
            nullable=False,
        ),
        sa.Column("transaction_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscriptions_owner_expires",
        "subscriptions",
        ["owner_id", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_subscriptions_transaction",
        "subscriptions",
        ["transaction_id"],
        unique=True,
        postgresql_where="transaction_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_subscriptions_transaction",
        table_name="subscriptions",
        postgresql_where="transaction_id IS NOT NULL",
    )
    op.drop_index(
        "ix_subscriptions_owner_expires", table_name="subscriptions"
    )
    op.drop_table("subscriptions")
    op.drop_index(
        op.f("ix_profile_photos_profile_id"), table_name="profile_photos"
    )
    op.drop_table("profile_photos")
    op.drop_index(
        op.f("ix_transactions_payer_id"), table_name="transactions"
    )
    op.drop_table("transactions")
    op.drop_table("search_preferences")
    op.drop_index(
        op.f("ix_referrals_referrer_id"), table_name="referrals"
    )
    op.drop_table("referrals")
    op.drop_index(op.f("ix_ratings_rater_id"), table_name="ratings")
    op.drop_index(op.f("ix_ratings_rated_id"), table_name="ratings")
    op.drop_table("ratings")
    op.drop_index(op.f("ix_profiles_owner_id"), table_name="profiles")
    op.drop_table("profiles")
    op.drop_table("profile_score_summaries")
    op.drop_index(op.f("ix_users_telegram_id"), table_name="users")
    op.drop_table("users")
    for enum_name in (
        "subscriptionsource",
        "tier",
        "status",
        "provider",
        "genderpreference",
        "gender",
        "language",
        "role",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

"""Cria as tabelas do ledger: products, idempotency_keys e movements.

- products: cadastro, com SKU único.
- idempotency_keys: uma linha por Idempotency-Key usada, com o hash do corpo e a resposta.
- movements: o ledger. Só recebe INSERT; o saldo é SUM(delta). As constraints garantem
  quantidade positiva, delta coerente com o tipo e no máximo uma movimentação por chave.

Revision ID: bd79d110263f
Revises:
Create Date: 2026-10-31 21:26:50.862727

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "bd79d110263f"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_idempotency_keys")),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("sku", name=op.f("uq_products_sku")),
    )
    op.create_table(
        "movements",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "IN",
                "OUT",
                "ADJUST",
                name="type",
                native_enum=False,
                create_constraint=True,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("delta", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(type = 'IN' AND delta = quantity)"
            " OR (type = 'OUT' AND delta = -quantity)"
            " OR type = 'ADJUST'",
            name=op.f("ck_movements_delta_matches_type"),
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_movements_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["idempotency_key"],
            ["idempotency_keys.key"],
            name=op.f("fk_movements_idempotency_key_idempotency_keys"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_movements_product_id_products")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movements")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_movements_idempotency_key")),
    )
    op.create_index(
        "ix_movements_product_id_occurred_at_id",
        "movements",
        ["product_id", "occurred_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_movements_product_id_occurred_at_id", table_name="movements")
    op.drop_table("movements")
    op.drop_table("products")
    op.drop_table("idempotency_keys")

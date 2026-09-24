"""Immutable Vaisala action programme snapshots, policy versions and review audit."""
import sqlalchemy as sa
from alembic import op

revision = "020_vaisala_programme"
down_revision = "019_vaisala_defect_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("vaisala_programme_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("authority_id", "version", name="uq_vaisala_programme_policy"))
    op.create_index("ix_vaisala_programme_policies_authority_id", "vaisala_programme_policies", ["authority_id"])
    op.create_table("vaisala_programmes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("authorities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("vaisala_surveys.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("merge_scale", sa.String(10), nullable=False),
        sa.Column("split", sa.String(20), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("authority_id", "created_by", "idempotency_key", name="uq_vaisala_programme_save"))
    op.create_index("ix_vaisala_programmes_authority_id", "vaisala_programmes", ["authority_id"])
    op.create_index("ix_vaisala_programmes_survey_id", "vaisala_programmes", ["survey_id"])
    op.create_table("vaisala_programme_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("programme_id", sa.Integer(), sa.ForeignKey("vaisala_programmes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("item_key", sa.String(200), nullable=False),
        sa.Column("assessment", sa.JSON(), nullable=False),
        sa.UniqueConstraint("programme_id", "item_key", name="uq_vaisala_programme_item"))
    op.create_index("ix_vaisala_programme_items_programme_id", "vaisala_programme_items", ["programme_id"])
    op.create_table("vaisala_programme_review_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("vaisala_programme_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decision", sa.JSON(), nullable=False),
        sa.UniqueConstraint("item_id", "sequence", name="uq_vaisala_programme_review_sequence"))
    op.create_index("ix_vaisala_programme_review_events_item_id", "vaisala_programme_review_events", ["item_id"])


def downgrade():
    # Deliberate maintenance operation only; application rollback leaves audit tables intact.
    for table in ("vaisala_programme_review_events", "vaisala_programme_items", "vaisala_programmes", "vaisala_programme_policies"):
        op.drop_table(table)

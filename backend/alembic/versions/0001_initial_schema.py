"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-06

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enums
    # ------------------------------------------------------------------
    op.execute("CREATE TYPE user_tier AS ENUM ('free', 'pro')")
    op.execute(
        "CREATE TYPE item_category AS ENUM ("
        "'subscription','insurance','voucher','warranty',"
        "'document','finance','domain','membership','other')"
    )
    op.execute(
        "CREATE TYPE date_type AS ENUM ('expiry','renewal','deadline','end_of_offer')"
    )
    op.execute("CREATE TYPE confidence_level AS ENUM ('high','medium','low')")
    op.execute(
        "CREATE TYPE scan_status AS ENUM ('queued','running','complete','failed')"
    )
    op.execute("CREATE TYPE scan_kind AS ENUM ('initial','weekly','manual')")

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE users (
          id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          email                    TEXT NOT NULL UNIQUE,
          gmail_address            TEXT NOT NULL,
          google_sub               TEXT NOT NULL UNIQUE,
          refresh_token_enc        TEXT NOT NULL,
          access_token_enc         TEXT,
          access_token_expires_at  TIMESTAMPTZ,
          api_key_enc              TEXT,
          tier                     user_tier NOT NULL DEFAULT 'free',
          stripe_customer_id       TEXT UNIQUE,
          stripe_subscription_id   TEXT UNIQUE,
          timezone                 TEXT NOT NULL DEFAULT 'UTC',
          digest_day_of_week       SMALLINT NOT NULL DEFAULT 1
                                     CHECK (digest_day_of_week BETWEEN 0 AND 6),
          last_scan_at             TIMESTAMPTZ,
          last_history_id          TEXT,
          deleted_at               TIMESTAMPTZ,
          created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_users_tier ON users(tier) WHERE deleted_at IS NULL"
    )

    # ------------------------------------------------------------------
    # extracted_items
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE extracted_items (
          id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          name              TEXT NOT NULL,
          category          item_category NOT NULL,
          expiry_date       DATE NOT NULL,
          date_type         date_type NOT NULL,
          confidence        confidence_level NOT NULL,
          notes             TEXT,
          source_sender     TEXT NOT NULL,
          source_date       TIMESTAMPTZ NOT NULL,
          source_message_id TEXT NOT NULL,
          dismissed         BOOLEAN NOT NULL DEFAULT FALSE,
          dismissed_at      TIMESTAMPTZ,
          exported_to_gcal  BOOLEAN NOT NULL DEFAULT FALSE,
          gcal_event_id     TEXT,
          created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT uq_user_msg_name UNIQUE (user_id, source_message_id, name)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_items_user_expiry ON extracted_items(user_id, expiry_date)"
        " WHERE dismissed = FALSE"
    )
    op.execute(
        "CREATE INDEX idx_items_user_dismissed ON extracted_items(user_id, dismissed)"
    )
    op.execute(
        "CREATE INDEX idx_items_user_category ON extracted_items(user_id, category)"
    )

    # ------------------------------------------------------------------
    # scan_jobs
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE scan_jobs (
          id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          kind              scan_kind NOT NULL,
          status            scan_status NOT NULL DEFAULT 'queued',
          since_date        DATE,
          emails_total      INTEGER NOT NULL DEFAULT 0,
          emails_processed  INTEGER NOT NULL DEFAULT 0,
          items_found       INTEGER NOT NULL DEFAULT 0,
          error             TEXT,
          locked_at         TIMESTAMPTZ,
          locked_by         TEXT,
          started_at        TIMESTAMPTZ,
          completed_at      TIMESTAMPTZ,
          created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_scan_jobs_status ON scan_jobs(status, created_at)"
    )
    op.execute(
        "CREATE INDEX idx_scan_jobs_user ON scan_jobs(user_id, created_at DESC)"
    )
    # Enforces at most one queued/running job per user at the DB level
    op.execute(
        """
        CREATE UNIQUE INDEX uq_one_running_job_per_user
          ON scan_jobs(user_id)
          WHERE status IN ('queued','running')
        """
    )

    # ------------------------------------------------------------------
    # dismissed_signatures
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE dismissed_signatures (
          id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          signature   TEXT NOT NULL,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT uq_user_signature UNIQUE (user_id, signature)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_dismissed_sig_user ON dismissed_signatures(user_id)"
    )

    # ------------------------------------------------------------------
    # audit_log
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE audit_log (
          id          BIGSERIAL PRIMARY KEY,
          user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
          event       TEXT NOT NULL,
          payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC)"
    )

    # ------------------------------------------------------------------
    # updated_at trigger (applied to users and extracted_items)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_updated
          BEFORE UPDATE ON users
          FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_items_updated
          BEFORE UPDATE ON extracted_items
          FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    # Triggers
    op.execute("DROP TRIGGER IF EXISTS trg_items_updated ON extracted_items")
    op.execute("DROP TRIGGER IF EXISTS trg_users_updated ON users")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at")

    # Tables — reverse dependency order
    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP TABLE IF EXISTS dismissed_signatures")
    op.execute("DROP TABLE IF EXISTS scan_jobs")
    op.execute("DROP TABLE IF EXISTS extracted_items")
    op.execute("DROP TABLE IF EXISTS users")

    # Enums
    op.execute("DROP TYPE IF EXISTS scan_kind")
    op.execute("DROP TYPE IF EXISTS scan_status")
    op.execute("DROP TYPE IF EXISTS confidence_level")
    op.execute("DROP TYPE IF EXISTS date_type")
    op.execute("DROP TYPE IF EXISTS item_category")
    op.execute("DROP TYPE IF EXISTS user_tier")

CREATE TABLE IF NOT EXISTS public.dbops_backup_status (
    backup_type TEXT PRIMARY KEY CHECK (backup_type IN ('logical', 'physical')),
    last_attempt_at TIMESTAMPTZ NOT NULL,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    last_artifact TEXT,
    last_duration_seconds NUMERIC(12, 3),
    last_size_bytes BIGINT,
    failure_count BIGINT NOT NULL DEFAULT 0,
    last_error_type TEXT
);

GRANT SELECT ON public.dbops_backup_status TO dbops_monitor;

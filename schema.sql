-- schema.sql
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    owner_key TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL, -- e.g., queued, running, done, error, cancelled
    pid INTEGER,         -- To store the process ID of the task
    result TEXT,
    progress INTEGER DEFAULT 0, -- Progress percentage (0-100)
    progress_message TEXT, -- User-friendly progress message
    error_count INTEGER DEFAULT 0, -- Number of retry attempts
    max_retries INTEGER DEFAULT 3, -- Maximum retry attempts allowed
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT, -- When the job should be cleaned up
    priority INTEGER DEFAULT 5 -- Job priority (1-10, 1 being highest)
);

-- Index for efficient cleanup queries
CREATE INDEX IF NOT EXISTS idx_jobs_expires_at ON jobs(expires_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status_created_at ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_owner_status ON jobs(owner_key, status);
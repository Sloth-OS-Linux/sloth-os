-- Sloth OS shared knowledge: the machines' anonymous reports (services/knowledge/README.md)
-- Per machine and setting only the latest result counts (one machine, one vote).
CREATE TABLE IF NOT EXISTS reports (
    machine   TEXT NOT NULL,   -- salted hash of the machine's random ID
    program   TEXT NOT NULL,   -- the program's fingerprint (sha256, computed on the machine; we do not see the name)
    gpu       TEXT NOT NULL,   -- amd | nvidia | intel | other
    config    TEXT NOT NULL,   -- kanonikus JSON: {"line", "profile", "fixes"}
    outcome   TEXT NOT NULL,   -- worked | failed
    updated   INTEGER NOT NULL,
    PRIMARY KEY (machine, program, gpu, config)
);
CREATE INDEX IF NOT EXISTS reports_program ON reports (program, gpu);

-- Against abuse: at most this many reports per address per day (the address only as a salted hash too)
CREATE TABLE IF NOT EXISTS rate (
    day   TEXT NOT NULL,
    ip    TEXT NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (day, ip)
);

-- Feedback: the attached log (only the link is in the issue; the Worker deletes it after 30 days)
CREATE TABLE IF NOT EXISTS feedback_logs (
    id      TEXT PRIMARY KEY,   -- random UUID
    created INTEGER NOT NULL,
    log     TEXT NOT NULL
);

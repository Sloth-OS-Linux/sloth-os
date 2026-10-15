-- Sloth OS közös tudás: a gépek névtelen jelentései (services/knowledge/README.md)
-- Gépenként és beállításonként csak a legutóbbi eredmény számít (egy gép egy szavazat).
CREATE TABLE IF NOT EXISTS reports (
    machine   TEXT NOT NULL,   -- a gép véletlen azonosítójának sózott hash-e
    program   TEXT NOT NULL,   -- a program ujjlenyomata (sha256, a gépen számolva; a nevet nem látjuk)
    gpu       TEXT NOT NULL,   -- amd | nvidia | intel | other
    config    TEXT NOT NULL,   -- kanonikus JSON: {"line", "profile", "fixes"}
    outcome   TEXT NOT NULL,   -- worked | failed
    updated   INTEGER NOT NULL,
    PRIMARY KEY (machine, program, gpu, config)
);
CREATE INDEX IF NOT EXISTS reports_program ON reports (program, gpu);

-- Visszaélés ellen: címenként naponta legfeljebb ennyi jelentés (a cím is csak sózott hash-ként)
CREATE TABLE IF NOT EXISTS rate (
    day   TEXT NOT NULL,
    ip    TEXT NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (day, ip)
);

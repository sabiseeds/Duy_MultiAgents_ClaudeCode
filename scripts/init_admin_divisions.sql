-- Administrative divisions table setup
-- Run this after init_database.sql

\c multi_agent_db

-- Create administrative_divisions table
CREATE TABLE administrative_divisions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_local TEXT,
    type TEXT NOT NULL,
    iso_code TEXT,
    parent_id TEXT,
    level INTEGER NOT NULL CHECK (level >= 0 AND level <= 10),
    population BIGINT CHECK (population >= 0),
    area_km2 NUMERIC CHECK (area_km2 >= 0),
    capital TEXT,
    timezone TEXT,
    latitude NUMERIC CHECK (latitude >= -90 AND latitude <= 90),
    longitude NUMERIC CHECK (longitude >= -180 AND longitude <= 180),
    bbox_north NUMERIC CHECK (bbox_north >= -90 AND bbox_north <= 90),
    bbox_south NUMERIC CHECK (bbox_south >= -90 AND bbox_south <= 90),
    bbox_east NUMERIC CHECK (bbox_east >= -180 AND bbox_east <= 180),
    bbox_west NUMERIC CHECK (bbox_west >= -180 AND bbox_west <= 180),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT name_length CHECK (LENGTH(name) BETWEEN 1 AND 255),
    CONSTRAINT valid_coordinates CHECK (
        (latitude IS NULL AND longitude IS NULL) OR
        (latitude IS NOT NULL AND longitude IS NOT NULL)
    ),
    CONSTRAINT valid_bbox CHECK (
        (bbox_north IS NULL AND bbox_south IS NULL AND bbox_east IS NULL AND bbox_west IS NULL) OR
        (bbox_north IS NOT NULL AND bbox_south IS NOT NULL AND bbox_east IS NOT NULL AND bbox_west IS NOT NULL AND
         bbox_north >= bbox_south AND bbox_east >= bbox_west)
    )
);

-- Add foreign key constraint for parent hierarchy
ALTER TABLE administrative_divisions
ADD CONSTRAINT fk_parent_division
FOREIGN KEY (parent_id) REFERENCES administrative_divisions(id)
ON DELETE SET NULL;

-- Create indexes for efficient querying
CREATE INDEX idx_admin_div_name ON administrative_divisions(name);
CREATE INDEX idx_admin_div_name_local ON administrative_divisions(name_local);
CREATE INDEX idx_admin_div_type ON administrative_divisions(type);
CREATE INDEX idx_admin_div_iso_code ON administrative_divisions(iso_code);
CREATE INDEX idx_admin_div_parent ON administrative_divisions(parent_id);
CREATE INDEX idx_admin_div_level ON administrative_divisions(level);
CREATE INDEX idx_admin_div_coordinates ON administrative_divisions(latitude, longitude);
CREATE INDEX idx_admin_div_created ON administrative_divisions(created_at DESC);

-- Create GiST index for spatial queries (if PostGIS is available)
-- CREATE INDEX idx_admin_div_spatial ON administrative_divisions USING GIST (ST_Point(longitude, latitude));

-- Create text search index for name searching
CREATE INDEX idx_admin_div_name_search ON administrative_divisions USING gin(to_tsvector('english', name));

-- Insert sample data for testing
INSERT INTO administrative_divisions (id, name, type, iso_code, level, population, area_km2, latitude, longitude, metadata) VALUES
('USA', 'United States', 'country', 'US', 0, 331900000, 9833517, 39.8283, -98.5795, '{"continent": "North America"}'),
('USA-CA', 'California', 'state', 'US-CA', 1, 39538223, 423967, 36.7783, -119.4179, '{"capital": "Sacramento"}'),
('USA-NY', 'New York', 'state', 'US-NY', 1, 20201249, 141297, 42.1657, -74.9481, '{"capital": "Albany"}'),
('CAN', 'Canada', 'country', 'CA', 0, 38000000, 9984670, 56.1304, -106.3468, '{"continent": "North America"}'),
('GBR', 'United Kingdom', 'country', 'GB', 0, 67886011, 242495, 55.3781, -3.4360, '{"continent": "Europe"}'),
('FRA', 'France', 'country', 'FR', 0, 65273511, 551695, 46.2276, 2.2137, '{"continent": "Europe"}'),
('DEU', 'Germany', 'country', 'DE', 0, 83783942, 357022, 51.1657, 10.4515, '{"continent": "Europe"}'),
('JPN', 'Japan', 'country', 'JP', 0, 126476461, 377930, 36.2048, 138.2529, '{"continent": "Asia"}'),
('CHN', 'China', 'country', 'CN', 0, 1439323776, 9596960, 35.8617, 104.1954, '{"continent": "Asia"}'),
('IND', 'India', 'country', 'IN', 0, 1380004385, 3287263, 20.5937, 78.9629, '{"continent": "Asia"}'
);

-- Update parent relationships
UPDATE administrative_divisions SET parent_id = 'USA' WHERE id IN ('USA-CA', 'USA-NY');

-- Display table information
\d administrative_divisions
SELECT COUNT(*) as total_divisions FROM administrative_divisions;
SELECT type, COUNT(*) as count FROM administrative_divisions GROUP BY type ORDER BY count DESC;
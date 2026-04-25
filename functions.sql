-- Practice 8: SQL functions for the phonebook schema.
-- Requires PostgreSQL 11+ (procedures are loaded from procedures.sql).

CREATE TABLE IF NOT EXISTS phonebook (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR NOT NULL,
    phone VARCHAR NOT NULL UNIQUE
);

CREATE OR REPLACE FUNCTION search_contacts(pattern TEXT)
RETURNS TABLE(id INT, first_name TEXT, phone TEXT)
LANGUAGE sql
STABLE
AS $$
    SELECT
        p.id::INT,
        p.first_name::TEXT,
        p.phone::TEXT
    FROM phonebook p
    WHERE p.first_name ILIKE '%' || pattern || '%'
       OR p.phone ILIKE '%' || pattern || '%'
    ORDER BY p.id;
$$;

CREATE OR REPLACE FUNCTION get_contacts_paginated("limit" INT, "offset" INT)
RETURNS TABLE(id INT, first_name TEXT, phone TEXT)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF "limit" IS NULL OR "limit" < 1 THEN
        RAISE EXCEPTION 'limit must be a positive integer';
    END IF;
    IF "offset" IS NULL OR "offset" < 0 THEN
        RAISE EXCEPTION 'offset must be a non-negative integer';
    END IF;

    RETURN QUERY
    SELECT
        p.id::INT,
        p.first_name::TEXT,
        p.phone::TEXT
    FROM phonebook p
    ORDER BY p.id ASC
    LIMIT "limit"
    OFFSET "offset";
END;
$$;

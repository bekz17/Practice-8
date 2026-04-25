-- Practice 8: PL/pgSQL procedures for the phonebook schema.
-- Run functions.sql before this file so phonebook exists.

CREATE TABLE IF NOT EXISTS bulk_staging (
    first_name TEXT NOT NULL,
    phone TEXT NOT NULL
);

CREATE OR REPLACE PROCEDURE insert_or_update_user(p_name TEXT, p_phone TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_name TEXT;
    v_phone TEXT;
BEGIN
    v_name := trim(p_name);
    v_phone := trim(p_phone);

    IF v_name IS NULL OR v_name = '' THEN
        RAISE EXCEPTION 'Name cannot be empty';
    END IF;

    IF v_phone !~ '^\+?[0-9]+$'
       OR length(regexp_replace(v_phone, '^\+', '')) < 10 THEN
        RAISE EXCEPTION 'Invalid phone: use digits only or a leading +, with at least 10 digit characters';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM phonebook pb
        WHERE lower(pb.first_name) = lower(v_name)
    ) THEN
        UPDATE phonebook pb
        SET phone = v_phone
        WHERE lower(pb.first_name) = lower(v_name);
    ELSE
        INSERT INTO phonebook (first_name, phone)
        VALUES (v_name, v_phone);
    END IF;
END;
$$;

CREATE OR REPLACE PROCEDURE bulk_insert_users()
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_reason TEXT;
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS bulk_invalid_results (
        first_name TEXT,
        phone TEXT,
        reason TEXT
    ) ON COMMIT PRESERVE ROWS;

    TRUNCATE bulk_invalid_results;

    FOR r IN
        SELECT bs.first_name, bs.phone
        FROM bulk_staging bs
    LOOP
        IF trim(r.first_name) IS NULL OR trim(r.first_name) = '' THEN
            v_reason := 'empty name';
        ELSIF trim(r.phone) !~ '^\+?[0-9]+$' THEN
            v_reason := 'phone must contain only digits with an optional leading +';
        ELSIF length(regexp_replace(trim(r.phone), '^\+', '')) < 10 THEN
            v_reason := 'phone must contain at least 10 digit characters';
        ELSE
            v_reason := NULL;
        END IF;

        IF v_reason IS NOT NULL THEN
            INSERT INTO bulk_invalid_results (first_name, phone, reason)
            VALUES (r.first_name, r.phone, v_reason);
        ELSE
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM phonebook pb
                    WHERE lower(pb.first_name) = lower(trim(r.first_name))
                ) THEN
                    UPDATE phonebook pb
                    SET phone = trim(r.phone)
                    WHERE lower(pb.first_name) = lower(trim(r.first_name));
                ELSE
                    INSERT INTO phonebook (first_name, phone)
                    VALUES (trim(r.first_name), trim(r.phone));
                END IF;
            EXCEPTION
                WHEN unique_violation THEN
                    INSERT INTO bulk_invalid_results (first_name, phone, reason)
                    VALUES (r.first_name, r.phone, 'unique phone conflict');
            END;
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE PROCEDURE delete_user(p_identifier TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id TEXT;
BEGIN
    v_id := trim(p_identifier);

    IF v_id IS NULL OR v_id = '' THEN
        RAISE EXCEPTION 'Identifier cannot be empty';
    END IF;

    DELETE FROM phonebook pb
    WHERE pb.phone = v_id
       OR lower(pb.first_name) = lower(v_id);
END;
$$;

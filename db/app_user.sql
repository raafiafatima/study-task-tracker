-- Creates (or updates) the limited-privilege runtime user and grants only what
-- the API needs: read and insert on tasks. Run as the database administrator
-- AFTER db/init.sql. Safe to run more than once.
--
-- Inputs come from environment variables inside psql, so the password never
-- appears on a command line:  APP_DB_USER and APP_DB_PASSWORD.
-- tasks.id is an IDENTITY column, so INSERT on the table is enough; no separate
-- sequence permission is needed.

\set ON_ERROR_STOP on
\getenv app_user APP_DB_USER
\getenv app_password APP_DB_PASSWORD

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE', :'app_user', :'app_password')
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'app_user')
\gexec

SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'app_user')
\gexec

SELECT format('GRANT SELECT, INSERT ON TABLE public.tasks TO %I', :'app_user')
\gexec

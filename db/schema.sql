-- ============================================================
-- Luma Booking Concierge — Database Schema
-- Supabase (PostgreSQL)
-- Run this first, then run seed_data.sql
-- ============================================================

-- Enable UUID generation
create extension if not exists "pgcrypto";


-- ============================================================
-- BRANCHES
-- ============================================================
create table if not exists branches (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    location    text,
    address     text,
    phone       text,
    hours       jsonb
);


-- ============================================================
-- ARTISTS
-- ============================================================
create table if not exists artists (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    branch_id   uuid references branches(id),
    speciality  text
);


-- ============================================================
-- SERVICES
-- ============================================================
create table if not exists services (
    id                      uuid primary key default gen_random_uuid(),
    name                    text not null,
    category                text,
    service_tier            text not null check (service_tier in ('T1', 'T2', 'T3')),
    duration_minutes        integer,
    price_aed               numeric(10, 2) default 0,
    requires_consultation   boolean default false,
    requires_patch_test     boolean default false,
    requires_screening      boolean default false,
    is_medical              boolean default false,
    min_frequency_weeks     integer,
    frequency_hard_block    boolean default false,
    consent_template_id     uuid,
    description             text,
    is_consultation         boolean default false
);


-- ============================================================
-- CLIENTS
-- ============================================================
create table if not exists clients (
    id          uuid primary key default gen_random_uuid(),
    name        text,
    phone       text,
    email       text,
    created_at  timestamptz default now()
);


-- ============================================================
-- VISITORS
-- Walk-in / anonymous contacts captured during chat
-- ============================================================
create table if not exists visitors (
    id          uuid primary key default gen_random_uuid(),
    name        text,
    contact     text unique,
    created_at  timestamptz default now()
);


-- ============================================================
-- SESSIONS
-- One row per chat session
-- ============================================================
create table if not exists sessions (
    id                  uuid primary key default gen_random_uuid(),
    channel             text default 'web',
    user_tier           text default 'visitor',
    client_id           uuid references clients(id),
    whatsapp_number     text,
    last_intent         text,
    last_booking_ref    text,
    status              text default 'active',
    created_at          timestamptz default now(),
    updated_at          timestamptz default now()
);


-- ============================================================
-- TIME_SLOTS
-- Available and booked appointment windows
-- ============================================================
create table if not exists time_slots (
    id          uuid primary key default gen_random_uuid(),
    branch_id   uuid references branches(id),
    service_id  uuid references services(id),
    artist_id   uuid references artists(id),
    start_time  timestamptz not null,
    end_time    timestamptz not null,
    status      text default 'available' check (status in ('available', 'booked', 'blocked'))
);

create index if not exists idx_time_slots_service_branch_status
    on time_slots (service_id, branch_id, status, start_time);


-- ============================================================
-- BOOKINGS
-- ============================================================
create table if not exists bookings (
    id                  text primary key,  -- e.g. BKG-2026-XXXX / CON-2026-XXXX
    client_id           uuid references clients(id),
    visitor_name        text,
    visitor_contact     text,
    service_id          uuid references services(id),
    branch_id           uuid references branches(id),
    slot_id             uuid references time_slots(id),
    artist_id           uuid references artists(id),
    status              text default 'confirmed' check (status in ('confirmed', 'completed', 'cancelled', 'no_show')),
    notes               text,
    booking_type        text default 'single' check (booking_type in ('single', 'consultation', 'package')),
    payment_type        text default 'full_upfront' check (payment_type in ('full_upfront', 'deposit_20pct', 'free', 'not_required')),
    deposit_amount_aed  numeric(10, 2) default 0,
    balance_due_aed     numeric(10, 2) default 0,
    payment_status      text default 'not_required' check (payment_status in ('not_required', 'payment_initiated', 'paid', 'refunded')),
    payment_link        text,
    screening_ref       text,
    clearance_ref       text,
    consent_status      text default 'not_required',
    channel             text default 'web',
    booking_source      text default 'ai_concierge',
    created_at          timestamptz default now(),
    updated_at          timestamptz default now()
);

create index if not exists idx_bookings_client_id   on bookings (client_id);
create index if not exists idx_bookings_service_id  on bookings (service_id);
create index if not exists idx_bookings_status      on bookings (status);


-- ============================================================
-- SPMU_CLEARANCES
-- Tracks consultation + patch test clearance for T2 services
-- ============================================================
create table if not exists spmu_clearances (
    id                      uuid primary key default gen_random_uuid(),
    client_id               uuid references clients(id),
    visitor_contact         text,
    service_category        text not null,
    consultation_booking_id text references bookings(id),
    patch_test_done         boolean default false,
    patch_test_cleared      boolean default false,
    cleared_at              timestamptz,
    valid_until             timestamptz,
    created_at              timestamptz default now()
);

create index if not exists idx_spmu_clearances_client     on spmu_clearances (client_id);
create index if not exists idx_spmu_clearances_contact    on spmu_clearances (visitor_contact);
create index if not exists idx_spmu_clearances_category   on spmu_clearances (service_category);


-- ============================================================
-- MEDICAL_SCREENINGS
-- T3 health screening submissions
-- ============================================================
create table if not exists medical_screenings (
    id                  text primary key,   -- e.g. SCR-2026-XXXX
    client_id           uuid references clients(id),
    visitor_name        text,
    visitor_contact     text,
    service_category    text not null,
    answers             jsonb default '{}',
    flagged_questions   jsonb default '[]',
    status              text default 'PENDING' check (status in ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
    reviewed_by         text,
    reviewed_at         timestamptz,
    approved_until      timestamptz,
    created_at          timestamptz default now()
);

create index if not exists idx_screenings_client       on medical_screenings (client_id);
create index if not exists idx_screenings_contact      on medical_screenings (visitor_contact);
create index if not exists idx_screenings_status       on medical_screenings (status);


-- ============================================================
-- FAQS
-- ============================================================
create table if not exists faqs (
    id          uuid primary key default gen_random_uuid(),
    question    text not null,
    answer      text not null,
    category    text
);


-- ============================================================
-- ESCALATIONS
-- Human handoff requests
-- ============================================================
create table if not exists escalations (
    id          uuid primary key default gen_random_uuid(),
    session_id  uuid references sessions(id),
    reason      text,
    reason_text text,
    created_at  timestamptz default now()
);


-- ============================================================
-- AGENT_LOGS
-- One row per conversation turn
-- ============================================================
create table if not exists agent_logs (
    id                  uuid primary key default gen_random_uuid(),
    session_id          uuid references sessions(id),
    turn                integer,
    channel             text,
    user_message        text,
    intent              text,
    confidence          numeric(4, 3),
    entities_extracted  jsonb,
    tool_called         text,
    tool_result         jsonb,
    agent_response      text,
    latency_ms          integer,
    escalated           boolean default false,
    timestamp           timestamptz default now(),
    turn_seq            integer
);

create index if not exists idx_agent_logs_session on agent_logs (session_id, turn_seq);


-- ============================================================
-- ERROR_LOGS
-- ============================================================
create table if not exists error_logs (
    id          uuid primary key default gen_random_uuid(),
    session_id  uuid,
    error_type  text,
    message     text,
    stack       text,
    created_at  timestamptz default now()
);

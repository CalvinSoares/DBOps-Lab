CREATE TABLE IF NOT EXISTS public.customers (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.tickets (
    ticket_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES public.customers(customer_id),
    subject TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.ticket_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id BIGINT NOT NULL REFERENCES public.tickets(ticket_id),
    event_type TEXT NOT NULL,
    event_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_customer_status
    ON public.tickets (customer_id, status);

CREATE INDEX IF NOT EXISTS idx_tickets_status_priority_created
    ON public.tickets (status, priority, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_created
    ON public.ticket_events (ticket_id, created_at DESC);

USE secondary_db;

CREATE TABLE IF NOT EXISTS customers (
    customer_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    full_name VARCHAR(160) NOT NULL,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id),
    UNIQUE KEY uq_customers_email (email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    customer_id BIGINT UNSIGNED NOT NULL,
    subject VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    priority TINYINT UNSIGNED NOT NULL DEFAULT 3,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticket_id),
    KEY idx_tickets_customer_status (customer_id, status),
    CONSTRAINT fk_tickets_customer
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    CONSTRAINT chk_tickets_priority CHECK (priority BETWEEN 1 AND 5)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ticket_events (
    event_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ticket_id BIGINT UNSIGNED NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    event_payload JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id),
    KEY idx_ticket_events_ticket_created (ticket_id, created_at),
    CONSTRAINT fk_ticket_events_ticket
        FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id)
) ENGINE=InnoDB;

-- Permissões mínimas e idempotentes para o exporter do laboratório.
GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'dbops_mysql'@'%';

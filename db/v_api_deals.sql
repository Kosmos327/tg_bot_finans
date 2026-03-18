-- public.v_api_deals
-- Enriched view over the deals table — joins reference tables to expose
-- both IDs and resolved names, and exposes manager_telegram_id for
-- role-based filtering in the backend.
--
-- BUG FIXED: LEFT JOIN clients c ON c.id = d.client_id was missing (or had a
-- wrong condition), so client_name was always NULL and the UI showed
-- "Клиент не указан" even when deals.client_id contained a valid value.
--
-- Column aliases match the field names expected by the backend routers
-- (backend/routers/deals_sql.py) so that WHERE clauses such as
--   manager_telegram_id = :tid
--   client_id = :client_id
--   status_id = :status_id
--   business_direction_id = :business_direction_id
-- resolve correctly against this view.

CREATE OR REPLACE VIEW public.v_api_deals AS
SELECT
    d.id,

    -- Manager
    d.manager_id,
    m.telegram_user_id          AS manager_telegram_id,
    m.manager_name,

    -- Client (FIX: correct LEFT JOIN on d.client_id = c.id)
    d.client_id,
    c.client_name,

    -- Status (expose integer id so backend can filter by status_id)
    ds.id                       AS status_id,
    d.status                    AS status_name,

    -- Business direction (expose integer id so backend can filter)
    bd.id                       AS business_direction_id,
    d.business_direction        AS business_direction_name,

    -- Financials
    d.amount_with_vat           AS charged_with_vat,
    d.vat_rate,
    d.vat_amount,
    d.amount_without_vat,
    d.paid_amount               AS paid,
    d.remaining_amount,
    d.variable_expense_1        AS variable_expense_1_without_vat,
    d.variable_expense_2        AS variable_expense_2_without_vat,
    d.production_expense        AS production_expense_without_vat,
    d.manager_bonus_pct         AS manager_bonus_percent,
    d.manager_bonus_amount,
    d.marginal_income,
    d.gross_profit,

    -- Source
    src.id                      AS source_id,
    d.source                    AS source_name,

    -- Misc
    d.document_url              AS document_link,
    d.comment,
    d.act_date,
    d.date_start                AS project_start_date,
    d.date_end                  AS project_end_date,
    d.created_at,
    d.updated_at

FROM       deals d
LEFT JOIN  managers          m   ON m.id   = d.manager_id
LEFT JOIN  clients           c   ON c.id   = d.client_id    -- FIX: joins on client_id FK
LEFT JOIN  deal_statuses     ds  ON ds.name  = d.status
LEFT JOIN  business_directions bd ON bd.name = d.business_direction
LEFT JOIN  sources           src ON src.name = d.source;

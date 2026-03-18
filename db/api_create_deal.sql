-- public.api_create_deal
-- Creates a new deal row and returns the inserted record.
--
-- Parameter order MUST match the call-site in backend/routers/deals_sql.py:
--   1. p_created_by_user_id     2. p_status_id
--   3. p_business_direction_id  4. p_client_id        ← was missing from INSERT (BUG FIX)
--   5. p_manager_id             6. p_charged_with_vat
--   7. p_vat_type_id            8. p_vat_rate
--   9. p_paid                  10. p_project_start_date
--  11. p_project_end_date      12. p_act_date
--  13. p_variable_expense_1_without_vat
--  14. p_variable_expense_2_without_vat
--  15. p_production_expense_without_vat
--  16. p_manager_bonus_percent  17. p_source_id
--  18. p_document_link         19. p_comment
--
-- BUG FIXED: p_client_id was not included in the INSERT INTO deals (...) VALUES (...)
-- which caused deals.client_id to be saved as NULL even when the frontend sent a
-- valid client_id.

CREATE OR REPLACE FUNCTION public.api_create_deal(
    p_created_by_user_id          bigint,
    p_status_id                   integer,
    p_business_direction_id       integer,
    p_client_id                   bigint,
    p_manager_id                  bigint,
    p_charged_with_vat            numeric,
    p_vat_type_id                 integer,
    p_vat_rate                    numeric,
    p_paid                        numeric,
    p_project_start_date          date,
    p_project_end_date            date,
    p_act_date                    date,
    p_variable_expense_1_without_vat numeric,
    p_variable_expense_2_without_vat numeric,
    p_production_expense_without_vat numeric,
    p_manager_bonus_percent       numeric,
    p_source_id                   integer,
    p_document_link               text,
    p_comment                     text
)
RETURNS SETOF deals
LANGUAGE plpgsql
AS $$
DECLARE
    v_status_name             text;
    v_business_direction_name text;
    v_source_name             text;
    v_vat_rate                numeric;
    v_amount_without_vat      numeric;
    v_vat_amount              numeric;
    v_remaining               numeric;
    v_marginal_income         numeric;
    v_gross_profit            numeric;
    v_manager_bonus_amount    numeric;
    v_new_id                  bigint;
BEGIN
    -- Resolve reference names from IDs
    SELECT name INTO v_status_name
    FROM   deal_statuses
    WHERE  id = p_status_id;

    SELECT name INTO v_business_direction_name
    FROM   business_directions
    WHERE  id = p_business_direction_id;

    -- Use caller-supplied vat_rate; fall back to vat_types.rate when omitted
    v_vat_rate := p_vat_rate;
    IF v_vat_rate IS NULL AND p_vat_type_id IS NOT NULL THEN
        SELECT rate INTO v_vat_rate
        FROM   vat_types
        WHERE  id = p_vat_type_id;
    END IF;

    -- VAT breakdown (vat_rate stored as percentage, e.g. 20 for 20 %)
    IF p_charged_with_vat IS NOT NULL AND v_vat_rate IS NOT NULL AND v_vat_rate > 0 THEN
        v_amount_without_vat := ROUND(
            p_charged_with_vat / (1 + v_vat_rate / 100), 2
        );
        v_vat_amount := ROUND(p_charged_with_vat - v_amount_without_vat, 2);
    ELSE
        v_amount_without_vat := p_charged_with_vat;
        v_vat_amount         := 0;
    END IF;

    -- Remaining amount
    v_remaining := GREATEST(
        COALESCE(p_charged_with_vat, 0) - COALESCE(p_paid, 0),
        0
    );

    -- Profitability metrics (using without-VAT basis)
    IF v_amount_without_vat IS NOT NULL THEN
        v_marginal_income := ROUND(
            v_amount_without_vat
            - COALESCE(p_variable_expense_1_without_vat, 0)
            - COALESCE(p_variable_expense_2_without_vat, 0),
            2
        );
        v_gross_profit := ROUND(
            v_marginal_income - COALESCE(p_production_expense_without_vat, 0),
            2
        );
        IF p_manager_bonus_percent IS NOT NULL AND p_manager_bonus_percent > 0 THEN
            v_manager_bonus_amount := ROUND(
                v_gross_profit * p_manager_bonus_percent / 100, 2
            );
        END IF;
    END IF;

    -- Optional source name
    IF p_source_id IS NOT NULL THEN
        SELECT name INTO v_source_name
        FROM   sources
        WHERE  id = p_source_id;
    END IF;

    INSERT INTO deals (
        manager_id,
        client_id,                              -- FIX: p_client_id is now inserted here
        status,
        business_direction,
        amount_with_vat,
        vat_rate,
        vat_amount,
        amount_without_vat,
        paid_amount,
        remaining_amount,
        variable_expense_1,
        variable_expense_2,
        production_expense,
        manager_bonus_pct,
        manager_bonus_amount,
        marginal_income,
        gross_profit,
        source,
        document_url,
        comment,
        act_date,
        date_start,
        date_end
    ) VALUES (
        p_manager_id,
        p_client_id,                            -- FIX: value of p_client_id passed here
        v_status_name,
        v_business_direction_name,
        p_charged_with_vat,
        v_vat_rate,
        v_vat_amount,
        v_amount_without_vat,
        COALESCE(p_paid, 0),
        v_remaining,
        p_variable_expense_1_without_vat,
        p_variable_expense_2_without_vat,
        p_production_expense_without_vat,
        p_manager_bonus_percent,
        v_manager_bonus_amount,
        v_marginal_income,
        v_gross_profit,
        v_source_name,
        p_document_link,
        p_comment,
        p_act_date,
        p_project_start_date,
        p_project_end_date
    )
    RETURNING id INTO v_new_id;

    RETURN QUERY
        SELECT * FROM deals WHERE id = v_new_id;
END;
$$;

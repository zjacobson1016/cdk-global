-- Databricks Metric View for Automated Quotes Analysis
-- Creates a semantic layer over quote data with customer, product, and notes dimensions
--Passed in job parameters: catalog and schema
USE CATALOG {{catalog}};
USE IDENTIFIER({{schema}});
CREATE OR REPLACE VIEW automated_quotes_metric_view
WITH METRICS
LANGUAGE YAML
AS $$
  version: 1.1
  comment: "Automated Quotes KPIs for sales, operations, and financial analysis"
  
  source: automated_quotes

  joins:
    - name: customers
      source: customers
      on: source.customer_id = customers.customer_id

    - name: products
      source: products
      on: source.product_id = products.product_id

    # Treating quote_notes as a dimension keyed by quote_id (1:1 in your sample).
    # If you later allow multiple notes per quote, consider joining to a
    # pre-aggregated "latest note per quote" view to avoid double-counting.
    - name: quote_notes
      source: quote_notes
      on: source.id = quote_notes.quote_id

  dimensions:
    # Fact-level identifiers & attributes
    - name: quote_id
      expr: id
    - name: customer_id
      expr: customer_id
    - name: product_id
      expr: product_id
    - name: location
      expr: location
    - name: status
      expr: status
    - name: priority
      expr: priority
    - name: assigned_reviewer
      expr: assigned_reviewer
    - name: email_source
      expr: email_source

    # Dates (casts + buckets)
    - name: order_date
      expr: TO_DATE(order_date)
    - name: order_month
      expr: DATE_TRUNC('MONTH', TO_DATE(order_date))
    - name: order_year
      expr: YEAR(TO_DATE(order_date))
    - name: created_at_ts
      expr: TO_TIMESTAMP(created_at)
    - name: updated_at_ts
      expr: TO_TIMESTAMP(updated_at)
    - name: email_received_at_ts
      expr: TO_TIMESTAMP(email_received_at)

    # Customer dimensions
    - name: customer_name
      expr: customers.company_name
    - name: customer_tier
      expr: customers.customer_tier
    - name: customer_email_domain
      expr: customers.email_domain

    # Product dimensions
    - name: product_name
      expr: products.product_name
    - name: product_category
      expr: products.category
    - name: product_price_tier
      expr: products.price_tier
    - name: product_type
      expr: products.product_type

    # Quote note dimensions (assumes 0-1 note per quote in your current data)
    - name: note_type
      expr: quote_notes.note_type
    - name: note_reviewer
      expr: quote_notes.reviewer
    - name: note_created_at
      expr: TO_TIMESTAMP(quote_notes.created_at)

  measures:
    # Core fact aggregations
    - name: quotes
      expr: COUNT(DISTINCT id)
    - name: total_quantity
      expr: SUM(quantity)
    - name: total_revenue
      expr: SUM(total_price)
    - name: avg_unit_price
      expr: AVG(unit_price)
    - name: avg_order_value
      expr: MEASURE(total_revenue) / MEASURE(quotes)

    # Status counts and rates
    - name: approved_quotes
      expr: SUM(1) FILTER (WHERE status = 'Approved')
    - name: denied_quotes
      expr: COUNT(DISTINCT id) FILTER (WHERE status = 'Denied')
    - name: pending_quotes
      expr: COUNT(DISTINCT id) FILTER (WHERE status = 'Pending')
    - name: approval_rate
      expr: MEASURE(approved_quotes) / MEASURE(quotes)
    - name: denial_rate
      expr: MEASURE(denied_quotes) / MEASURE(quotes)
    - name: pending_rate
      expr: MEASURE(pending_quotes) / MEASURE(quotes)

    # Segmented revenue
    - name: revenue_high_priority
      expr: MEASURE(total_revenue) -- FILTER (WHERE priority = 'High')
    - name: revenue_approved
      expr: MEASURE(total_revenue) -- FILTER (WHERE status = 'Approved')

    # Timeliness / ops metrics
    - name: avg_minutes_email_to_quote_create
      expr: AVG(TIMESTAMPDIFF(MINUTE, email_received_at_ts, created_at_ts))
    - name: avg_minutes_quote_to_update
      expr: AVG(TIMESTAMPDIFF(MINUTE, created_at_ts, updated_at_ts))

    # Notes coverage (uses DISTINCT to guard against future multi-note joins)
    - name: quotes_with_notes
      expr: COUNT(DISTINCT id) FILTER (WHERE note_created_at IS NOT NULL)
    - name: notes_coverage_rate
      expr: MEASURE(quotes_with_notes) / MEASURE(quotes)

    # Windowed revenue on order_date
    - name: trailing_30_day_revenue
      expr: MEASURE(total_revenue)
      window:
        - order: order_date
          range: trailing 30 days
          semiadditive: last

    - name: rolling_3_month_revenue
      expr: MEASURE(total_revenue)
      window:
        - order: order_date
          range: trailing 3 months
          semiadditive: last

    - name: previous_month_revenue
      expr: MEASURE(total_revenue)
      window:
        - order: order_date
          range: trailing 1 month
          semiadditive: last

    - name: current_month_revenue
      expr: MEASURE(total_revenue)
      window:
        - order: order_date
          range: current
          semiadditive: last

    - name: month_over_month_growth_pct
      expr: (MEASURE(current_month_revenue) - MEASURE(previous_month_revenue)) / MEASURE(previous_month_revenue) * 100
$$;

from sqlalchemy import text

get_unprocessed_posts_query = text("""
    SELECT s.post_id, s.title, s.body_text
    FROM staging.cleaned_reddit as s
    LEFT JOIN staging.llm_outputs e ON s.post_id = e.post_id
    WHERE e.post_id IS NULL
    LIMIT :batch_size
""")

insert_idea_query = text("""
    INSERT INTO staging.llm_outputs (
        post_id, is_valid_idea, confidence_score,
        problem_statement, pain_intensity, urgency,
        suggested_solution, product_category, monetization_model,
        target_audience, market_size_signal,
        existing_alternatives, competitive_gap, willingness_to_pay,
        tags
    ) VALUES (
        :post_id, :is_valid_idea, :confidence_score,
        :problem_statement, :pain_intensity, :urgency,
        :suggested_solution, :product_category, :monetization_model,
        :target_audience, :market_size_signal,
        :existing_alternatives, :competitive_gap, :willingness_to_pay,
        :tags
    )
    ON CONFLICT (post_id) DO NOTHING
""")
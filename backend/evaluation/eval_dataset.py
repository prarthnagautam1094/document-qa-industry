"""Hand-written evaluation set for the RAG pipeline, based on the actual
content of sample.pdf (the BrightWave Technologies employee handbook).

Every ground_truth below is taken verbatim or near-verbatim from the
handbook text, not guessed — RAGAS metrics compare the pipeline's real
answer against these, so a wrong or approximate ground truth would make
the scores measure "does the pipeline agree with me" instead of "does the
pipeline answer correctly."

Each entry:
  question         -- what run_eval.py sends into the pipeline.
  ground_truth      -- the correct answer, used as RAGAS's `reference`.
  history           -- prior turns (as {"role", "content"} dicts) fed into
                        generate_answer() before `question`, for the
                        follow-up-style entries. Defaults to [] (a fresh,
                        standalone question) when omitted.
  reference_context -- optional: the exact source sentence(s) the answer
                        should be grounded in. Not required by any of the
                        four metrics run here, but kept alongside each
                        entry for human review (e.g. a report appendix)
                        and for future metrics that do use it.

Mix, as required: 6 direct factual questions, 2 follow-up-style questions
(exercising rewrite_query_standalone's conversation-history handling), and
2 deliberately off-topic questions — for those last two, the *correct*
answer is the pipeline's fixed "I couldn't find relevant information..."
fallback, not a hallucinated guess, so a low answer_relevancy score there
reflects the fallback wording being generic (expected), not the pipeline
failing.
"""

EVAL_DATASET = [
    # --- Direct factual questions -------------------------------------
    {
        "question": "How many paid leaves are full-time employees entitled to per year?",
        "ground_truth": (
            "Full-time employees are entitled to 24 paid leaves per calendar year, "
            "credited at 2 leaves per month. They may carry forward a maximum of 10 "
            "unused leaves to the next year."
        ),
        "reference_context": (
            "All full-time employees are entitled to 24 paid leaves per calendar "
            "year, credited at 2 leaves per month. Employees may carry forward a "
            "maximum of 10 unused leaves to the next year."
        ),
    },
    {
        "question": "How many days of paid maternity leave are female employees entitled to?",
        "ground_truth": (
            "Female employees are entitled to 26 weeks of paid maternity leave, as "
            "per the Maternity Benefit Act."
        ),
        "reference_context": (
            "Female employees are entitled to 26 weeks of paid maternity leave as "
            "per the Maternity Benefit Act."
        ),
    },
    {
        "question": "What is the standard notice period for resignation?",
        "ground_truth": (
            "The standard notice period is 60 days for confirmed employees and 15 "
            "days for employees on probation."
        ),
        "reference_context": (
            "The standard notice period is 60 days for confirmed employees and 15 "
            "days for employees on probation."
        ),
    },
    {
        "question": "How many days per week can employees work from home without prior approval?",
        "ground_truth": (
            "Employees may work from home up to 2 days per week without prior "
            "approval. Fully remote arrangements require manager and HR approval."
        ),
        "reference_context": (
            "Employees may work from home up to 2 days per week without prior "
            "approval. Fully remote arrangements require manager and HR approval."
        ),
    },
    {
        "question": "How long is the probation period for new employees?",
        "ground_truth": "The probation period for new employees is 3 months from their date of joining.",
        "reference_context": "New employees undergo a probation period of 3 months from their date of joining.",
    },
    {
        "question": "What happens to unused leave when an employee resigns?",
        "ground_truth": "Unused leaves at the time of resignation are encashed along with the final settlement.",
        "reference_context": "Unused leaves at the time of resignation will be encashed along with the final settlement.",
    },
    # --- Follow-up-style questions (exercise conversation rewriting) ---
    {
        "history": [
            {"role": "user", "content": "What is the leave policy at BrightWave?"},
            {
                "role": "assistant",
                "content": (
                    "Full-time employees get 24 paid leaves per year, credited at 2 "
                    "per month, with sick leave capped at 8 days."
                ),
            },
        ],
        "question": "What about paternity leave specifically?",
        "ground_truth": (
            "Male employees are entitled to 15 days of paid paternity leave, which "
            "must be availed within 6 months of the child's birth."
        ),
        "reference_context": (
            "Male employees are entitled to 15 days of paid paternity leave, which "
            "must be availed within 6 months of the child's birth."
        ),
    },
    {
        "history": [
            {"role": "user", "content": "Tell me about the resignation process."},
            {
                "role": "assistant",
                "content": (
                    "Employees who wish to resign must submit a written resignation "
                    "to their manager and HR."
                ),
            },
        ],
        "question": "How much notice do I need to give if I'm still on probation?",
        "ground_truth": "You need to give 15 days' notice if you are still on probation.",
        "reference_context": (
            "The standard notice period is 60 days for confirmed employees and 15 "
            "days for employees on probation."
        ),
    },
    # --- Deliberately off-topic questions -------------------------------
    # Correct behavior is the pipeline's fixed fallback message, not an
    # invented answer — treat that fallback as a pass, not a failure.
    {
        "question": "What is the capital of France?",
        "ground_truth": "I couldn't find relevant information in the uploaded documents for this question.",
        "reference_context": None,
    },
    {
        "question": "What is BrightWave's current stock price?",
        "ground_truth": "I couldn't find relevant information in the uploaded documents for this question.",
        "reference_context": None,
    },
]

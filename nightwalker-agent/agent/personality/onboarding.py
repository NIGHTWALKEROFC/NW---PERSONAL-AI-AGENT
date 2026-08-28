"""
agent/personality/onboarding.py

Runs the onboarding interview conversationally rather than as a rigid
questionnaire. For each topic in onboarding_questions.py, it asks the
question, and if the answer looks short or vague, it asks the model to
generate ONE natural follow-up question before moving on.

This does not write to the profile itself — see profile_extractor.py
for turning the finished transcript into structured traits, and
profile_store.py for saving them. Keeping these separate means the
transcript is always available raw (stored under
profile["raw_onboarding_transcripts"]) even if extraction logic
improves later and you want to re-run it against old transcripts.
"""

import datetime

from agent.brain.model_client import ModelClient, ModelClientError
from agent.brain.model_manager import get_active_model
from agent.personality.onboarding_questions import ONBOARDING_TOPICS

# An answer shorter than this (in characters) is treated as possibly
# vague enough to warrant one natural follow-up question.
SHORT_ANSWER_THRESHOLD = 15

FOLLOW_UP_SYSTEM_PROMPT = """You are conducting a friendly personality interview.
The person just gave a short or vague answer to a question. Write ONE natural,
casual follow-up question that would draw out more useful detail. Do not repeat
the original question. Keep it to one sentence. Respond with ONLY the question,
nothing else."""


def _generate_follow_up(original_question: str, answer: str, model_name: str) -> str | None:
    client = ModelClient(model_name)
    messages = [
        {"role": "system", "content": FOLLOW_UP_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Original question: {original_question}\nTheir answer: {answer}",
        },
    ]
    try:
        result = client.chat(messages)
        return result["content"].strip()
    except ModelClientError:
        return None  # If the follow-up generation fails, just skip it — not critical.


def run_onboarding_interview(input_fn=input, print_fn=print) -> list[dict]:
    """
    Runs the interview using input_fn/print_fn (defaults to terminal
    input()/print()) so this can be tested or reused with a different
    interface (e.g. the future dashboard) without rewriting the logic.

    Returns the transcript as a list of dicts, ready for
    profile_extractor.extract_traits().
    """
    model_name = get_active_model()
    transcript = []

    print_fn(
        "\nLet's do a quick onboarding interview so the agent can start learning "
        "how you actually communicate. Answer naturally — there are no wrong answers.\n"
        "Type 'skip' to skip a question, or 'stop' to end the interview early.\n"
    )

    for topic in ONBOARDING_TOPICS:
        print_fn(f"\n{topic['question']}")
        answer = input_fn("> ").strip()

        if answer.lower() == "stop":
            print_fn("\nEnding interview early. What you've answered so far will still be saved.")
            break
        if answer.lower() == "skip" or not answer:
            continue

        turn = {
            "topic": topic["id"],
            "category": topic["category"],
            "question": topic["question"],
            "answer": answer,
            "follow_up": None,
            "follow_up_answer": None,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }

        if len(answer) < SHORT_ANSWER_THRESHOLD:
            follow_up = _generate_follow_up(topic["question"], answer, model_name)
            if follow_up:
                print_fn(f"{follow_up}")
                follow_up_answer = input_fn("> ").strip()
                if follow_up_answer and follow_up_answer.lower() not in ("skip", "stop"):
                    turn["follow_up"] = follow_up
                    turn["follow_up_answer"] = follow_up_answer

        transcript.append(turn)

    print_fn("\nThanks — that's everything for now.\n")
    return transcript

"""
agent/personality/onboarding_questions.py

The topic list the onboarding interview walks through. Each topic maps
to something from the original spec (section 1: onboarding/personality
learning). Questions are written to sound like a natural conversation
opener, not a form field label — the interview flow in onboarding.py
uses the model to generate a follow-up when an answer seems too short
or vague to be useful.

Order matters a little: boundaries/never-say/permissions are asked
near the end, once the person has warmed up talking about themselves.
"""

ONBOARDING_TOPICS = [
    {
        "id": "close_friends_style",
        "category": "communication_style",
        "question": "How do you usually text your close friends? Feel free to just describe it naturally.",
    },
    {
        "id": "strangers_style",
        "category": "communication_style",
        "question": "And how does that change when you're talking to someone you don't know well, or a stranger online?",
    },
    {
        "id": "emoji_usage",
        "category": "communication_style",
        "question": "Do you use emojis much? If so, which ones do you actually reach for?",
    },
    {
        "id": "slang_and_abbreviations",
        "category": "communication_style",
        "question": "Any slang, abbreviations, or shortcuts you use a lot when typing?",
    },
    {
        "id": "language_mixing",
        "category": "communication_style",
        "question": "Do you mix Malayalam and English when you chat? How does that usually happen?",
    },
    {
        "id": "punctuation_and_caps",
        "category": "communication_style",
        "question": "Do you bother with punctuation and capital letters when texting casually, or do you keep it lowercase/loose?",
    },
    {
        "id": "message_length",
        "category": "communication_style",
        "question": "Do you tend to send short quick messages, or longer ones? Or does it depend a lot?",
    },
    {
        "id": "humor_style",
        "category": "communication_style",
        "question": "How would you describe your sense of humor when chatting — sarcastic, playful, dry, rare, something else?",
    },
    {
        "id": "response_when_happy",
        "category": "behavioral_patterns",
        "question": "How does your texting change when you're in a good mood?",
    },
    {
        "id": "response_when_angry",
        "category": "behavioral_patterns",
        "question": "What about when you're annoyed or angry — how does that show up in how you reply?",
    },
    {
        "id": "response_when_busy",
        "category": "behavioral_patterns",
        "question": "When you're busy, what happens to your replies — do they get shorter, delayed, skipped entirely?",
    },
    {
        "id": "response_to_serious_topics",
        "category": "behavioral_patterns",
        "question": "How do you handle it when someone brings up something serious or heavy in a chat?",
    },
    {
        "id": "messages_ignored",
        "category": "behavioral_patterns",
        "question": "What kind of messages do you normally just... not reply to, or leave on read?",
    },
    {
        "id": "messages_urgent",
        "category": "behavioral_patterns",
        "question": "What kind of message makes you drop everything and reply immediately?",
    },
    {
        "id": "conversation_starters",
        "category": "behavioral_patterns",
        "question": "How do you usually start a conversation with someone?",
    },
    {
        "id": "conversation_enders",
        "category": "behavioral_patterns",
        "question": "And how do you usually end one, or let it fade out?",
    },
    {
        "id": "never_say",
        "category": "boundaries",
        "question": "Now something important: is there anything you'd never want this agent to say on your behalf — phrases, topics, tones, anything off-limits?",
    },
    {
        "id": "approval_required_actions",
        "category": "boundaries",
        "question": "What kinds of actions should always need your approval before happening, even if the agent is pretty confident?",
    },
    {
        "id": "never_allowed_actions",
        "category": "boundaries",
        "question": "And what should the agent NEVER be allowed to do, full stop, no exceptions?",
    },
]

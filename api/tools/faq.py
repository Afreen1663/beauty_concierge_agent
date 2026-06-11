from api.database import supabase


def lookup_faq(question: str) -> dict:
    """
    Searches the FAQ table for a relevant answer.
    Uses simple text search (no pgvector needed for prototype).
    Returns the best matching answer or a fallback.
    """

    # Extract keywords from the question
    keywords = [
        word.lower() for word in question.split()
        if len(word) > 3 and word.lower() not in
        ["what", "when", "where", "how", "does", "your", "have", "that", "this", "with"]
    ]

    if not keywords:
        return {
            "status": "NOT_FOUND",
            "answer": (
                "I'm not sure about that one. You can contact our team directly "
                "at either branch and they'll be happy to help."
            )
        }

    try:
        # Try each keyword and return first match
        for keyword in keywords:
            result = supabase.table("faqs").select("question, answer") \
                .ilike("question", f"%{keyword}%") \
                .limit(1).execute()

            if result.data:
                return {
                    "status": "FOUND",
                    "answer": result.data[0]["answer"],
                    "matched_question": result.data[0]["question"]
                }

            # Also search in answer text
            result = supabase.table("faqs").select("question, answer") \
                .ilike("answer", f"%{keyword}%") \
                .limit(1).execute()

            if result.data:
                return {
                    "status": "FOUND",
                    "answer": result.data[0]["answer"],
                    "matched_question": result.data[0]["question"]
                }

    except Exception as e:
        return {
            "status": "ERROR",
            "answer": "I couldn't look that up right now. Please contact the branch directly."
        }

    return {
        "status": "NOT_FOUND",
        "answer": (
            "I don't have that information to hand. For anything I can't answer, "
            "you're welcome to call either branch and our team will help you out."
        )
    }
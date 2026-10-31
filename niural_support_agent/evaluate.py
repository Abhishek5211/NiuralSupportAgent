"""One selected benchmark question; no automatic judging or file output."""

async def evaluate_one(agent, case):
    session_id = f"benchmark-{case['id']}"
    agent.reset(session_id)
    context = ([{"role": "user", "content":
                 "The freight payment I am asking about has transaction reference txn-88403."}]
               if case["id"] == 8 else [])
    outcome = await agent.ask(session_id, case["question"], context=context)
    return {"id": case["id"], "question": case["question"], "context": context, **outcome.model_dump()}

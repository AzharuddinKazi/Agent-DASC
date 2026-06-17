from agents.graph import build_graph
import uuid

graph = build_graph()

initial_state = {
    "task_id":               str(uuid.uuid4()),
    "query":                 "What is the total transaction amount by currency in test.csv?",
    "formatting_guidelines": "Print a table with currency and total amount",
    "data_descriptions":     {},
    "cumulative_plan":       [],
    "current_script":        "",
    "execution_result":      "",
    "exit_code":             0,
    "current_round":         0,
    "max_rounds":            5,
    "verifier_verdict":      "",
    "router_decision":       "",
    "status":                "queued",
    "final_result":          None,
}

config = {"configurable": {"thread_id": initial_state["task_id"]}}

print("Starting DS-STAR graph...")
print(f"Query: {initial_state['query']}")
print("-" * 50)

result = graph.invoke(initial_state, config=config)

print("-" * 50)
print(f"Status:       {result['status']}")
print(f"Rounds taken: {result['current_round']}")
print(f"Plan steps:   {len(result['cumulative_plan'])}")
print(f"\nFinal result:\n{result['final_result']}")
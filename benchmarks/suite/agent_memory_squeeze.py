def search_memory(memory, query):
    results = []
    for entry in memory:
        if query.lower() in str(entry["value"]).lower():
            results.append(entry)
    return results


def main():
    memory = []

    # Remember first message
    memory.append(
        {"key": "1", "value": "Secret key is: ZOLTREX_VIP_KEY", "namespace": "session"}
    )

    # 100 consecutive chatty questions
    for i in range(100):
        memory.append(
            {
                "key": str(i + 2),
                "value": "Chatty user question about system status or billing updates in Zoltrex Arena",
                "namespace": "session",
            }
        )

    # Recall via search
    results = search_memory(memory, "secret key")
    if results:
        # Sort by updated/created index (most recent first)
        secret_val = results[0]["value"]
    else:
        secret_val = None

    print(secret_val)


if __name__ == "__main__":
    main()

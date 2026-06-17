# Simulated tools
def mock_search(query, limit=5):
    if not isinstance(limit, int):
        raise TypeError("limit must be an int")
    return [{"title": f"Result for {query}", "snippet": "Snippet content"}]


def main():
    result = ""
    attempts = 0
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        try:
            attempts += 1
            if attempts == 1:
                # Call non-existent tool
                raise NameError("tool invalid_tool_name not defined")
            elif attempts == 2:
                # Schema validation error
                mock_search("INTHON", limit="high")
            elif attempts == 3:
                # Valid call
                search_res = mock_search("INTHON", limit=1)
                result = search_res[0]["title"]
                break
        except Exception as e:
            if attempt == max_retries:
                result = f"Failed to recover: {e}"

    print(result)


if __name__ == "__main__":
    main()

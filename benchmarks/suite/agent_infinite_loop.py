class SandboxViolationError(Exception):
    pass


def mock_search(query, call_count):
    if call_count >= 5:
        raise SandboxViolationError("Tool call limit of 5 exceeded")
    return [{"title": f"Result for {query}"}]


def main():
    call_count = 0
    found = False
    query = "secret_query"

    try:
        while not found:
            mock_search(query, call_count)
            call_count += 1
    except SandboxViolationError as e:
        print(f"Halted: {e}")


if __name__ == "__main__":
    main()

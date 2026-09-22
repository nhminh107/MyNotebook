import json

from ddgs.exceptions import DDGSException

from BackEnd.app.chatbot.tools import ToolList, WEB_SEARCH_BACKENDS


def test_web_search_is_registered_with_a_simple_schema() -> None:
    tool_list = ToolList.__new__(ToolList)
    tool_list.tools = []

    tool_list._search_tool()

    assert len(tool_list.tools) == 1
    assert tool_list.tools[0].name == "web_search"
    assert set(tool_list.tools[0].args) == {"query", "max_results"}


def test_web_search_falls_back_to_next_backend() -> None:
    tool_list = ToolList.__new__(ToolList)
    calls = []

    def search_backend(query: str, backend: str, max_results: int) -> list[dict]:
        calls.append((query, backend, max_results))
        if backend == WEB_SEARCH_BACKENDS[0]:
            raise DDGSException("DNS unavailable")
        return [
            {
                "title": "Example result",
                "body": "Example snippet",
                "href": "https://example.com/result",
            }
        ]

    tool_list._search_backend = search_backend

    response = json.loads(tool_list._web_search_tool("example query", max_results=3))

    assert response == {
        "status": "ok",
        "backend": WEB_SEARCH_BACKENDS[1],
        "results": [
            {
                "title": "Example result",
                "snippet": "Example snippet",
                "url": "https://example.com/result",
            }
        ],
    }
    assert calls == [
        ("example query", WEB_SEARCH_BACKENDS[0], 3),
        ("example query", WEB_SEARCH_BACKENDS[1], 3),
    ]


def test_web_search_returns_unavailable_when_all_backends_fail() -> None:
    tool_list = ToolList.__new__(ToolList)

    def search_backend(query: str, backend: str, max_results: int) -> list[dict]:
        raise DDGSException("Network unavailable")

    tool_list._search_backend = search_backend

    response = json.loads(tool_list._web_search_tool("example query"))

    assert response["status"] == "unavailable"
    assert response["attempted_backends"] == list(WEB_SEARCH_BACKENDS)


def test_web_search_rejects_an_empty_query() -> None:
    tool_list = ToolList.__new__(ToolList)

    response = json.loads(tool_list._web_search_tool("   "))

    assert response == {
        "status": "invalid_query",
        "message": "Search query is empty.",
    }

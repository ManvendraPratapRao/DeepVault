import pytest

from app.api.schemas.requests import QueryAPIRequest
from app.core.exceptions import RetrievalError
from app.services.query import QueryService


@pytest.fixture
def query_service(mock_retriever, mock_llm_client):
    return QueryService(retriever=mock_retriever, llm_client=mock_llm_client)


@pytest.mark.asyncio
async def test_ask_returns_response(query_service, mock_retriever, mock_llm_client):
    request = QueryAPIRequest(query_text="What is DeepVault?", top_k=3)

    response = await query_service.ask(request)

    assert response is not None
    assert response.answer == "This is a mocked LLM answer."
    assert len(response.sources) == 3
    assert response.latency_ms > 0
    assert response.request_id is not None

    mock_retriever.retrieve.assert_awaited_once_with(query="What is DeepVault?", top_k=5, filters=None)
    mock_llm_client.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_ask_no_results_raises(query_service, mock_retriever):
    mock_retriever.retrieve.return_value = []
    request = QueryAPIRequest(query_text="What is DeepVault?", top_k=3)

    with pytest.raises(RetrievalError):
        await query_service.ask(request)


@pytest.mark.asyncio
async def test_latency_measured(query_service):
    request = QueryAPIRequest(query_text="latency test", top_k=3)
    response = await query_service.ask(request)

    assert isinstance(response.latency_ms, float)
    assert response.latency_ms >= 0.0

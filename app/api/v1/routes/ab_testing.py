from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_api_key
from app.dependencies import get_ab_testing_service
from app.services.ab_testing import ABTestingService

router = APIRouter()


@router.get("/results", response_model=list[dict[str, Any]])
async def get_ab_test_results(
    service: ABTestingService = Depends(get_ab_testing_service),
    _auth: str = Depends(get_api_key),
):
    """
    Returns the results of all active A/B tests, including statistical significance.
    """
    active_tests = await service.list_active_tests()
    results = []

    for test in active_tests:
        test_result = await service.get_results(test["name"])
        results.append(test_result)

    return results


@router.get("/active", response_model=list[dict[str, Any]])
async def get_active_tests(
    service: ABTestingService = Depends(get_ab_testing_service),
    _auth: str = Depends(get_api_key),
):
    """
    Returns the list of currently active A/B tests and their configurations.
    """
    return await service.list_active_tests()

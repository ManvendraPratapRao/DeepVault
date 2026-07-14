import logging

from fastapi import FastAPI
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings

logger = logging.getLogger(__name__)

def setup_tracing(app: FastAPI = None):
    if not settings.PHOENIX_ENABLED:
        logger.info("Phoenix tracing is disabled via config.")
        return

    # Start Phoenix if not running locally, though we assume Docker Phoenix is running
    # We will just point OTLP to the Phoenix collector endpoint
    
    # 1. Set up the OTLP Exporter pointing to Phoenix
    resource = Resource(attributes={
        "service.name": settings.PHOENIX_PROJECT_NAME,
        "service.version": settings.VERSION,
    })
    
    provider = TracerProvider(resource=resource)
    
    # Send traces to local Phoenix instance (usually http://localhost:6006/v1/traces)
    exporter = OTLPSpanExporter(endpoint=settings.PHOENIX_ENDPOINT)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    
    # Set the global default tracer provider
    trace.set_tracer_provider(provider)
    
    # Instrument LiteLLM (which underpins our LLM calls) automatically
    # This captures LLM prompts, token counts, and completion data for Phoenix natively!
    try:
        LiteLLMInstrumentor().instrument()
        if app:
            FastAPIInstrumentor.instrument_app(app)
        logger.info(f"OpenTelemetry tracing enabled. Sending to Phoenix at {settings.PHOENIX_ENDPOINT}")
    except Exception as e:
        logger.error(f"Failed to instrument LiteLLM for Phoenix: {e}")

def get_tracer(name: str):
    return trace.get_tracer(name)

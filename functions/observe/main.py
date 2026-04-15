# OBSERVE Pillar - Main Cloud Function
# Entry point for the GCP AI-Native Self-Healing DevOps telemetry collection

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import functions_framework

from .collectors import (
    CloudLoggingCollector,
    CloudMonitoringCollector,
    CloudTraceCollector
)
from .models import CollectorResult, Incident
from .processors import IncidentProcessor
from .utils import BigQueryClient, EventarcClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
PROJECT_ID = os.getenv('GCP_PROJECT', '')
BIGQUERY_DATASET = os.getenv('BIGQUERY_DATASET', 'devops_observe')
BIGQUERY_TABLE = os.getenv('BIGQUERY_TABLE', 'incidents')


@functions_framework.http
def observe_incidents(request):
    """
    Main Cloud Function entry point for incident observation.

    This function is triggered by:
    1. HTTP requests (manual/API calls)
    2. Cloud Scheduler (periodic collection)
    3. Eventarc events (real-time triggers)
    4. Pub/Sub messages (async processing)

    Args:
        request: Flask request object

    Returns:
        JSON response with collection results
    """
    try:
        logger.info("Starting OBSERVE pillar incident collection")

        # Parse request parameters
        params = _parse_request_params(request)

        # Initialize collectors
        collectors = _initialize_collectors(PROJECT_ID)

        # Collect data from all sources
        collection_results = _collect_from_all_sources(collectors, params)

        # Process and correlate incidents
        incidents = _process_and_correlate_incidents(collection_results)

        # Store results
        storage_result = _store_results(incidents, collection_results)

        # Send to next pillar (ANALYZE) via Eventarc
        _forward_to_analyze_pillar(incidents)

        # Return response
        response = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "pillar": "OBSERVE",
            "collection_results": [result.__dict__ for result in collection_results],
            "incidents_detected": len(incidents),
            "storage_result": storage_result,
            "next_pillar_triggered": len(incidents) > 0
        }

        logger.info(f"OBSERVE pillar completed successfully. Detected {len(incidents)} incidents.")
        return json.dumps(response, indent=2), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        logger.error(f"Error in OBSERVE pillar: {str(e)}", exc_info=True)

        error_response = {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "pillar": "OBSERVE",
            "error": str(e),
            "collection_results": [],
            "incidents_detected": 0
        }

        return json.dumps(error_response, indent=2), 500, {'Content-Type': 'application/json'}


@functions_framework.cloud_event
def observe_incidents_event(event):
    """
    Cloud Event handler for Eventarc triggers.

    Args:
        event: CloudEvent object
    """
    try:
        logger.info(f"Received Cloud Event: {event['type']}")

        # Extract event data
        event_data = event.data if hasattr(event, 'data') else {}

        # Convert to HTTP request format for processing
        mock_request = type('MockRequest', (), {
            'get_json': lambda: event_data,
            'args': event_data
        })()

        # Process using main function
        return observe_incidents(mock_request)

    except Exception as e:
        logger.error(f"Error processing Cloud Event: {str(e)}", exc_info=True)
        raise


def _parse_request_params(request) -> Dict[str, Any]:
    """Parse request parameters for collection configuration"""
    try:
        # Get JSON data
        data = request.get_json(silent=True) or {}

        # Extract parameters with defaults
        params = {
            "time_window_minutes": data.get("time_window_minutes", 5),
            "max_results_per_collector": data.get("max_results", 1000),
            "resource_filter": data.get("resource_filter"),
            "severity_filter": data.get("severity_filter"),
            "collect_logging": data.get("collect_logging", True),
            "collect_monitoring": data.get("collect_monitoring", True),
            "collect_traces": data.get("collect_traces", True),
            "correlation_enabled": data.get("correlation_enabled", True)
        }

        logger.info(f"Parsed request parameters: {params}")
        return params

    except Exception as e:
        logger.warning(f"Error parsing request parameters: {e}")
        return {
            "time_window_minutes": 5,
            "max_results_per_collector": 1000,
            "collect_logging": True,
            "collect_monitoring": True,
            "collect_traces": True,
            "correlation_enabled": True
        }


def _initialize_collectors(project_id: str) -> Dict[str, Any]:
    """Initialize all data collectors"""
    try:
        collectors = {
            "logging": CloudLoggingCollector(project_id),
            "monitoring": CloudMonitoringCollector(project_id),
            "trace": CloudTraceCollector(project_id)
        }

        logger.info("Initialized all collectors successfully")
        return collectors

    except Exception as e:
        logger.error(f"Error initializing collectors: {e}")
        raise


def _collect_from_all_sources(collectors: Dict[str, Any], params: Dict[str, Any]) -> List[CollectorResult]:
    """Collect data from all configured sources"""
    results = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=params["time_window_minutes"])

    # Collect from logging
    if params.get("collect_logging", True):
        try:
            logger.info("Collecting from Cloud Logging...")
            result = collectors["logging"].collect_and_detect(
                start_time=start_time,
                end_time=end_time,
                max_results=params["max_results_per_collector"]
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Error collecting from logging: {e}")
            results.append(CollectorResult(
                collector_name="cloud_logging",
                success=False,
                data_count=0,
                incidents_detected=0,
                errors=[str(e)]
            ))

    # Collect from monitoring
    if params.get("collect_monitoring", True):
        try:
            logger.info("Collecting from Cloud Monitoring...")
            result = collectors["monitoring"].collect_and_detect(
                start_time=start_time,
                end_time=end_time,
                alignment_period=300  # 5 minutes
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Error collecting from monitoring: {e}")
            results.append(CollectorResult(
                collector_name="cloud_monitoring",
                success=False,
                data_count=0,
                incidents_detected=0,
                errors=[str(e)]
            ))

    # Collect from traces
    if params.get("collect_traces", True):
        try:
            logger.info("Collecting from Cloud Trace...")
            result = collectors["trace"].collect_and_detect(
                start_time=start_time,
                end_time=end_time,
                max_results=params["max_results_per_collector"]
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Error collecting from traces: {e}")
            results.append(CollectorResult(
                collector_name="cloud_trace",
                success=False,
                data_count=0,
                incidents_detected=0,
                errors=[str(e)]
            ))

    logger.info(f"Completed collection from {len(results)} sources")
    return results


def _process_and_correlate_incidents(collection_results: List[CollectorResult]) -> List[Incident]:
    """Process and correlate incidents from all collectors"""
    try:
        all_incidents = []

        # Extract incidents from results
        for result in collection_results:
            if result.success and hasattr(result, 'metadata') and 'incidents' in result.metadata:
                incidents_data = result.metadata['incidents']
                for incident_data in incidents_data:
                    try:
                        incident = Incident.from_dict(incident_data)
                        all_incidents.append(incident)
                    except Exception as e:
                        logger.warning(f"Error parsing incident: {e}")

        # Correlate related incidents
        if len(all_incidents) > 1:
            correlated_incidents = _correlate_incidents(all_incidents)
        else:
            correlated_incidents = all_incidents

        logger.info(f"Processed {len(correlated_incidents)} incidents after correlation")
        return correlated_incidents

    except Exception as e:
        logger.error(f"Error processing incidents: {e}")
        return []


def _correlate_incidents(incidents: List[Incident]) -> List[Incident]:
    """Correlate related incidents from different sources"""
    # Simple correlation based on resource and time proximity
    correlated = []
    processed_ids = set()

    for incident in incidents:
        if incident.id in processed_ids:
            continue

        # Find related incidents within 5 minutes and same resource
        related = [incident]
        for other in incidents:
            if (other.id != incident.id and
                other.id not in processed_ids and
                other.resource.resource_name == incident.resource.resource_name and
                abs((other.timestamp - incident.timestamp).total_seconds()) < 300):  # 5 minutes

                related.append(other)
                processed_ids.add(other.id)

        if len(related) > 1:
            # Merge related incidents
            merged = _merge_related_incidents(related)
            correlated.append(merged)
        else:
            correlated.append(incident)

        processed_ids.add(incident.id)

    return correlated


def _merge_related_incidents(incidents: List[Incident]) -> Incident:
    """Merge multiple related incidents into one"""
    # Use the most severe incident as base
    base_incident = max(incidents, key=lambda x: x.severity.value)

    # Combine data from all incidents
    all_logs = []
    all_metrics = []
    all_traces = []

    for incident in incidents:
        all_logs.extend(incident.logs)
        all_metrics.extend(incident.metrics)
        all_traces.extend(incident.traces)

    # Update base incident with combined data
    base_incident.logs = all_logs
    base_incident.metrics = all_metrics
    base_incident.traces = all_traces

    # Update description to reflect correlation
    base_incident.description += f" (Correlated from {len(incidents)} sources)"
    base_incident.tags["correlated_sources"] = len(incidents)

    return base_incident


def _store_results(incidents: List[Incident], collection_results: List[CollectorResult]) -> Dict[str, Any]:
    """Store incidents and collection results in BigQuery"""
    try:
        bq_client = BigQueryClient(PROJECT_ID, BIGQUERY_DATASET, BIGQUERY_TABLE)

        stored_incidents = 0
        for incident in incidents:
            try:
                bq_client.store_incident(incident)
                stored_incidents += 1
            except Exception as e:
                logger.error(f"Error storing incident {incident.id}: {e}")

        return {
            "success": True,
            "incidents_stored": stored_incidents,
            "total_incidents": len(incidents)
        }

    except Exception as e:
        logger.error(f"Error storing results: {e}")
        return {
            "success": False,
            "error": str(e),
            "incidents_stored": 0,
            "total_incidents": len(incidents)
        }


def _forward_to_analyze_pillar(incidents: List[Incident]) -> None:
    """Forward detected incidents to the ANALYZE pillar via Eventarc"""
    if not incidents:
        logger.info("No incidents to forward to ANALYZE pillar")
        return

    try:
        eventarc_client = EventarcClient(PROJECT_ID)

        for incident in incidents:
            try:
                eventarc_client.publish_incident_event(incident, "analyze")
                logger.info(f"Forwarded incident {incident.id} to ANALYZE pillar")
            except Exception as e:
                logger.error(f"Error forwarding incident {incident.id}: {e}")

    except Exception as e:
        logger.error(f"Error initializing Eventarc client: {e}")


# Health check endpoint
@functions_framework.http
def health_check(request):
    """Health check endpoint for the OBSERVE pillar"""
    return json.dumps({
        "status": "healthy",
        "pillar": "OBSERVE",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }), 200, {'Content-Type': 'application/json'}
# Cloud Logging Collector
# Collects and analyzes Cloud Logging entries for incident detection

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.cloud import logging as cloud_logging
from google.api_core.exceptions import GoogleAPIError

from ..models import (
    LogEntry,
    Incident,
    IncidentSeverity,
    IncidentSource,
    GCPResource,
    CollectorResult
)

logger = logging.getLogger(__name__)


class CloudLoggingCollector:
    """Collector for Cloud Logging data"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = cloud_logging.Client(project=project_id)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def collect_logs(
        self,
        filter_str: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_results: int = 1000
    ) -> List[LogEntry]:
        """
        Collect log entries based on filter criteria

        Args:
            filter_str: Cloud Logging filter string
            start_time: Start time for log collection
            end_time: End time for log collection
            max_results: Maximum number of log entries to collect

        Returns:
            List of LogEntry objects
        """
        try:
            # Set default time range if not provided
            if not end_time:
                end_time = datetime.utcnow()
            if not start_time:
                start_time = end_time - timedelta(minutes=5)

            # Build filter
            base_filter = f'timestamp>="{start_time.isoformat()}Z" AND timestamp<="{end_time.isoformat()}Z"'
            if filter_str:
                base_filter += f" AND {filter_str}"

            self.logger.info(f"Collecting logs with filter: {base_filter}")

            # Get log entries
            entries = self.client.list_entries(
                filter_=base_filter,
                max_results=max_results,
                order_by=cloud_logging.DESCENDING
            )

            log_entries = []
            for entry in entries:
                log_entry = self._convert_to_log_entry(entry)
                if log_entry:
                    log_entries.append(log_entry)

            self.logger.info(f"Collected {len(log_entries)} log entries")
            return log_entries

        except GoogleAPIError as e:
            self.logger.error(f"Error collecting logs: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in log collection: {e}")
            raise

    def detect_incidents(self, log_entries: List[LogEntry]) -> List[Incident]:
        """
        Analyze log entries and detect potential incidents

        Args:
            log_entries: List of log entries to analyze

        Returns:
            List of detected incidents
        """
        incidents = []

        # Group logs by resource for analysis
        resource_logs = self._group_logs_by_resource(log_entries)

        for resource_key, logs in resource_logs.items():
            incident = self._analyze_resource_logs(resource_key, logs)
            if incident:
                incidents.append(incident)

        self.logger.info(f"Detected {len(incidents)} incidents from {len(log_entries)} log entries")
        return incidents

    def collect_and_detect(
        self,
        filter_str: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_results: int = 1000
    ) -> CollectorResult:
        """
        Collect logs and detect incidents in one operation

        Returns:
            CollectorResult with collected data and detected incidents
        """
        errors = []
        incidents_detected = 0

        try:
            # Collect logs
            log_entries = self.collect_logs(filter_str, start_time, end_time, max_results)

            # Detect incidents
            incidents = self.detect_incidents(log_entries)
            incidents_detected = len(incidents)

            return CollectorResult(
                collector_name="cloud_logging",
                success=True,
                data_count=len(log_entries),
                incidents_detected=incidents_detected,
                metadata={
                    "filter_used": filter_str,
                    "time_range": {
                        "start": start_time.isoformat() if start_time else None,
                        "end": end_time.isoformat() if end_time else None
                    },
                    "incidents": [incident.to_dict() for incident in incidents]
                }
            )

        except Exception as e:
            error_msg = f"Error in collect_and_detect: {str(e)}"
            self.logger.error(error_msg)
            errors.append(error_msg)

            return CollectorResult(
                collector_name="cloud_logging",
                success=False,
                data_count=0,
                incidents_detected=0,
                errors=errors
            )

    def _convert_to_log_entry(self, entry: cloud_logging.LogEntry) -> Optional[LogEntry]:
        """Convert Cloud Logging entry to our LogEntry model"""
        try:
            # Extract resource information
            resource = entry.resource
            gcp_resource = GCPResource(
                project_id=self.project_id,
                resource_type=resource.type if resource else "unknown",
                resource_name=getattr(resource, 'labels', {}).get('resource_name', 'unknown'),
                location=getattr(resource, 'labels', {}).get('location', 'unknown'),
                labels=dict(getattr(resource, 'labels', {}))
            )

            # Extract trace information
            trace_id = None
            span_id = None
            if hasattr(entry, 'trace') and entry.trace:
                # Parse trace path: projects/{project}/traces/{trace_id}/spans/{span_id}
                trace_parts = entry.trace.split('/')
                if len(trace_parts) >= 6:
                    trace_id = trace_parts[5]
                    if len(trace_parts) >= 8:
                        span_id = trace_parts[7]

            return LogEntry(
                timestamp=entry.timestamp,
                severity=entry.severity or "DEFAULT",
                message=str(entry.payload) if entry.payload else "",
                resource=gcp_resource,
                labels=dict(getattr(entry, 'labels', {})),
                trace_id=trace_id,
                span_id=span_id
            )

        except Exception as e:
            self.logger.warning(f"Error converting log entry: {e}")
            return None

    def _group_logs_by_resource(self, log_entries: List[LogEntry]) -> Dict[str, List[LogEntry]]:
        """Group log entries by GCP resource"""
        resource_groups = {}

        for entry in log_entries:
            resource_key = f"{entry.resource.resource_type}:{entry.resource.resource_name}"
            if resource_key not in resource_groups:
                resource_groups[resource_key] = []
            resource_groups[resource_key].append(entry)

        return resource_groups

    def _analyze_resource_logs(self, resource_key: str, logs: List[LogEntry]) -> Optional[Incident]:
        """Analyze logs for a specific resource and detect incidents"""
        if not logs:
            return None

        # Sort logs by timestamp
        logs.sort(key=lambda x: x.timestamp)

        # Check for error patterns
        error_logs = [log for log in logs if log.severity in ['ERROR', 'CRITICAL', 'ALERT']]
        warning_logs = [log for log in logs if log.severity in ['WARNING']]

        # Determine if this constitutes an incident
        incident_severity = self._calculate_severity(error_logs, warning_logs, logs)

        if incident_severity in [IncidentSeverity.CRITICAL, IncidentSeverity.HIGH]:
            # Create incident
            latest_log = logs[-1]
            incident_id = f"logging-{resource_key.replace(':', '-')}-{int(datetime.utcnow().timestamp())}"

            return Incident(
                id=incident_id,
                timestamp=latest_log.timestamp,
                severity=incident_severity,
                source=IncidentSource.LOGGING,
                title=self._generate_incident_title(error_logs, latest_log),
                description=self._generate_incident_description(error_logs, warning_logs),
                resource=latest_log.resource,
                logs=logs,
                detected_by="cloud_logging_collector",
                confidence_score=self._calculate_confidence(error_logs, warning_logs, logs)
            )

        return None

    def _calculate_severity(
        self,
        error_logs: List[LogEntry],
        warning_logs: List[LogEntry],
        all_logs: List[LogEntry]
    ) -> IncidentSeverity:
        """Calculate incident severity based on log analysis"""
        error_count = len(error_logs)
        warning_count = len(warning_logs)
        total_count = len(all_logs)

        # Critical: Multiple errors or high error ratio
        if error_count >= 3 or (error_count / total_count > 0.5 if total_count > 0 else False):
            return IncidentSeverity.CRITICAL

        # High: Single error or significant warnings
        if error_count >= 1 or warning_count >= 5:
            return IncidentSeverity.HIGH

        # Medium: Some warnings
        if warning_count >= 2:
            return IncidentSeverity.MEDIUM

        return IncidentSeverity.LOW

    def _generate_incident_title(self, error_logs: List[LogEntry], latest_log: LogEntry) -> str:
        """Generate a descriptive incident title"""
        if error_logs:
            return f"Error detected in {latest_log.resource.resource_type}: {error_logs[0].message[:100]}..."
        else:
            return f"Anomalous activity in {latest_log.resource.resource_type}"

    def _generate_incident_description(
        self,
        error_logs: List[LogEntry],
        warning_logs: List[LogEntry]
    ) -> str:
        """Generate detailed incident description"""
        description_parts = []

        if error_logs:
            description_parts.append(f"Found {len(error_logs)} error log(s)")
        if warning_logs:
            description_parts.append(f"Found {len(warning_logs)} warning log(s)")

        if not description_parts:
            description_parts.append("Anomalous log patterns detected")

        return ". ".join(description_parts)

    def _calculate_confidence(
        self,
        error_logs: List[LogEntry],
        warning_logs: List[LogEntry],
        all_logs: List[LogEntry]
    ) -> float:
        """Calculate confidence score for incident detection"""
        error_ratio = len(error_logs) / len(all_logs) if all_logs else 0
        warning_ratio = len(warning_logs) / len(all_logs) if all_logs else 0

        # Higher confidence with more severe logs
        confidence = min(1.0, (error_ratio * 2.0) + (warning_ratio * 0.5) + 0.1)
        return round(confidence, 2)
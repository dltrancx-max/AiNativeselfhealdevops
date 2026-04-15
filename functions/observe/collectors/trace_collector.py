# Cloud Trace Collector
# Collects and analyzes Cloud Trace data for incident detection

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.cloud import trace_v2
from google.api_core.exceptions import GoogleAPIError

from ..models import (
    TraceSpan,
    Incident,
    IncidentSeverity,
    IncidentSource,
    GCPResource,
    CollectorResult
)

logger = logging.getLogger(__name__)


class CloudTraceCollector:
    """Collector for Cloud Trace data"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = trace_v2.TraceServiceClient()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def collect_traces(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filter_str: Optional[str] = None,
        max_results: int = 1000
    ) -> List[TraceSpan]:
        """
        Collect trace data from Cloud Trace

        Args:
            start_time: Start time for trace collection
            end_time: End time for trace collection
            filter_str: Additional filter string
            max_results: Maximum number of traces to collect

        Returns:
            List of TraceSpan objects
        """
        try:
            # Set default time range
            if not end_time:
                end_time = datetime.utcnow()
            if not start_time:
                start_time = end_time - timedelta(minutes=5)

            # Build request
            request = trace_v2.ListTracesRequest(
                parent=f"projects/{self.project_id}",
                start_time=start_time,
                end_time=end_time,
                filter=filter_str or "",
                order_by="start_time desc",
                page_size=min(max_results, 1000)  # API limit
            )

            self.logger.info(f"Collecting traces from {start_time} to {end_time}")

            # Get traces
            traces = self.client.list_traces(request)

            trace_spans = []
            for trace in traces:
                spans = self._get_trace_spans(trace.trace_id)
                trace_spans.extend(spans)

                if len(trace_spans) >= max_results:
                    break

            self.logger.info(f"Collected {len(trace_spans)} trace spans")
            return trace_spans[:max_results]

        except GoogleAPIError as e:
            self.logger.error(f"Error collecting traces: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in trace collection: {e}")
            raise

    def detect_incidents(self, trace_spans: List[TraceSpan]) -> List[Incident]:
        """
        Analyze trace data and detect potential incidents

        Args:
            trace_spans: List of trace spans to analyze

        Returns:
            List of detected incidents
        """
        incidents = []

        # Group spans by trace
        trace_groups = self._group_spans_by_trace(trace_spans)

        for trace_id, spans in trace_groups.items():
            incident = self._analyze_trace(trace_id, spans)
            if incident:
                incidents.append(incident)

        self.logger.info(f"Detected {len(incidents)} incidents from {len(trace_spans)} trace spans")
        return incidents

    def collect_and_detect(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filter_str: Optional[str] = None,
        max_results: int = 1000
    ) -> CollectorResult:
        """
        Collect traces and detect incidents in one operation

        Returns:
            CollectorResult with collected data and detected incidents
        """
        errors = []
        incidents_detected = 0

        try:
            # Collect traces
            trace_spans = self.collect_traces(start_time, end_time, filter_str, max_results)

            # Detect incidents
            incidents = self.detect_incidents(trace_spans)
            incidents_detected = len(incidents)

            return CollectorResult(
                collector_name="cloud_trace",
                success=True,
                data_count=len(trace_spans),
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
                collector_name="cloud_trace",
                success=False,
                data_count=0,
                incidents_detected=0,
                errors=errors
            )

    def _get_trace_spans(self, trace_id: str) -> List[TraceSpan]:
        """Get all spans for a specific trace"""
        try:
            request = trace_v2.GetTraceRequest(
                name=f"projects/{self.project_id}/traces/{trace_id}"
            )

            trace = self.client.get_trace(request)

            spans = []
            for span in trace.spans:
                trace_span = self._convert_to_trace_span(trace_id, span)
                if trace_span:
                    spans.append(trace_span)

            return spans

        except Exception as e:
            self.logger.warning(f"Error getting spans for trace {trace_id}: {e}")
            return []

    def _convert_to_trace_span(self, trace_id: str, span) -> Optional[TraceSpan]:
        """Convert Cloud Trace span to our TraceSpan model"""
        try:
            # Convert timestamps
            start_time = datetime.fromtimestamp(span.start_time.seconds + span.start_time.nanos / 1e9)
            end_time = datetime.fromtimestamp(span.end_time.seconds + span.end_time.nanos / 1e9)

            # Extract attributes
            attributes = {}
            for attribute in span.attributes.attribute_map:
                value = attribute[1]
                if hasattr(value, 'string_value'):
                    attributes[attribute[0]] = value.string_value.value
                elif hasattr(value, 'int_value'):
                    attributes[attribute[0]] = value.int_value
                elif hasattr(value, 'bool_value'):
                    attributes[attribute[0]] = value.bool_value
                elif hasattr(value, 'double_value'):
                    attributes[attribute[0]] = value.double_value

            return TraceSpan(
                trace_id=trace_id,
                span_id=str(span.span_id),
                name=span.display_name.value,
                start_time=start_time,
                end_time=end_time,
                status=span.status.message if span.status else "OK",
                attributes=attributes
            )

        except Exception as e:
            self.logger.warning(f"Error converting trace span: {e}")
            return None

    def _group_spans_by_trace(self, trace_spans: List[TraceSpan]) -> Dict[str, List[TraceSpan]]:
        """Group trace spans by trace ID"""
        trace_groups = {}

        for span in trace_spans:
            if span.trace_id not in trace_groups:
                trace_groups[span.trace_id] = []
            trace_groups[span.trace_id].append(span)

        return trace_groups

    def _analyze_trace(self, trace_id: str, spans: List[TraceSpan]) -> Optional[Incident]:
        """Analyze a complete trace for incidents"""
        if not spans:
            return None

        # Sort spans by start time
        spans.sort(key=lambda x: x.start_time)

        # Analyze trace for issues
        issues = self._detect_trace_issues(spans)

        if issues:
            # Find the most severe issue
            most_severe = max(issues, key=lambda x: x['severity_score'])

            # Extract resource information from spans
            resource = self._extract_resource_from_spans(spans)

            incident_id = f"trace-{trace_id}-{int(datetime.utcnow().timestamp())}"

            return Incident(
                id=incident_id,
                timestamp=most_severe['timestamp'],
                severity=most_severe['severity'],
                source=IncidentSource.TRACE,
                title=most_severe['title'],
                description=most_severe['description'],
                resource=resource,
                traces=spans,
                detected_by="cloud_trace_collector",
                confidence_score=most_severe['confidence']
            )

        return None

    def _detect_trace_issues(self, spans: List[TraceSpan]) -> List[Dict[str, Any]]:
        """Detect issues in trace data"""
        issues = []

        # Check for long-running operations
        long_running = self._detect_long_running_spans(spans)
        issues.extend(long_running)

        # Check for error spans
        error_spans = self._detect_error_spans(spans)
        issues.extend(error_spans)

        # Check for performance degradation
        performance_issues = self._detect_performance_issues(spans)
        issues.extend(performance_issues)

        return issues

    def _detect_long_running_spans(self, spans: List[TraceSpan]) -> List[Dict[str, Any]]:
        """Detect spans that are running longer than expected"""
        issues = []

        for span in spans:
            duration = (span.end_time - span.start_time).total_seconds()

            # Define thresholds based on span name/type
            threshold = self._get_duration_threshold(span.name)

            if duration > threshold:
                issues.append({
                    'timestamp': span.end_time,
                    'severity': IncidentSeverity.MEDIUM if duration > threshold * 2 else IncidentSeverity.LOW,
                    'title': f"Long-running operation: {span.name}",
                    'description': f"Span '{span.name}' took {duration:.1f}s (threshold: {threshold}s)",
                    'severity_score': 2 if duration > threshold * 2 else 1,
                    'confidence': min(0.8, duration / (threshold * 2))
                })

        return issues

    def _detect_error_spans(self, spans: List[TraceSpan]) -> List[Dict[str, Any]]:
        """Detect spans with error status"""
        issues = []

        for span in spans:
            if span.status and span.status.upper() not in ['OK', 'SUCCESS', '']:
                issues.append({
                    'timestamp': span.end_time,
                    'severity': IncidentSeverity.HIGH,
                    'title': f"Trace span error: {span.name}",
                    'description': f"Span '{span.name}' failed with status: {span.status}",
                    'severity_score': 3,
                    'confidence': 0.9
                })

        return issues

    def _detect_performance_issues(self, spans: List[TraceSpan]) -> List[Dict[str, Any]]:
        """Detect performance degradation patterns"""
        issues = []

        if len(spans) < 2:
            return issues

        # Calculate average span duration
        durations = [(span.end_time - span.start_time).total_seconds() for span in spans]
        avg_duration = sum(durations) / len(durations)

        # Check for spans that are outliers
        for span in spans:
            span_duration = (span.end_time - span.start_time).total_seconds()
            if span_duration > avg_duration * 3:  # 3x average
                issues.append({
                    'timestamp': span.end_time,
                    'severity': IncidentSeverity.MEDIUM,
                    'title': f"Performance outlier: {span.name}",
                    'description': f"Span '{span.name}' took {span_duration:.1f}s (3x avg: {avg_duration:.1f}s)",
                    'severity_score': 2,
                    'confidence': 0.7
                })

        return issues

    def _get_duration_threshold(self, span_name: str) -> float:
        """Get expected duration threshold for different span types"""
        thresholds = {
            'http': 5.0,  # 5 seconds for HTTP requests
            'database': 2.0,  # 2 seconds for DB queries
            'cache': 0.5,  # 0.5 seconds for cache operations
            'external': 10.0,  # 10 seconds for external calls
        }

        for key, threshold in thresholds.items():
            if key.lower() in span_name.lower():
                return threshold

        return 1.0  # Default 1 second

    def _extract_resource_from_spans(self, spans: List[TraceSpan]) -> GCPResource:
        """Extract GCP resource information from trace spans"""
        # Try to extract from span attributes
        for span in spans:
            service_name = span.attributes.get('service.name')
            service_version = span.attributes.get('service.version')
            project_id = span.attributes.get('project_id', self.project_id)
            location = span.attributes.get('location', 'unknown')

            if service_name:
                return GCPResource(
                    project_id=project_id,
                    resource_type='cloud_run_service' if 'run' in service_name.lower() else 'generic_service',
                    resource_name=service_name,
                    location=location,
                    labels={
                        'service_version': service_version or 'unknown',
                        'source': 'trace_analysis'
                    }
                )

        # Fallback
        return GCPResource(
            project_id=self.project_id,
            resource_type='unknown',
            resource_name='unknown',
            location='unknown',
            labels={'source': 'trace_analysis'}
        )
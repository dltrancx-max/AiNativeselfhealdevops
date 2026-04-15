# Cloud Monitoring Collector
# Collects and analyzes Cloud Monitoring metrics for incident detection

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.cloud import monitoring_v3
from google.api_core.exceptions import GoogleAPIError

from ..models import (
    MetricData,
    Incident,
    IncidentSeverity,
    IncidentSource,
    GCPResource,
    CollectorResult
)

logger = logging.getLogger(__name__)


class CloudMonitoringCollector:
    """Collector for Cloud Monitoring metrics data"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = monitoring_v3.MetricServiceClient()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Common GCP metric types to monitor
        self.metric_types = [
            "compute.googleapis.com/instance/cpu/utilization",
            "compute.googleapis.com/instance/disk/write_bytes_count",
            "compute.googleapis.com/instance/network/received_bytes_count",
            "run.googleapis.com/request_count",
            "run.googleapis.com/request_latencies",
            "loadbalancing.googleapis.com/https/request_count",
            "cloudfunctions.googleapis.com/function/execution_count",
            "cloudfunctions.googleapis.com/function/execution_times",
            "bigquery.googleapis.com/query/count",
            "storage.googleapis.com/api/request_count"
        ]

    def collect_metrics(
        self,
        resource_type: Optional[str] = None,
        metric_types: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        alignment_period: int = 300  # 5 minutes
    ) -> List[MetricData]:
        """
        Collect metrics data from Cloud Monitoring

        Args:
            resource_type: Filter by resource type (e.g., "gce_instance")
            metric_types: List of metric types to collect
            start_time: Start time for metric collection
            end_time: End time for metric collection
            alignment_period: Alignment period in seconds

        Returns:
            List of MetricData objects
        """
        try:
            # Set default time range
            if not end_time:
                end_time = datetime.utcnow()
            if not start_time:
                start_time = end_time - timedelta(minutes=10)

            # Use provided metric types or defaults
            metrics_to_collect = metric_types or self.metric_types

            all_metrics = []

            for metric_type in metrics_to_collect:
                try:
                    metrics = self._collect_single_metric_type(
                        metric_type, resource_type, start_time, end_time, alignment_period
                    )
                    all_metrics.extend(metrics)
                except Exception as e:
                    self.logger.warning(f"Error collecting metric {metric_type}: {e}")
                    continue

            self.logger.info(f"Collected {len(all_metrics)} metric data points")
            return all_metrics

        except GoogleAPIError as e:
            self.logger.error(f"Error collecting metrics: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in metric collection: {e}")
            raise

    def detect_incidents(self, metrics: List[MetricData]) -> List[Incident]:
        """
        Analyze metrics and detect potential incidents

        Args:
            metrics: List of metric data to analyze

        Returns:
            List of detected incidents
        """
        incidents = []

        # Group metrics by resource
        resource_metrics = self._group_metrics_by_resource(metrics)

        for resource_key, resource_metric_list in resource_metrics.items():
            incident = self._analyze_resource_metrics(resource_key, resource_metric_list)
            if incident:
                incidents.append(incident)

        self.logger.info(f"Detected {len(incidents)} incidents from {len(metrics)} metric data points")
        return incidents

    def collect_and_detect(
        self,
        resource_type: Optional[str] = None,
        metric_types: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        alignment_period: int = 300
    ) -> CollectorResult:
        """
        Collect metrics and detect incidents in one operation

        Returns:
            CollectorResult with collected data and detected incidents
        """
        errors = []
        incidents_detected = 0

        try:
            # Collect metrics
            metrics = self.collect_metrics(resource_type, metric_types, start_time, end_time, alignment_period)

            # Detect incidents
            incidents = self.detect_incidents(metrics)
            incidents_detected = len(incidents)

            return CollectorResult(
                collector_name="cloud_monitoring",
                success=True,
                data_count=len(metrics),
                incidents_detected=incidents_detected,
                metadata={
                    "resource_type": resource_type,
                    "metric_types": metric_types or self.metric_types,
                    "time_range": {
                        "start": start_time.isoformat() if start_time else None,
                        "end": end_time.isoformat() if end_time else None
                    },
                    "alignment_period": alignment_period,
                    "incidents": [incident.to_dict() for incident in incidents]
                }
            )

        except Exception as e:
            error_msg = f"Error in collect_and_detect: {str(e)}"
            self.logger.error(error_msg)
            errors.append(error_msg)

            return CollectorResult(
                collector_name="cloud_monitoring",
                success=False,
                data_count=0,
                incidents_detected=0,
                errors=errors
            )

    def _collect_single_metric_type(
        self,
        metric_type: str,
        resource_type: Optional[str],
        start_time: datetime,
        end_time: datetime,
        alignment_period: int
    ) -> List[MetricData]:
        """Collect data for a single metric type"""
        # Build filter
        filter_parts = [f'metric.type = "{metric_type}"']

        if resource_type:
            filter_parts.append(f'resource.type = "{resource_type}"')

        filter_str = " AND ".join(filter_parts)

        # Create request
        request = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{self.project_id}",
            filter=filter_str,
            interval=monitoring_v3.TimeInterval(
                start_time=start_time,
                end_time=end_time
            ),
            aggregation=monitoring_v3.Aggregation(
                alignment_period={"seconds": alignment_period},
                per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                cross_series_reducer=monitoring_v3.Aggregation.Reducer.REDUCE_NONE,
                group_by_fields=[]
            )
        )

        # Execute request
        time_series = self.client.list_time_series(request)

        metrics = []
        for series in time_series:
            for point in series.points:
                metric_data = self._convert_to_metric_data(series, point)
                if metric_data:
                    metrics.append(metric_data)

        return metrics

    def _convert_to_metric_data(
        self,
        series: monitoring_v3.TimeSeries,
        point: monitoring_v3.Point
    ) -> Optional[MetricData]:
        """Convert Cloud Monitoring data to our MetricData model"""
        try:
            # Extract resource information
            resource = series.resource
            resource_name = resource.labels.get('instance_name', resource.labels.get('service_name', 'unknown'))

            # Extract metric value
            value = self._extract_metric_value(point.value)

            # Extract labels
            labels = dict(series.metric.labels)
            labels.update(series.resource.labels)

            return MetricData(
                name=series.metric.type,
                value=value,
                unit=getattr(series, 'unit', ''),
                timestamp=point.interval.end_time,
                labels=labels
            )

        except Exception as e:
            self.logger.warning(f"Error converting metric data: {e}")
            return None

    def _extract_metric_value(self, value) -> float:
        """Extract numeric value from different value types"""
        if hasattr(value, 'double_value'):
            return value.double_value
        elif hasattr(value, 'int64_value'):
            return float(value.int64_value)
        elif hasattr(value, 'bool_value'):
            return 1.0 if value.bool_value else 0.0
        else:
            return 0.0

    def _group_metrics_by_resource(self, metrics: List[MetricData]) -> Dict[str, List[MetricData]]:
        """Group metrics by GCP resource"""
        resource_groups = {}

        for metric in metrics:
            # Use resource name from labels or generate key
            resource_name = metric.labels.get('instance_name',
                            metric.labels.get('service_name',
                            metric.labels.get('resource_name', 'unknown')))

            resource_type = metric.labels.get('resource_type', 'unknown')
            resource_key = f"{resource_type}:{resource_name}"

            if resource_key not in resource_groups:
                resource_groups[resource_key] = []
            resource_groups[resource_key].append(metric)

        return resource_groups

    def _analyze_resource_metrics(self, resource_key: str, metrics: List[MetricData]) -> Optional[Incident]:
        """Analyze metrics for a specific resource and detect incidents"""
        if not metrics:
            return None

        # Sort metrics by timestamp
        metrics.sort(key=lambda x: x.timestamp)

        # Analyze different metric types
        anomalies = self._detect_metric_anomalies(metrics)

        if anomalies:
            # Create incident from most severe anomaly
            most_severe = max(anomalies, key=lambda x: x['severity_score'])

            resource_type, resource_name = resource_key.split(':', 1)

            gcp_resource = GCPResource(
                project_id=self.project_id,
                resource_type=resource_type,
                resource_name=resource_name,
                location=metrics[0].labels.get('zone', 'unknown')
            )

            incident_id = f"monitoring-{resource_key.replace(':', '-')}-{int(datetime.utcnow().timestamp())}"

            return Incident(
                id=incident_id,
                timestamp=most_severe['timestamp'],
                severity=most_severe['severity'],
                source=IncidentSource.MONITORING,
                title=most_severe['title'],
                description=most_severe['description'],
                resource=gcp_resource,
                metrics=metrics,
                detected_by="cloud_monitoring_collector",
                confidence_score=most_severe['confidence']
            )

        return None

    def _detect_metric_anomalies(self, metrics: List[MetricData]) -> List[Dict[str, Any]]:
        """Detect anomalies in metric data"""
        anomalies = []

        # Group by metric name
        metric_groups = {}
        for metric in metrics:
            if metric.name not in metric_groups:
                metric_groups[metric.name] = []
            metric_groups[metric.name].append(metric)

        for metric_name, metric_list in metric_groups.items():
            if len(metric_list) < 3:  # Need minimum data points
                continue

            anomaly = self._analyze_single_metric(metric_name, metric_list)
            if anomaly:
                anomalies.append(anomaly)

        return anomalies

    def _analyze_single_metric(self, metric_name: str, metrics: List[MetricData]) -> Optional[Dict[str, Any]]:
        """Analyze a single metric for anomalies"""
        values = [m.value for m in metrics]

        # Simple anomaly detection based on thresholds
        if metric_name.endswith('cpu/utilization'):
            return self._check_cpu_anomaly(metrics, values)
        elif metric_name.endswith('request_latencies'):
            return self._check_latency_anomaly(metrics, values)
        elif metric_name.endswith('error_rate'):
            return self._check_error_rate_anomaly(metrics, values)
        elif 'disk' in metric_name and 'write_bytes_count' in metric_name:
            return self._check_disk_anomaly(metrics, values)

        # Generic threshold check for unknown metrics
        return self._check_generic_anomaly(metrics, values)

    def _check_cpu_anomaly(self, metrics: List[MetricData], values: List[float]) -> Optional[Dict[str, Any]]:
        """Check for CPU utilization anomalies"""
        latest_value = values[-1]
        avg_value = sum(values) / len(values)

        if latest_value > 0.9:  # 90% CPU usage
            return {
                'timestamp': metrics[-1].timestamp,
                'severity': IncidentSeverity.HIGH,
                'title': f"High CPU utilization: {latest_value:.1%}",
                'description': f"CPU usage spiked to {latest_value:.1%} (avg: {avg_value:.1%})",
                'severity_score': 3,
                'confidence': 0.8
            }
        elif latest_value > 0.8:  # 80% CPU usage
            return {
                'timestamp': metrics[-1].timestamp,
                'severity': IncidentSeverity.MEDIUM,
                'title': f"Elevated CPU utilization: {latest_value:.1%}",
                'description': f"CPU usage at {latest_value:.1%} (avg: {avg_value:.1%})",
                'severity_score': 2,
                'confidence': 0.6
            }

        return None

    def _check_latency_anomaly(self, metrics: List[MetricData], values: List[float]) -> Optional[Dict[str, Any]]:
        """Check for latency anomalies"""
        latest_value = values[-1]
        avg_value = sum(values) / len(values)

        if latest_value > avg_value * 2:  # 2x average latency
            return {
                'timestamp': metrics[-1].timestamp,
                'severity': IncidentSeverity.HIGH,
                'title': f"High latency spike: {latest_value:.0f}ms",
                'description': f"Response time spiked to {latest_value:.0f}ms (avg: {avg_value:.0f}ms)",
                'severity_score': 3,
                'confidence': 0.7
            }

        return None

    def _check_error_rate_anomaly(self, metrics: List[MetricData], values: List[float]) -> Optional[Dict[str, Any]]:
        """Check for error rate anomalies"""
        latest_value = values[-1]

        if latest_value > 0.1:  # 10% error rate
            return {
                'timestamp': metrics[-1].timestamp,
                'severity': IncidentSeverity.CRITICAL,
                'title': f"High error rate: {latest_value:.1%}",
                'description': f"Error rate reached {latest_value:.1%}",
                'severity_score': 4,
                'confidence': 0.9
            }
        elif latest_value > 0.05:  # 5% error rate
            return {
                'timestamp': metrics[-1].timestamp,
                'severity': IncidentSeverity.HIGH,
                'title': f"Elevated error rate: {latest_value:.1%}",
                'description': f"Error rate at {latest_value:.1%}",
                'severity_score': 3,
                'confidence': 0.7
            }

        return None

    def _check_disk_anomaly(self, metrics: List[MetricData], values: List[float]) -> Optional[Dict[str, Any]]:
        """Check for disk I/O anomalies"""
        # Simple rate of change analysis
        if len(values) >= 2:
            rate_of_change = values[-1] - values[-2]
            if rate_of_change > 1000000:  # 1MB/s spike
                return {
                    'timestamp': metrics[-1].timestamp,
                    'severity': IncidentSeverity.MEDIUM,
                    'title': f"High disk write activity",
                    'description': f"Disk write rate increased by {rate_of_change/1000000:.1f} MB/s",
                    'severity_score': 2,
                    'confidence': 0.6
                }

        return None

    def _check_generic_anomaly(self, metrics: List[MetricData], values: List[float]) -> Optional[Dict[str, Any]]:
        """Generic anomaly detection for unknown metrics"""
        if len(values) < 3:
            return None

        # Simple statistical anomaly detection
        avg_value = sum(values) / len(values)
        std_dev = (sum((x - avg_value) ** 2 for x in values) / len(values)) ** 0.5

        if std_dev == 0:
            return None

        latest_value = values[-1]
        z_score = abs(latest_value - avg_value) / std_dev

        if z_score > 3:  # 3 standard deviations
            return {
                'timestamp': metrics[-1].timestamp,
                'severity': IncidentSeverity.MEDIUM,
                'title': f"Metric anomaly detected",
                'description': f"Value {latest_value} deviates {z_score:.1f}σ from mean {avg_value:.2f}",
                'severity_score': 2,
                'confidence': min(0.8, z_score / 5)
            }

        return None
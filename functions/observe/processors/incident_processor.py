# Incident Processor
# Processes and correlates incident data from multiple collectors

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict

from ..models import Incident, IncidentSeverity, IncidentSource

logger = logging.getLogger(__name__)


class IncidentProcessor:
    """Processes and correlates incident data"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def correlate_incidents(self, incidents: List[Incident]) -> List[Incident]:
        """
        Correlate related incidents from different sources

        Args:
            incidents: List of incidents to correlate

        Returns:
            List of correlated incidents
        """
        if len(incidents) <= 1:
            return incidents

        self.logger.info(f"Starting correlation of {len(incidents)} incidents")

        # Group incidents by correlation criteria
        correlation_groups = self._group_incidents_for_correlation(incidents)

        correlated_incidents = []
        processed_ids = set()

        for group_key, group_incidents in correlation_groups.items():
            if len(group_incidents) == 1:
                correlated_incidents.append(group_incidents[0])
            else:
                # Merge correlated incidents
                merged_incident = self._merge_incidents(group_incidents)
                correlated_incidents.append(merged_incident)

            # Mark all incidents in group as processed
            for incident in group_incidents:
                processed_ids.add(incident.id)

        # Add any remaining ungrouped incidents
        for incident in incidents:
            if incident.id not in processed_ids:
                correlated_incidents.append(incident)

        self.logger.info(f"Correlation complete. Reduced to {len(correlated_incidents)} incidents")
        return correlated_incidents

    def enrich_incidents(self, incidents: List[Incident]) -> List[Incident]:
        """
        Enrich incidents with additional context and metadata

        Args:
            incidents: List of incidents to enrich

        Returns:
            List of enriched incidents
        """
        enriched = []

        for incident in incidents:
            try:
                enriched_incident = self._enrich_single_incident(incident)
                enriched.append(enriched_incident)
            except Exception as e:
                self.logger.error(f"Error enriching incident {incident.id}: {e}")
                enriched.append(incident)  # Return original if enrichment fails

        return enriched

    def filter_incidents(
        self,
        incidents: List[Incident],
        min_severity: Optional[IncidentSeverity] = None,
        resource_filter: Optional[str] = None,
        time_window: Optional[timedelta] = None
    ) -> List[Incident]:
        """
        Filter incidents based on criteria

        Args:
            incidents: List of incidents to filter
            min_severity: Minimum severity level
            resource_filter: Resource name filter (partial match)
            time_window: Only incidents within this time window from now

        Returns:
            Filtered list of incidents
        """
        filtered = incidents

        # Filter by severity
        if min_severity:
            severity_order = {
                IncidentSeverity.INFO: 0,
                IncidentSeverity.LOW: 1,
                IncidentSeverity.MEDIUM: 2,
                IncidentSeverity.HIGH: 3,
                IncidentSeverity.CRITICAL: 4
            }
            min_order = severity_order.get(min_severity, 0)
            filtered = [
                inc for inc in filtered
                if severity_order.get(inc.severity, 0) >= min_order
            ]

        # Filter by resource
        if resource_filter:
            filtered = [
                inc for inc in filtered
                if resource_filter.lower() in inc.resource.resource_name.lower()
            ]

        # Filter by time window
        if time_window:
            cutoff_time = datetime.utcnow() - time_window
            filtered = [
                inc for inc in filtered
                if inc.timestamp >= cutoff_time
            ]

        self.logger.info(f"Filtered incidents: {len(filtered)} of {len(incidents)} remain")
        return filtered

    def prioritize_incidents(self, incidents: List[Incident]) -> List[Incident]:
        """
        Sort incidents by priority/severity

        Args:
            incidents: List of incidents to prioritize

        Returns:
            Sorted list of incidents (highest priority first)
        """
        severity_weights = {
            IncidentSeverity.CRITICAL: 5,
            IncidentSeverity.HIGH: 4,
            IncidentSeverity.MEDIUM: 3,
            IncidentSeverity.LOW: 2,
            IncidentSeverity.INFO: 1
        }

        def priority_key(incident: Incident) -> tuple:
            severity_weight = severity_weights.get(incident.severity, 0)
            # Secondary sort by timestamp (newer first)
            return (-severity_weight, -incident.timestamp.timestamp())

        return sorted(incidents, key=priority_key)

    def _group_incidents_for_correlation(self, incidents: List[Incident]) -> Dict[str, List[Incident]]:
        """
        Group incidents that should be correlated together

        Correlation criteria:
        1. Same resource (exact match)
        2. Time proximity (within 5 minutes)
        3. Related symptoms (same error patterns)
        """
        groups = defaultdict(list)

        # Sort by timestamp for efficient grouping
        sorted_incidents = sorted(incidents, key=lambda x: x.timestamp)

        for incident in sorted_incidents:
            # Try to find existing group to join
            joined_group = False

            for group_key, group_incidents in groups.items():
                if self._should_correlate_incidents(incident, group_incidents[0]):
                    groups[group_key].append(incident)
                    joined_group = True
                    break

            # Create new group if no match found
            if not joined_group:
                group_key = f"{incident.resource.resource_name}_{incident.timestamp.strftime('%Y%m%d_%H%M%S')}"
                groups[group_key] = [incident]

        return dict(groups)

    def _should_correlate_incidents(self, incident1: Incident, incident2: Incident) -> bool:
        """Determine if two incidents should be correlated"""
        # Same resource
        if incident1.resource.resource_name != incident2.resource.resource_name:
            return False

        # Time proximity (within 5 minutes)
        time_diff = abs((incident1.timestamp - incident2.timestamp).total_seconds())
        if time_diff > 300:  # 5 minutes
            return False

        # Similar severity or escalating pattern
        severity_escalation = (
            incident1.severity == IncidentSeverity.CRITICAL or
            incident2.severity == IncidentSeverity.CRITICAL or
            (incident1.severity == IncidentSeverity.HIGH and incident2.severity in [IncidentSeverity.MEDIUM, IncidentSeverity.HIGH]) or
            (incident2.severity == IncidentSeverity.HIGH and incident1.severity in [IncidentSeverity.MEDIUM, IncidentSeverity.HIGH])
        )

        if not severity_escalation:
            return False

        # Similar error patterns (basic text similarity)
        title_similarity = self._calculate_text_similarity(incident1.title, incident2.title)
        desc_similarity = self._calculate_text_similarity(incident1.description, incident2.description)

        return title_similarity > 0.3 or desc_similarity > 0.3

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity score"""
        if not text1 or not text2:
            return 0.0

        # Simple word overlap similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _merge_incidents(self, incidents: List[Incident]) -> Incident:
        """Merge multiple related incidents into a single correlated incident"""
        if not incidents:
            return None

        # Use the most severe incident as base
        base_incident = max(incidents, key=lambda x: self._get_severity_score(x.severity))

        # Combine all data
        all_logs = []
        all_metrics = []
        all_traces = []
        all_tags = {}

        earliest_time = min(inc.timestamp for inc in incidents)
        latest_time = max(inc.timestamp for inc in incidents)

        for incident in incidents:
            all_logs.extend(incident.logs)
            all_metrics.extend(incident.metrics)
            all_traces.extend(incident.traces)
            all_tags.update(incident.tags)

        # Update base incident
        base_incident.logs = all_logs
        base_incident.metrics = all_metrics
        base_incident.traces = all_traces
        base_incident.tags = all_tags

        # Update metadata
        base_incident.tags["correlated_incidents"] = len(incidents)
        base_incident.tags["correlation_time_range"] = f"{earliest_time.isoformat()} to {latest_time.isoformat()}"
        base_incident.confidence_score = min(1.0, base_incident.confidence_score * 1.2)  # Boost confidence for correlation

        # Update title and description
        base_incident.title = f"[CORRELATED] {base_incident.title}"
        base_incident.description += f" (Correlated from {len(incidents)} related incidents)"

        # Update processing history
        correlation_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": "incident_correlation",
            "correlated_incidents": [inc.id for inc in incidents],
            "correlation_reason": "same_resource_time_proximity"
        }
        base_incident.processing_history.append(correlation_entry)

        return base_incident

    def _enrich_single_incident(self, incident: Incident) -> Incident:
        """Enrich a single incident with additional context"""
        # Add resource type classification
        resource_type = incident.resource.resource_type
        if 'compute' in resource_type:
            incident.tags["resource_category"] = "compute"
        elif 'storage' in resource_type:
            incident.tags["resource_category"] = "storage"
        elif 'database' in resource_type:
            incident.tags["resource_category"] = "database"
        elif 'network' in resource_type:
            incident.tags["resource_category"] = "network"
        else:
            incident.tags["resource_category"] = "other"

        # Add time-based context
        now = datetime.utcnow()
        incident_age = (now - incident.timestamp).total_seconds()

        if incident_age < 300:  # 5 minutes
            incident.tags["urgency"] = "immediate"
        elif incident_age < 1800:  # 30 minutes
            incident.tags["urgency"] = "high"
        elif incident_age < 3600:  # 1 hour
            incident.tags["urgency"] = "medium"
        else:
            incident.tags["urgency"] = "low"

        # Add data source summary
        data_sources = []
        if incident.logs:
            data_sources.append("logs")
        if incident.metrics:
            data_sources.append("metrics")
        if incident.traces:
            data_sources.append("traces")

        incident.tags["data_sources"] = ",".join(data_sources)

        # Calculate data volume
        incident.tags["data_volume"] = len(incident.logs) + len(incident.metrics) + len(incident.traces)

        return incident

    def _get_severity_score(self, severity: IncidentSeverity) -> int:
        """Get numeric score for severity level"""
        scores = {
            IncidentSeverity.INFO: 1,
            IncidentSeverity.LOW: 2,
            IncidentSeverity.MEDIUM: 3,
            IncidentSeverity.HIGH: 4,
            IncidentSeverity.CRITICAL: 5
        }
        return scores.get(severity, 0)
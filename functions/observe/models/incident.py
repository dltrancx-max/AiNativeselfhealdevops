# OBSERVE Pillar - Data Models
# Defines the core data structures for incident detection and telemetry collection

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class IncidentSeverity(Enum):
    """Incident severity levels"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class IncidentStatus(Enum):
    """Incident processing status"""
    NEW = "NEW"
    ANALYZING = "ANALYZING"
    DIAGNOSED = "DIAGNOSED"
    DECIDING = "DECIDING"
    REMEDIATING = "REMEDIATING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"


class IncidentSource(Enum):
    """Source of incident detection"""
    LOGGING = "logging"
    MONITORING = "monitoring"
    TRACE = "trace"
    CUSTOM = "custom"


@dataclass
class GCPResource:
    """GCP resource information"""
    project_id: str
    resource_type: str  # e.g., "gce_instance", "cloud_run_service"
    resource_name: str
    location: str
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricData:
    """Individual metric measurement"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class LogEntry:
    """Cloud Logging entry"""
    timestamp: datetime
    severity: str
    message: str
    resource: GCPResource
    labels: Dict[str, str] = field(default_factory=dict)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None


@dataclass
class TraceSpan:
    """Cloud Trace span data"""
    trace_id: str
    span_id: str
    name: str
    start_time: datetime
    end_time: datetime
    status: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    """Core incident data structure"""
    id: str
    timestamp: datetime
    severity: IncidentSeverity
    source: IncidentSource
    title: str
    description: str
    resource: GCPResource

    # Related data
    metrics: List[MetricData] = field(default_factory=list)
    logs: List[LogEntry] = field(default_factory=list)
    traces: List[TraceSpan] = field(default_factory=list)

    # Classification and metadata
    tags: Dict[str, str] = field(default_factory=dict)
    status: IncidentStatus = IncidentStatus.NEW

    # Processing metadata
    detected_by: str = ""  # Which collector detected this
    confidence_score: float = 0.0  # AI confidence in detection
    processing_history: List[Dict[str, Any]] = field(default_factory=list)

    # Resolution data
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "source": self.source.value,
            "title": self.title,
            "description": self.description,
            "resource": {
                "project_id": self.resource.project_id,
                "resource_type": self.resource.resource_type,
                "resource_name": self.resource.resource_name,
                "location": self.resource.location,
                "labels": self.resource.labels
            },
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "unit": m.unit,
                    "timestamp": m.timestamp.isoformat(),
                    "labels": m.labels
                } for m in self.metrics
            ],
            "logs": [
                {
                    "timestamp": l.timestamp.isoformat(),
                    "severity": l.severity,
                    "message": l.message,
                    "resource": {
                        "project_id": l.resource.project_id,
                        "resource_type": l.resource.resource_type,
                        "resource_name": l.resource.resource_name,
                        "location": l.resource.location,
                        "labels": l.resource.labels
                    },
                    "labels": l.labels,
                    "trace_id": l.trace_id,
                    "span_id": l.span_id
                } for l in self.logs
            ],
            "traces": [
                {
                    "trace_id": t.trace_id,
                    "span_id": t.span_id,
                    "name": t.name,
                    "start_time": t.start_time.isoformat(),
                    "end_time": t.end_time.isoformat(),
                    "status": t.status,
                    "attributes": t.attributes
                } for t in self.traces
            ],
            "tags": self.tags,
            "status": self.status.value,
            "detected_by": self.detected_by,
            "confidence_score": self.confidence_score,
            "processing_history": self.processing_history,
            "root_cause": self.root_cause,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Incident':
        """Create Incident from dictionary"""
        resource_data = data["resource"]
        resource = GCPResource(
            project_id=resource_data["project_id"],
            resource_type=resource_data["resource_type"],
            resource_name=resource_data["resource_name"],
            location=resource_data["location"],
            labels=resource_data.get("labels", {})
        )

        metrics = [
            MetricData(
                name=m["name"],
                value=m["value"],
                unit=m["unit"],
                timestamp=datetime.fromisoformat(m["timestamp"]),
                labels=m.get("labels", {})
            ) for m in data.get("metrics", [])
        ]

        logs = []
        for l in data.get("logs", []):
            log_resource_data = l["resource"]
            log_resource = GCPResource(
                project_id=log_resource_data["project_id"],
                resource_type=log_resource_data["resource_type"],
                resource_name=log_resource_data["resource_name"],
                location=log_resource_data["location"],
                labels=log_resource_data.get("labels", {})
            )
            logs.append(LogEntry(
                timestamp=datetime.fromisoformat(l["timestamp"]),
                severity=l["severity"],
                message=l["message"],
                resource=log_resource,
                labels=l.get("labels", {}),
                trace_id=l.get("trace_id"),
                span_id=l.get("span_id")
            ))

        traces = [
            TraceSpan(
                trace_id=t["trace_id"],
                span_id=t["span_id"],
                name=t["name"],
                start_time=datetime.fromisoformat(t["start_time"]),
                end_time=datetime.fromisoformat(t["end_time"]),
                status=t["status"],
                attributes=t.get("attributes", {})
            ) for t in data.get("traces", [])
        ]

        resolved_at = datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None

        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            severity=IncidentSeverity(data["severity"]),
            source=IncidentSource(data["source"]),
            title=data["title"],
            description=data["description"],
            resource=resource,
            metrics=metrics,
            logs=logs,
            traces=traces,
            tags=data.get("tags", {}),
            status=IncidentStatus(data["status"]),
            detected_by=data.get("detected_by", ""),
            confidence_score=data.get("confidence_score", 0.0),
            processing_history=data.get("processing_history", []),
            root_cause=data.get("root_cause"),
            resolution=data.get("resolution"),
            resolved_at=resolved_at,
            resolved_by=data.get("resolved_by")
        )


@dataclass
class TelemetryData:
    """Unified telemetry data structure"""
    timestamp: datetime
    source: str  # "logging", "monitoring", "trace"
    resource_type: str
    resource_name: str
    project_id: str
    location: str

    # Data payload
    data_type: str  # "metric", "log", "trace"
    payload: Dict[str, Any]

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "project_id": self.project_id,
            "location": self.location,
            "data_type": self.data_type,
            "payload": self.payload,
            "labels": self.labels,
            "metadata": self.metadata
        }


@dataclass
class CollectorResult:
    """Result from a data collector"""
    collector_name: str
    success: bool
    data_count: int
    incidents_detected: int
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    collected_at: datetime = field(default_factory=datetime.utcnow)
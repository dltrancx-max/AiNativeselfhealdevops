# BigQuery Client
# Handles storage of incident data in BigQuery for analysis and reporting

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

from ..models import Incident

logger = logging.getLogger(__name__)


class BigQueryClient:
    """Client for storing and retrieving incident data in BigQuery"""

    def __init__(self, project_id: str, dataset_id: str, table_id: str):
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.client = bigquery.Client(project=project_id)
        self.table_ref = f"{project_id}.{dataset_id}.{table_id}"

        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def ensure_table_exists(self) -> bool:
        """
        Ensure the incidents table exists with correct schema

        Returns:
            True if table exists or was created successfully
        """
        try:
            # Check if dataset exists
            dataset_ref = bigquery.DatasetReference(self.project_id, self.dataset_id)
            try:
                self.client.get_dataset(dataset_ref)
                self.logger.info(f"Dataset {self.dataset_id} exists")
            except Exception:
                # Create dataset
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = "US"  # Default location
                self.client.create_dataset(dataset)
                self.logger.info(f"Created dataset {self.dataset_id}")

            # Check if table exists
            table_ref = bigquery.TableReference.from_string(self.table_ref)
            try:
                self.client.get_table(table_ref)
                self.logger.info(f"Table {self.table_id} exists")
                return True
            except Exception:
                # Create table with schema
                return self._create_incidents_table()

        except GoogleAPIError as e:
            self.logger.error(f"Error ensuring table exists: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return False

    def _create_incidents_table(self) -> bool:
        """Create the incidents table with proper schema"""
        try:
            schema = self._get_incidents_schema()

            table_ref = bigquery.TableReference.from_string(self.table_ref)
            table = bigquery.Table(table_ref, schema=schema)

            # Set table properties
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp"
            )

            # Create table
            self.client.create_table(table)
            self.logger.info(f"Created incidents table: {self.table_id}")

            return True

        except GoogleAPIError as e:
            self.logger.error(f"Error creating table: {e}")
            return False

    def _get_incidents_schema(self) -> List[bigquery.SchemaField]:
        """Get the BigQuery schema for incidents table"""
        return [
            # Basic incident information
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("severity", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("title", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("description", "STRING", mode="NULLABLE"),

            # Resource information
            bigquery.SchemaField("resource_project_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("resource_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("resource_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("resource_location", "STRING", mode="REQUIRED"),

            # Processing metadata
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("detected_by", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("confidence_score", "FLOAT", mode="NULLABLE"),

            # Resolution data
            bigquery.SchemaField("root_cause", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("resolution", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("resolved_at", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("resolved_by", "STRING", mode="NULLABLE"),

            # Data counts (for quick analysis)
            bigquery.SchemaField("logs_count", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("metrics_count", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("traces_count", "INTEGER", mode="NULLABLE"),

            # JSON fields for complex data
            bigquery.SchemaField("tags", "JSON", mode="NULLABLE"),
            bigquery.SchemaField("resource_labels", "JSON", mode="NULLABLE"),
            bigquery.SchemaField("processing_history", "JSON", mode="NULLABLE"),

            # Raw data (stored as JSON strings for detailed analysis)
            bigquery.SchemaField("logs_data", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("metrics_data", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("traces_data", "STRING", mode="NULLABLE"),

            # Metadata
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED")
        ]

    def store_incident(self, incident: Incident) -> bool:
        """
        Store a single incident in BigQuery

        Args:
            incident: Incident object to store

        Returns:
            True if stored successfully
        """
        try:
            # Ensure table exists
            if not self.ensure_table_exists():
                return False

            # Convert incident to BigQuery row
            row = self._incident_to_bigquery_row(incident)

            # Insert row
            errors = self.client.insert_rows_json(self.table_ref, [row])

            if errors:
                self.logger.error(f"Errors inserting incident {incident.id}: {errors}")
                return False

            self.logger.info(f"Successfully stored incident {incident.id}")
            return True

        except GoogleAPIError as e:
            self.logger.error(f"BigQuery API error storing incident {incident.id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error storing incident {incident.id}: {e}")
            return False

    def store_incidents_batch(self, incidents: List[Incident]) -> Dict[str, Any]:
        """
        Store multiple incidents in a batch operation

        Args:
            incidents: List of incidents to store

        Returns:
            Dictionary with success/failure counts
        """
        if not incidents:
            return {"success": 0, "failed": 0, "total": 0}

        try:
            # Ensure table exists
            if not self.ensure_table_exists():
                return {"success": 0, "failed": len(incidents), "total": len(incidents)}

            # Convert incidents to rows
            rows = [self._incident_to_bigquery_row(incident) for incident in incidents]

            # Batch insert
            errors = self.client.insert_rows_json(self.table_ref, rows)

            success_count = len(incidents) - len(errors) if errors else len(incidents)
            failed_count = len(errors) if errors else 0

            if errors:
                self.logger.warning(f"Batch insert had {len(errors)} errors")

            self.logger.info(f"Batch stored {success_count}/{len(incidents)} incidents")
            return {
                "success": success_count,
                "failed": failed_count,
                "total": len(incidents)
            }

        except Exception as e:
            self.logger.error(f"Error in batch store: {e}")
            return {
                "success": 0,
                "failed": len(incidents),
                "total": len(incidents)
            }

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """
        Retrieve a specific incident by ID

        Args:
            incident_id: ID of the incident to retrieve

        Returns:
            Incident object if found, None otherwise
        """
        try:
            query = f"""
            SELECT * FROM `{self.table_ref}`
            WHERE id = @incident_id
            LIMIT 1
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("incident_id", "STRING", incident_id)
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()

            for row in results:
                return self._bigquery_row_to_incident(row)

            return None

        except Exception as e:
            self.logger.error(f"Error retrieving incident {incident_id}: {e}")
            return None

    def get_incidents_by_resource(
        self,
        resource_name: str,
        limit: int = 100,
        start_time: Optional[datetime] = None
    ) -> List[Incident]:
        """
        Get incidents for a specific resource

        Args:
            resource_name: Name of the resource
            limit: Maximum number of incidents to return
            start_time: Only incidents after this time

        Returns:
            List of incidents for the resource
        """
        try:
            query = f"""
            SELECT * FROM `{self.table_ref}`
            WHERE resource_name = @resource_name
            {{time_filter}}
            ORDER BY timestamp DESC
            LIMIT @limit
            """

            params = [
                bigquery.ScalarQueryParameter("resource_name", "STRING", resource_name),
                bigquery.ScalarQueryParameter("limit", "INT64", limit)
            ]

            if start_time:
                query = query.replace("{time_filter}", "AND timestamp >= @start_time")
                params.append(bigquery.ScalarQueryParameter("start_time", "TIMESTAMP", start_time))
            else:
                query = query.replace("{time_filter}", "")

            job_config = bigquery.QueryJobConfig(query_parameters=params)
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()

            incidents = []
            for row in results:
                incident = self._bigquery_row_to_incident(row)
                if incident:
                    incidents.append(incident)

            return incidents

        except Exception as e:
            self.logger.error(f"Error getting incidents for resource {resource_name}: {e}")
            return []

    def _incident_to_bigquery_row(self, incident: Incident) -> Dict[str, Any]:
        """Convert Incident object to BigQuery row format"""
        import json

        return {
            "id": incident.id,
            "timestamp": incident.timestamp.isoformat(),
            "severity": incident.severity.value,
            "source": incident.source.value,
            "title": incident.title,
            "description": incident.description,
            "resource_project_id": incident.resource.project_id,
            "resource_type": incident.resource.resource_type,
            "resource_name": incident.resource.resource_name,
            "resource_location": incident.resource.location,
            "status": incident.status.value,
            "detected_by": incident.detected_by,
            "confidence_score": incident.confidence_score,
            "root_cause": incident.root_cause,
            "resolution": incident.resolution,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "resolved_by": incident.resolved_by,
            "logs_count": len(incident.logs),
            "metrics_count": len(incident.metrics),
            "traces_count": len(incident.traces),
            "tags": json.dumps(incident.tags) if incident.tags else None,
            "resource_labels": json.dumps(incident.resource.labels) if incident.resource.labels else None,
            "processing_history": json.dumps(incident.processing_history) if incident.processing_history else None,
            "logs_data": json.dumps([log.__dict__ for log in incident.logs]) if incident.logs else None,
            "metrics_data": json.dumps([metric.__dict__ for metric in incident.metrics]) if incident.metrics else None,
            "traces_data": json.dumps([trace.__dict__ for trace in incident.traces]) if incident.traces else None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

    def _bigquery_row_to_incident(self, row) -> Optional[Incident]:
        """Convert BigQuery row to Incident object"""
        try:
            import json
            from ..models import GCPResource

            # Reconstruct resource
            resource = GCPResource(
                project_id=row.resource_project_id,
                resource_type=row.resource_type,
                resource_name=row.resource_name,
                location=row.resource_location,
                labels=json.loads(row.resource_labels) if row.resource_labels else {}
            )

            # Parse JSON fields
            tags = json.loads(row.tags) if row.tags else {}
            processing_history = json.loads(row.processing_history) if row.processing_history else []

            # Create incident
            incident = Incident(
                id=row.id,
                timestamp=datetime.fromisoformat(row.timestamp),
                severity=getattr(Incident, row.severity.upper()),
                source=getattr(Incident, row.source.upper()),
                title=row.title,
                description=row.description,
                resource=resource,
                tags=tags,
                status=getattr(Incident, row.status.upper()),
                detected_by=row.detected_by,
                confidence_score=row.confidence_score,
                processing_history=processing_history,
                root_cause=row.root_cause,
                resolution=row.resolution,
                resolved_at=datetime.fromisoformat(row.resolved_at) if row.resolved_at else None,
                resolved_by=row.resolved_by
            )

            return incident

        except Exception as e:
            self.logger.error(f"Error converting BigQuery row to incident: {e}")
            return None
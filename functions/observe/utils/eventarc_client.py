# Eventarc Client
# Handles publishing events to trigger the next pillar in the OODA loop

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from google.cloud import pubsub_v1
from google.api_core.exceptions import GoogleAPIError

from ..models import Incident

logger = logging.getLogger(__name__)


class EventarcClient:
    """Client for publishing events via Eventarc to trigger next pillar"""

    def __init__(self, project_id: str, topic_prefix: str = "devops-ooda"):
        self.project_id = project_id
        self.topic_prefix = topic_prefix
        self.publisher = pubsub_v1.PublisherClient()

        # Define topic names for each pillar
        self.topics = {
            "observe": f"projects/{project_id}/topics/{topic_prefix}-observe",
            "analyze": f"projects/{project_id}/topics/{topic_prefix}-analyze",
            "decide": f"projects/{project_id}/topics/{topic_prefix}-decide",
            "act": f"projects/{project_id}/topics/{topic_prefix}-act",
            "communicate": f"projects/{project_id}/topics/{topic_prefix}-communicate"
        }

        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def publish_incident_event(self, incident: Incident, target_pillar: str) -> bool:
        """
        Publish an incident event to trigger the next pillar

        Args:
            incident: Incident to publish
            target_pillar: Target pillar ("analyze", "decide", "act", "communicate")

        Returns:
            True if published successfully
        """
        try:
            if target_pillar not in self.topics:
                self.logger.error(f"Unknown target pillar: {target_pillar}")
                return False

            topic_path = self.topics[target_pillar]

            # Create event data
            event_data = self._create_incident_event_data(incident, target_pillar)

            # Publish message
            future = self.publisher.publish(
                topic_path,
                data=event_data["data"],
                **event_data["attributes"]
            )

            # Wait for publish to complete
            message_id = future.result()
            self.logger.info(f"Published incident {incident.id} to {target_pillar} pillar (message: {message_id})")

            return True

        except GoogleAPIError as e:
            self.logger.error(f"PubSub API error publishing to {target_pillar}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error publishing to {target_pillar}: {e}")
            return False

    def publish_batch_incidents(self, incidents: List[Incident], target_pillar: str) -> Dict[str, Any]:
        """
        Publish multiple incidents in batch

        Args:
            incidents: List of incidents to publish
            target_pillar: Target pillar

        Returns:
            Dictionary with success/failure counts
        """
        if not incidents:
            return {"success": 0, "failed": 0, "total": 0}

        success_count = 0
        failed_count = 0

        for incident in incidents:
            if self.publish_incident_event(incident, target_pillar):
                success_count += 1
            else:
                failed_count += 1

        self.logger.info(f"Batch published {success_count}/{len(incidents)} incidents to {target_pillar}")
        return {
            "success": success_count,
            "failed": failed_count,
            "total": len(incidents)
        }

    def publish_pillar_status_event(
        self,
        pillar_name: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish a pillar status event for monitoring

        Args:
            pillar_name: Name of the pillar
            status: Status message
            metadata: Additional metadata

        Returns:
            True if published successfully
        """
        try:
            topic_path = self.topics.get("observe", self.topics["observe"])  # Default to observe topic

            event_data = {
                "event_type": "pillar_status",
                "pillar": pillar_name,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }

            import json
            data = json.dumps(event_data).encode("utf-8")

            attributes = {
                "event_type": "pillar_status",
                "pillar": pillar_name,
                "status": status
            }

            future = self.publisher.publish(topic_path, data, **attributes)
            message_id = future.result()

            self.logger.info(f"Published pillar status for {pillar_name}: {status} (message: {message_id})")
            return True

        except Exception as e:
            self.logger.error(f"Error publishing pillar status: {e}")
            return False

    def _create_incident_event_data(self, incident: Incident, target_pillar: str) -> Dict[str, Any]:
        """Create event data for incident publishing"""
        import json

        # Convert incident to JSON
        incident_data = incident.to_dict()

        # Create CloudEvent data
        event_data = {
            "specversion": "1.0",
            "type": f"com.devops.ooda.incident.{target_pillar}",
            "source": f"//devops/ooda/observe/{incident.id}",
            "id": f"incident-{incident.id}-{int(datetime.utcnow().timestamp())}",
            "time": datetime.utcnow().isoformat(),
            "data": json.dumps(incident_data)
        }

        # PubSub message data
        data = json.dumps(event_data).encode("utf-8")

        # Message attributes
        attributes = {
            "event_type": "incident_detected",
            "incident_id": incident.id,
            "severity": incident.severity.value,
            "source": incident.source.value,
            "resource_name": incident.resource.resource_name,
            "resource_type": incident.resource.resource_type,
            "target_pillar": target_pillar,
            "confidence_score": str(incident.confidence_score),
            "timestamp": incident.timestamp.isoformat()
        }

        return {
            "data": data,
            "attributes": attributes
        }

    def ensure_topics_exist(self) -> Dict[str, bool]:
        """
        Ensure all required PubSub topics exist

        Returns:
            Dictionary mapping topic names to existence status
        """
        results = {}

        for pillar, topic_path in self.topics.items():
            try:
                # Extract topic name from path
                topic_name = topic_path.split("/")[-1]

                # Check if topic exists
                topic = self.publisher.topic_path(self.project_id, topic_name)

                # Try to get topic (this will raise exception if it doesn't exist)
                self.publisher.get_topic(topic)

                results[pillar] = True
                self.logger.info(f"Topic {topic_name} exists")

            except Exception as e:
                # Topic doesn't exist, try to create it
                try:
                    topic = self.publisher.topic_path(self.project_id, topic_name)
                    self.publisher.create_topic(topic)
                    results[pillar] = True
                    self.logger.info(f"Created topic {topic_name}")
                except Exception as create_error:
                    results[pillar] = False
                    self.logger.error(f"Failed to create topic {topic_name}: {create_error}")

        return results

    def get_topic_info(self) -> Dict[str, Any]:
        """
        Get information about all topics

        Returns:
            Dictionary with topic information
        """
        info = {}

        for pillar, topic_path in self.topics.items():
            try:
                topic_name = topic_path.split("/")[-1]
                topic = self.publisher.topic_path(self.project_id, topic_name)

                # This will raise an exception if topic doesn't exist
                self.publisher.get_topic(topic)

                info[pillar] = {
                    "exists": True,
                    "topic_path": topic_path,
                    "topic_name": topic_name
                }

            except Exception:
                info[pillar] = {
                    "exists": False,
                    "topic_path": topic_path,
                    "topic_name": topic_name
                }

        return info
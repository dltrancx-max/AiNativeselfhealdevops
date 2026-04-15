# GCP AI-Native Self-Healing DevOps Platform

> An autonomous DevOps ecosystem built on Google Cloud Platform that implements the **OODA Loop** (Observe, Orient, Decide, Act) to detect, diagnose, and remediate infrastructure and application failures **without human intervention**.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Frontend Tech Stack](#frontend-tech-stack)
- [Implementation Roadmap](#implementation-roadmap)
- [OODA as the Base Framework](#ooda-as-the-base-framework)
- [OODA Loop Flow](#ooda-loop-flow)
- [Landing Page Content](#landing-page-content)
- [Prerequisites](#prerequisites)
- [Setup & Deployment](#setup--deployment)
- [Component Overview](#component-overview)
- [Usage](#usage)
- [Monitoring & Observability](#monitoring--observability)
- [Contributing](#contributing)

---

## Overview

This platform implements a fully autonomous self-healing DevOps system on GCP that:

- **OBSERVE**: Captures telemetry from Cloud Logging, Monitoring, Trace, and Eventarc
- **ANALYZE**: Uses Vertex AI (Gemini 1.5 Flash) for root cause analysis
- **DECIDE**: Employs multi-agent orchestration for safe remediation decisions
- **ACT**: Executes fixes via Cloud Build, Terraform, and GKE automation
- **COMMUNICATE**: Reports to Slack, Jira, and Opsgenie for human oversight

---

## Architecture

### The OODA Loop

```
┌─────────────────────────────────────────────────────────────────────┐
│                    GCP Self-Healing DevOps Flow                      │
└─────────────────────────────────────────────────────────────────────┘

TRIGGER ──→ OBSERVE ──→ ANALYZE ──→ DECIDE ──→ ACT ──→ FEEDBACK
   ↓           ↓           ↓           ↓         ↓         ↓
   │           │           │           │         │         │
   └───────────┼───────────┼───────────┼─────────┼─────────┘
               └───────────┼───────────┼─────────┼───────────
                           └───────────┼─────────┼───────────
                                       └─────────┼───────────
                                                 └───────────
---

## Frontend Tech Stack

> **Mobile-First, Microfrontend Architecture** with **Tailwind CSS** for responsive, scalable DevOps dashboards.

### 🎯 **Key Features**
- ✅ **Mobile-Compatible**: Progressive Web App (PWA) with touch-optimized interfaces
- ✅ **Microfrontend Architecture**: Independent module development and deployment
- ✅ **Real-time Dashboards**: Live incident monitoring and AI insights
- ✅ **Responsive Design**: Works seamlessly across all devices

### 🏗️ **Technology Stack**
```
Frontend Architecture:
├── 🏠 Container App (React + Module Federation)
├── 📊 Monitoring Module (Real-time dashboards)
├── 🤖 AI Analytics Module (RCA visualizations)
├── ⚙️ Configuration Module (Safety rules & settings)
└── 📱 Mobile PWA Shell (Offline capabilities)
```

### 📚 **Detailed Documentation**
For comprehensive frontend implementation details, see **[FRONTEND_STACK.md](FRONTEND_STACK.md)** which covers:
- Complete tech stack with code examples
- Microfrontend module architecture
- Mobile-first responsive design patterns
- PWA implementation strategies
- Real-time WebSocket integration
- Performance optimization techniques

---

## Implementation Roadmap

> **Strategic development plan** for building the AI-Native Self-Healing DevOps platform.

### 🎯 **Current Status: Step 1 - OBSERVE Pillar**
```
� COMPLETED: OBSERVE Pillar Implementation Ready for Deployment
├── Phase 1: Core Infrastructure Setup ✅
├── Phase 2: Data Collectors (Cloud Logging, Monitoring, Trace) ✅
├── Phase 3: Data Processing & Incident Detection ✅
├── Phase 4: Eventarc Integration & BigQuery Storage ✅
└── Phase 5: API Endpoints & Testing ✅
```

### 📚 **Detailed Implementation**
For comprehensive Step 1 implementation details, see **[STEP1_OBSERVE_IMPLEMENTATION.md](STEP1_OBSERVE_IMPLEMENTATION.md)** which covers:
- Complete OBSERVE pillar architecture and data flow
- Implementation phases and timeline
- Data models and API specifications
- Testing strategy and success metrics

**Next Steps**: Deploy OBSERVE pillar → ANALYZE pillar → DECIDE pillar → ACT pillar

---

## OODA as the Base Framework

**OODA Loop** = **Operational Foundation**
- Provides the **decision-making cycle**
- Ensures **rapid iteration** (Observe → Orient → Decide → Act)
- Maintains **human-understandable workflow**
- Enables **predictable system behavior**

**AI Techniques** = **Intelligence Enhancements**
- Make each pillar **smarter and more accurate**
- Add **predictive capabilities**
- Enable **autonomous learning**
- Provide **explainable decisions**

### Enhanced OODA Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Enhanced OODA Loop                               │
└─────────────────────────────────────────────────────────────────────┘

TRIGGER ──→ OBSERVE ──→ ANALYZE ──→ DECIDE ──→ ACT ──→ FEEDBACK
   ↓           ↓           ↓           ↓         ↓         ↓
   │           │           │           │         │         │
   └───────────┼───────────┼───────────┼─────────┼─────────┘
               │           │           │         │
            Predictive   Causal     RL Agents Digital
            Analytics   Inference   Learning   Twins
               ↓           ↓           ↓         ↓
            Prevent      True RCA   Optimal    Safe Test
            Incidents    Analysis   Decisions  Remediations
```

### Pillar-Specific AI Enhancements

#### OBSERVE Pillar Enhancements
- **Predictive Analytics**: Anomaly detection, time series forecasting
- **Digital Twins**: Real-time infrastructure simulation
- **Graph Neural Networks**: Dependency relationship mapping

#### ANALYZE Pillar Enhancements
- **Causal Inference**: True root cause vs correlation analysis
- **Large Language Models**: Natural language incident understanding
- **Neuro-Symbolic AI**: Explainable pattern recognition

#### DECIDE Pillar Enhancements
- **Reinforcement Learning**: Learn optimal remediation strategies
- **Multi-Agent Consensus**: Swarm intelligence decision making
- **Self-Adaptive Systems**: Dynamic threshold adjustment

#### ACT Pillar Enhancements
- **Digital Twins**: Pre-deployment remediation testing
- **Federated Learning**: Cross-environment knowledge sharing
- **Autonomous Optimization**: Self-tuning remediation parameters

### Implementation Strategy

**Phase 1: OODA Foundation** (Current Focus)
- Basic OODA loop implementation
- Rule-based decision making
- Manual remediation validation

**Phase 2: AI Enhancement** (Next Steps)
- Add predictive analytics to OBSERVE
- Implement causal inference in ANALYZE
- Add reinforcement learning to DECIDE

**Phase 3: Full AI-Native** (Future)
- Digital twins for safe testing
- Self-adaptive thresholds
- Autonomous optimization

---

## OODA Loop Flow

## OODA Loop Flow

### Step 1: TRIGGER - Incident Detection

**What happens:**
1. **Eventarc** captures infrastructure events (pod crashes, deployment failures)
2. **Cloud Logging Sink** filters `ERROR`/`CRITICAL` logs
3. **Cloud Monitoring** alerts on metric thresholds
4. **Pub/Sub** receives the event and triggers the workflow

**Data Flow:**
```
Infrastructure Event → Pub/Sub Topic → Cloud Workflows → incident_detector()
```

**Example Event:**
```json
{
  "event_type": "container_crashed",
  "resource_id": "payment-service-pod-xyz",
  "severity": "CRITICAL",
  "message": "Container killed due to out of memory",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Step 2: OBSERVE - Data Collection

**What happens:**
1. **CloudLoggingCollector** queries recent error logs
2. **CloudMonitoringCollector** fetches CPU/memory metrics
3. **CloudTraceCollector** analyzes distributed traces
4. **PubSubEventListener** aggregates all signals

**Data Collection:**
```python
# Collect telemetry
error_logs = observer["logging"].filter_critical_logs()
metrics = observer["monitoring"].get_pod_cpu_usage()
traces = observer["tracing"].get_traces()

# Publish for analysis
observer["events"].publish_observation(EventData(...))
```

### Step 3: ANALYZE - AI-Powered Root Cause Analysis

**What happens:**
1. **VertexAIReasoningEngine** receives telemetry data
2. **Gemini 1.5 Flash** analyzes patterns and context
3. **KnowledgeBase** searches for similar past incidents
4. **RCAResult** provides structured analysis

**AI Analysis Process:**
```python
# Build context for Gemini
context = RCAContext(
    error_logs=error_logs,
    metrics=metrics,
    recent_deployments=deployments,
    git_commits=commits
)

# Call Vertex AI
rca_result = analyzer["reasoning_engine"].analyze_incident(context)

# Store in knowledge base
analyzer["knowledge_base"].store_incident(rca_result)
```

**Gemini Prompt Example:**
```
You are an expert DevOps incident response AI. Analyze this incident:

ERROR LOGS:
- [CRITICAL] payment-service: OutOfMemoryError: Java heap space
- [ERROR] payment-service: Connection timeout to database

METRICS:
- Memory utilization: 95.2%
- CPU utilization: 85.1%

RECENT DEPLOYMENTS:
- payment-service v2.1.0 deployed 2 hours ago

Provide JSON with probable_causes, confidence_score, affected_components, impact_severity, suggested_actions.
```

### Step 4: DECIDE - Multi-Agent Orchestration

**What happens:**
1. **DiagnoserAgent** validates RCA against knowledge base
2. **ValidatorAgent** checks safety constraints
3. **RemediatorAgent** generates specific remediation plan
4. **DecisionOrchestrator** makes final decision

**Agent Flow:**
```python
# Initialize orchestrator
orchestrator = DecisionOrchestrator(analyzer["knowledge_base"])

# Execute decision workflow
context = {"rca_result": rca_result}
decision = orchestrator.orchestrate(context)
```

**Safety Checks:**
- Is it peak hours? (9-5 business hours)
- Is it a critical service?
- Does it require approval?
- Are there concurrent remediations?

### Step 5: ACT - Remediation Execution

**What happens:**
1. **RemediationExecutor** routes to appropriate handler
2. **CloudBuildRemediator** or **TerraformRemediator** executes
3. **RollbackManager** monitors and prepares rollback
4. **FeedbackLoop** verifies the fix

**Execution Flow:**
```python
# Route based on remediation type
if decision.remediation_path == "terraform":
    result = executor.terraform.scale_gke_cluster(
        cluster_name="production",
        node_pool="default",
        desired_nodes=5
    )
elif decision.remediation_path == "cloud_build":
    result = executor.cloud_build.trigger_rollback(
        service_name="payment-service",
        target_version="v2.0.0"
    )
```

**Remediation Types:**
- **Resource Scaling**: Terraform → GKE cluster scaling
- **Service Restart**: Kubernetes API → Pod restart
- **Rollback**: Cloud Build → Previous deployment
- **Firewall Update**: Terraform → VPC firewall rules
- **Database Recovery**: Cloud SQL → Connection pool reset

### Step 6: COMMUNICATE - Human Oversight

**Parallel Process Throughout:**
1. **SlackReporter** sends real-time updates
2. **JiraReporter** creates incident tickets
3. **OpsgenieReporter** sends alerts

### Step 7: FEEDBACK LOOP - Verification

**What happens:**
1. **Re-observe** after 30 seconds
2. **Verify fix** by checking metrics/logs
3. **Auto-rollback** if fix failed
4. **Update knowledge base** with results

---

## Landing Page Content

For a professional, responsive landing page for your AI-Native Self-Healing DevOps platform, see [`LANDING_PAGE.md`](LANDING_PAGE.md) which contains:

### **Hero Section**
- Compelling headline and value proposition
- Clear call-to-action buttons
- Professional messaging

### **Interactive OODA Visualization**
- Visual representation of the OODA loop
- Step-by-step process explanation
- AI enhancement overlays

### **Feature Highlights**
- Autonomous incident response
- AI-powered intelligence
- Enterprise-grade reliability
- Multi-channel communication

### **Technical Architecture**
- System component diagrams
- Technology stack overview
- Integration points

### **Business Value**
- ROI metrics and benefits
- Success stories and use cases
- Performance improvements

### **Getting Started**
- Quick start guide
- Prerequisites checklist
- Deployment instructions

The landing page content is designed to be:
- **Progressive**: Loads fast with critical content first
- **Responsive**: Works perfectly on desktop, tablet, and mobile
- **Conversion-focused**: Clear CTAs and value propositions
- **Technical**: Appeals to both business and technical audiences

---

## Prerequisites

### GCP Setup
- GCP Project with billing enabled
- Service account with appropriate permissions
- gcloud CLI configured

### Local Development
- Python 3.11+
- Terraform 1.0+
- Docker (for testing)
- Virtual environment (`venv` or `conda`)

### External Services
- Slack workspace with bot token
- Jira instance with API access
- Opsgenie account with API key

---

## Setup & Deployment

### 1. Clone and Initialize
```bash
git clone https://github.com/dltrancx-max/AiNativeselfhealdevops.git
cd AiNativeselfhealdevops

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your GCP project ID and API keys
nano .env
```

### 3. Deploy Infrastructure
```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var-file=terraform.tfvars

# Apply configuration
terraform apply -var-file=terraform.tfvars
```

### 4. Deploy Cloud Functions
```bash
# Package function code
cd ../../
zip -r functions.zip functions/ agents/ remediation/ requirements.txt

# Upload to Cloud Storage
gsutil cp functions.zip gs://YOUR_PROJECT-functions-source/

# Terraform will deploy functions automatically
```

### 5. Verify Deployment
```bash
# Check Cloud Functions
gcloud functions list --region=us-central1

# Check Pub/Sub topics
gcloud pubsub topics list

# Check Cloud Workflows
gcloud workflows list --location=us-central1
```

---

## Component Overview

### Pillar 1: OBSERVE (Telemetry & Data Ingestion)
**Location**: `functions/observe.py`

Responsibilities:
- Aggregates logs from Cloud Logging
- Collects metrics from Cloud Monitoring
- Traces requests via Cloud Trace
- Listens to infrastructure events via Eventarc

### Pillar 2: ANALYZE / ORIENT (AI Core)
**Location**: `functions/analyze.py`

Responsibilities:
- Root Cause Analysis (RCA) using Vertex AI Gemini
- Context enrichment from multiple data sources
- Knowledge base integration for historical patterns
- Vector search for similar incidents

### Pillar 3: DECIDE (Multi-Agent Orchestration)
**Location**: `agents/orchestrator.py`

Responsibilities:
- Validates RCA findings against knowledge base
- Applies safety constraints and approval policies
- Generates specific remediation plans
- Manages multi-agent workflow

### Pillar 4: ACT (Remediation & Infrastructure)
**Location**: `remediation/executor.py`

Responsibilities:
- Executes Cloud Build for deployments
- Applies Terraform for infrastructure changes
- Manages rollback procedures
- Monitors remediation execution

### Communication & Reporting
**Location**: `functions/communicate.py`

Responsibilities:
- Sends incidents to Slack
- Creates Jira tickets
- Sends alerts to Opsgenie
- Provides human-in-the-loop oversight

---

## Usage

### Triggering Manual Incident
```bash
# Publish test event to Pub/Sub
gcloud pubsub topics publish infrastructure-events \
  --message '{
    "incident_id": "test-123",
    "severity": "CRITICAL",
    "service": "payment-service",
    "message": "Memory usage exceeding threshold"
  }'
```

### Monitoring Workflow Execution
```bash
# List recent executions
gcloud workflows executions list \
  --workflow=aidevops-orchestrator \
  --location=us-central1

# Inspect specific execution
gcloud workflows executions describe EXECUTION_ID \
  --workflow=aidevops-orchestrator \
  --location=us-central1
```

### Querying Incidents in BigQuery
```sql
SELECT
  incident_id,
  root_causes,
  severity,
  confidence,
  timestamp
FROM `PROJECT_ID.aidevops_knowledge.incident_history`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY timestamp DESC
LIMIT 10;
```

---

## Monitoring & Observability

### Cloud Logging
View platform logs:
```bash
gcloud logging read "resource.type=cloud_function" --limit 50
```

### Cloud Monitoring
Create dashboard:
```bash
gcloud monitoring dashboards create --config-from-file=monitoring-dashboard.json
```

### Error Tracking
```bash
gcloud error-reporting events list --project=YOUR_PROJECT_ID
```

---

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Submit pull request

---

## License

This project is licensed under the MIT License.

## Advanced AI-Native Enhancements to OODA

While **OODA remains the core operational framework**, modern AI techniques can significantly enhance each pillar:

### OODA + AI Enhancements

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Enhanced OODA Loop                               │
└─────────────────────────────────────────────────────────────────────┘

TRIGGER ──→ OBSERVE ──→ ANALYZE ──→ DECIDE ──→ ACT ──→ FEEDBACK
   ↓           ↓           ↓           ↓         ↓         ↓
   │           │           │           │         │         │
   └───────────┼───────────┼───────────┼─────────┼─────────┘
               │           │           │         │
            Predictive   Causal     RL Agents Digital
            Analytics   Inference   Learning   Twins
               ↓           ↓           ↓         ↓
            Prevent      True RCA   Optimal    Safe Test
            Incidents    Analysis   Decisions  Remediations
```

### Pillar-Specific AI Enhancements

#### OBSERVE Pillar Enhancements
- **Predictive Analytics**: Anomaly detection, time series forecasting
- **Digital Twins**: Real-time infrastructure simulation
- **Graph Neural Networks**: Dependency relationship mapping

#### ANALYZE Pillar Enhancements
- **Causal Inference**: True root cause vs correlation analysis
- **Large Language Models**: Natural language incident understanding
- **Neuro-Symbolic AI**: Explainable pattern recognition

#### DECIDE Pillar Enhancements
- **Reinforcement Learning**: Learn optimal remediation strategies
- **Multi-Agent Consensus**: Swarm intelligence decision making
- **Self-Adaptive Systems**: Dynamic threshold adjustment

#### ACT Pillar Enhancements
- **Digital Twins**: Pre-deployment remediation testing
- **Federated Learning**: Cross-environment knowledge sharing
- **Autonomous Optimization**: Self-tuning remediation parameters

### Implementation Strategy

**Phase 1: OODA Foundation** (Current)
- Basic OODA loop implementation
- Rule-based decision making
- Manual remediation validation

**Phase 2: AI Enhancement** (Recommended Next)
- Add predictive analytics to OBSERVE
- Implement causal inference in ANALYZE
- Add reinforcement learning to DECIDE

**Phase 3: Full AI-Native** (Future)
- Digital twins for safe testing
- Self-adaptive thresholds
- Autonomous optimization
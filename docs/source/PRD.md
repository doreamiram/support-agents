Modelyo Support Agents — Technical Requirements
2026-05-02
Contents
1 Modelyo Support Agents — Technical Requirements 1
1.1 1. Purpose & Scope . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 2
1.1.1 1.1 Purpose . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 2
1.1.2 1.2 In Scope . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 2
1.1.3 1.3 Out of Scope . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 2
1.2 2. System Context . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 2
1.2.1 2.1 Customers . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 2
1.2.2 2.2 Existing Infrastructure (assumed in place) . . . . . . . . . . . . . . . . . . . . . . . 2
1.2.3 2.3 Operating Environment . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 2
1.3 3. Functional Requirements . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 3
1.3.1 3.1 Channel Intake . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 3
1.3.2 3.2 Issue Reporting Guidance . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 3
1.3.3 3.3 Diagnostics Collection . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 3
1.3.4 3.4 First Response . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 3
1.3.5 3.5 Engineer Notification & SLA Tracking . . . . . . . . . . . . . . . . . . . . . . . . . 3
1.3.6 3.6 Escalation . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 3
1.3.7 3.7 Customer Communication . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4
1.3.8 3.8 Human Handoff . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4
1.3.9 3.9 Knowledge Use . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4
1.4 4. Non-Functional Requirements . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4
1.4.1 4.1 Multi-Tenancy & Isolation . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4
1.4.2 4.2 Confidentiality . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4
1.4.3 4.3 Audit & Observability . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4
1.4.4 4.4 Security . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 5
1.4.5 4.5 Performance & Availability . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 5
1.4.6 4.6 Quality & Evaluation . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 5
1.5 5. Integration Requirements . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 5
1.5.1 5.1 JIRA Service Desk . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 5
1.5.2 5.2 Slack . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 5
1.5.3 5.3 WhatsApp . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 5
1.5.4 5.4 On-Call Rotation . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 6
1.5.5 5.5 Knowledge Sources . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 6
1.6 6. Out of Scope . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 6
1.7 7. Architecture & Design Tasks . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 6
1.8 8. Open Decisions for Modelyo . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 7
1 Modelyo Support Agents — Technical Requirements
Version: 0.1 — frozen baseline for handoff Date: 2026-05-02
1
This document specifies the requirements for an LLM-based agent system providing Tier 1 and Tier 2 customer
support for Modelyo Confidential Cloud enterprise customers. The implementing third party is responsible for
system architecture and engineering. This document specifies what the system must do; it does not prescribe
how.
1.1 1. Purpose & Scope
1.1.1 1.1 Purpose
Modelyo customers (engineers operating Modelyo Confidential Cloud) currently raise support requests through
JIRA Service Desk, Slack, and WhatsApp. Tier 1 and Tier 2 handling — intake, triage, diagnostics guidance, first
response, engineer notification, escalation, and customer communication — is to be delivered by an LLM-based
agent system. This document defines the requirements for that system.
1.1.2 1.2 In Scope
The system must:
• Monitor inbound communication channels for customer issues
• Triage incoming issues and guide customers through reporting and diagnostics
• Generate first responses grounded in Modelyo's internal knowledge
• Notify the engineer on duty and track response time against SLAs
• Escalate when SLA timers expire, following a configured chain
• Maintain respectful, low-noise communication with customers throughout
1.1.3 1.3 Out of Scope
See §6 for the full enumeration. In summary: the system does not execute against customer infrastructure, does
not handle Tier 3 work, does not redefine Modelyo's existing severity model or on-call rotation, and does not
replace any existing infrastructure.
1.2 2. System Context
1.2.1 2.1 Customers
End users are engineers at customer organizations operating Modelyo Confidential Cloud. They are technically
literate; the system can assume engineering fluency (CLI usage, log inspection, kubectl, configuration files).
1.2.2 2.2 Existing Infrastructure (assumed in place)
• JIRA Service Desk is the system of record for tickets. The existing severity model is consumed as-is.
• Slack workspaces are shared between Modelyo and customer organizations.
• WhatsApp Business API is configured with Modelyo support phone numbers.
• Engineer on-call rotation is defined and tooled (PagerDuty, Opsgenie, or equivalent).
• Internal knowledge sources — runbooks/KB, historical resolved tickets, product documentation — exist
and can be queried.
1.2.3 2.3 Operating Environment
Modelyo Confidential Cloud is a confidential-computing platform. Customer ticket content may describe confidential workloads, enclave configurations, or sensitive operational state. Data privacy and trust boundaries are
first-class concerns the implementer must address explicitly.
2
1.3 3. Functional Requirements
1.3.1 3.1 Channel Intake
• FR-01. The system must monitor JIRA Service Desk for new tickets and ticket updates, identifying which
require agent attention.
• FR-02. The system must monitor designated Slack channels for customer messages that may indicate incidents or support requests.
• FR-03. The system must handle inbound WhatsApp messages from registered customer phone numbers.
• FR-04. The system must verify the identity of every inbound contact (mapping phone number, Slack user,
JIRA reporter to a known customer organization) before any outbound interaction.
• FR-05. The system must classify each inbound interaction (incident, question, follow-up, noise). Lowconfidence classifications must defer to a human rather than auto-route.
1.3.2 3.2 Issue Reporting Guidance
• FR-06. When a customer initiates contact outside JIRA, the system must guide the customer through opening a well-formed JIRA Service Desk ticket, including all required fields.
• FR-07. The system must validate that customer-provided information is sufficient to file the ticket; if not,
request the missing items before submission.
1.3.3 3.3 Diagnostics Collection
• FR-08. The system must guide the customer through diagnostic steps relevant to the reported symptom
and the affected Modelyo component. Guidance must be derived from authoritative runbooks.
• FR-09. The system must validate that collected diagnostics are sufficient for engineer review; if not, request
additional steps.
• FR-10. The system must attach collected diagnostics to the corresponding JIRA Service Desk ticket.
• FR-11. The system must not execute commands against customer infrastructure under any circumstance.
Diagnostics are customer-driven; the system guides, the customer runs.
1.3.4 3.4 First Response
• FR-12. For each new incident, the system must generate a first response containing acknowledgement of
the report, any known related issues from internal knowledge, and suggested next steps or workarounds
when known.
• FR-13. Every claim in a first response must be traceable to an authoritative source (runbook, past resolved
ticket, product documentation). The system must not generate guidance not grounded in these sources.
• FR-14. When no confident answer can be sourced, the first response must acknowledge the issue and
indicate that an engineer is being engaged — no fabricated guidance.
1.3.5 3.5 Engineer Notification & SLA Tracking
• FR-15. The system must notify the engineer on duty for the relevant Modelyo component when an incident
is logged, using the existing on-call rotation as the source of truth.
• FR-16. The system must track an SLA timer per incident, starting from the earliest customer contact across
any channel. Severity-based response targets are consumed from JIRA Service Desk's existing severity
model.
• FR-17. The system must distinguish ”engineer notified” from ”engineer engaged” (acknowledgement received) and maintain timer state across the lifecycle of each incident.
1.3.6 3.6 Escalation
• FR-18. When an SLA timer expires without engineer engagement, the system must escalate to the next role
in the configured escalation chain.
3
• FR-19. The escalation chain must be configurable along two dimensions: severity (depth and pace of escalation) and Modelyo component (which chain is followed).
• FR-20. Every escalation event must be auditable: who was contacted, when, why, and the outcome.
1.3.7 3.7 Customer Communication
• FR-21. The system must inform the customer when meaningful state changes occur (ticket opened, engineer engaged, escalation triggered, additional information needed, resolution proposed, ticket resolved).
The canonical list of qualifying events is to be specified during design (T-11).
• FR-22. The system must not message the customer outside the canonical state-change events. No ”just
checking in”; no status pings without new information.
• FR-23. The system must respect per-customer quiet hours (resolved against the customer's timezone) and
a configurable cooldown between unsolicited outbound messages. The Severity-1 override rule is to be
specified during design (T-12).
1.3.8 3.8 Human Handoff
• FR-24. When the system hands an incident to a human, it must deliver a structured context packet: customer goal, attempts made, diagnostics collected, current SLA timer state, suggested next action.
• FR-25. The system must support handoff at any point in the workflow: low-confidence triage, exhausted
runbook, customer request, classification failure, dependency unavailable.
1.3.9 3.9 Knowledge Use
• FR-26. The system must use Modelyo's internal runbooks/KB, past resolved JIRA tickets, and product
documentation as authoritative knowledge sources.
• FR-27. Live system signals (status page, current incidents, recent releases) are explicitly excluded from v1
knowledge sources.
• FR-28. Knowledge retrieval must respect customer-tenant boundaries: a query for customer A must not
surface customer B's confidential ticket history.
1.4 4. Non-Functional Requirements
1.4.1 4.1 Multi-Tenancy & Isolation
• NFR-01. Customer data must be isolated such that one customer's data cannot leak into another customer's
interaction, knowledge retrieval, or audit trail.
• NFR-02. Tenant scoping must be enforced at the storage layer, not only at the application layer.
1.4.2 4.2 Confidentiality
• NFR-03. The system must respect Modelyo's confidential-computing posture. The implementation must
explicitly address where customer data flows and must not place customer data outside the trust boundary
without explicit Modelyo sign-off.
• NFR-04. A customer-data classification scheme and corresponding handling rules must be defined as part
of the design (T-03).
1.4.3 4.3 Audit & Observability
• NFR-05. Every customer-facing message, classification decision, routing decision, escalation step, and external action taken by the system must be recorded in an audit trail.
• NFR-06. The audit trail must be tamper-evident and immutable, with per-tenant scoping and a defined
retention period meeting applicable regulatory obligations.
4
• NFR-07. The system must produce operational telemetry (latency, error rates, classification accuracy, escalation correctness, SLA breach rates) suitable for monitoring and quality measurement.
1.4.4 4.4 Security
• NFR-08. All inbound webhooks must verify sender signatures and reject unsigned or replayed events.
• NFR-09. Inbound channel content must not be allowed to manipulate the system's behavior beyond the
intended customer-input role (prompt-injection mitigation).
• NFR-10. Credentials must not appear in customer-facing messages, audit logs, or agent context. Credentials
inadvertently sent by customers must be detected, redacted, and the customer notified to rotate.
• NFR-11. No agent or component may hold long-lived credentials in memory or prompts; credentials must
be sourced from a secrets management system and rotated.
1.4.5 4.5 Performance & Availability
• NFR-12. First-response, classification, and per-channel response latency targets are to be agreed during
design (T-15).
• NFR-13. When a critical dependency is unavailable (LLM inference, knowledge source, channel API, oncall system), the system must degrade gracefully and surface the failure to humans rather than fail silently.
1.4.6 4.6 Quality & Evaluation
• NFR-14. The system's behavior must be measurable: classification accuracy, response groundedness, escalation correctness, SLA detection accuracy, and customer-communication etiquette compliance must all
be quantifiable.
• NFR-15. Regressions in any of the above must be detectable before deployment.
1.5 5. Integration Requirements
1.5.1 5.1 JIRA Service Desk
• IR-01. The system must subscribe to ticket lifecycle events (created, commented, status-changed, resolved)
and act on them within agreed latency targets.
• IR-02. The system must read and write JIRA fields needed for triage, communication, and escalation.
• IR-03. The system must thread its comments coherently and identify itself clearly as an automated agent.
• IR-04. JIRA permissions must be scoped per customer; the system must not have read access to one customer's tickets while servicing another.
1.5.2 5.2 Slack
• IR-05. The system must monitor designated shared customer channels and respond appropriately to messages addressed to it or matching incident criteria.
• IR-06. The system must not act on messages from unverified senders.
1.5.3 5.3 WhatsApp
• IR-07. The system must handle inbound messages from registered customer numbers, including verifying
sender identity before responding.
• IR-08. Outbound communications must comply with WhatsApp Business platform policies, including
session-window constraints.
5
1.5.4 5.4 On-Call Rotation
• IR-09. The system must consume the existing on-call schedule to identify the engineer on duty for any
given Modelyo component at any given time.
• IR-10. Notifications must be acknowledgeable, and acknowledgement state must be available to the system
for SLA tracking.
1.5.5 5.5 Knowledge Sources
• IR-11. The system must ingest Modelyo's internal runbooks/KB, past resolved JIRA tickets, and product
documentation as queryable knowledge sources, with freshness guarantees agreed during design (T-13).
1.6 6. Out of Scope
Item Reason
Autonomous remediation against customer infrastructure Confidential-cloud trust posture; v1 is guide-only
Tier 3 / engineering deep-dive support Agents handle Tier 1 and Tier 2 only
Live system signals as knowledge source Adds correlation/freshness complexity without clear v1 value
Modelyo internal-team support Agents serve external Modelyo customers only
Redefinition of JIRA SD severity model Existing model is consumed as-is
Redefinition of on-call rotation Existing rotation is consumed as-is
Replacement of JIRA SD, Slack, or WhatsApp Business Existing infrastructure is assumed
Voice channel and consumer chat widget Channel set is JIRA SD + Slack + WhatsApp only
Per-customer SLA customization Severity-driven SLAs only for v1
Multi-language support English only for v1
1.7 7. Architecture & Design Tasks
These are tasks the implementing third party owns. Each must produce a design artifact reviewable by Modelyo
before implementation begins.
• T-01. Design the agent system decomposition: components, responsibilities, interaction model.
• T-02. Evaluate LLM hosting options (managed external API, self-hosted, hybrid) against confidentiality,
performance, and cost; recommend an approach with rationale.
• T-03. Define the data classification scheme for fields traversing the system, and the routing rules per classification.
• T-04. Specify the trust boundaries and the data-flow rules across them, consistent with Modelyo's
confidential-computing posture.
• T-05. Define the integration data contracts for events flowing between channels, agents, and downstream
systems.
• T-06. Specify webhook security mechanisms per integration (signature verification, replay protection, replay window).
• T-07. Specify the prompt-injection mitigation strategy for inbound channel content reaching agent context.
• T-08. Specify the audit trail schema, immutability mechanism, retention policy, and integrity-verification
approach.
• T-09. Specify the SLA timing model: clock events, pause/resume rules, multi-channel timestamp resolution, time zone handling.
• T-10. Specify the escalation chain configuration model and traversal logic (severity × component).
• T-11. Specify the canonical list of state-change events that warrant proactive customer outreach (FR-21).
6
• T-12. Specify the customer communication etiquette policy in detail: quiet-hours rules, cooldown floors,
Severity-1 override semantics (FR-23).
• T-13. Specify the knowledge ingestion pipeline: sources, freshness, refresh, tenant-scoped retrieval (FR-26
through FR-28).
• T-14. Specify failure-mode and degradation behaviors for each critical dependency (NFR-13).
• T-15. Specify the evaluation framework: metrics, test corpus, regression gating, production feedback loop.
Includes latency targets (NFR-12).
• T-16. Specify per-requirement acceptance criteria sufficient for Modelyo to verify implementation against
this document.
1.8 8. Open Decisions for Modelyo
The following require Modelyo stakeholder input before implementation kickoff. Each is owned by Modelyo, not
the third-party implementer.
• D-01. Approval of the data classification policy proposed in T-03 — particularly which classifications may
flow outside Modelyo's trust boundary. Gates the LLM hosting decision in T-02.
• D-02. Configuration of the severity × component escalation chain, with input from the on-call rotation
owner (feeds T-10).
• D-03. Numeric thresholds for knowledge-source freshness SLAs (feeds T-13).
• D-04. Approval of the canonical list of state-change events for proactive outreach (feeds T-11).
• D-05. Audit retention period and applicable regulatory obligations (feeds T-08).
• D-06. WhatsApp message templates required for out-of-session outbound communication (Meta
pre-approval workflow).
• D-07. Acceptance criteria sign-off process between Modelyo and the third party.
Version 0.1 — frozen baseline for handoff. Subsequent revisions issued as numbered amendments.

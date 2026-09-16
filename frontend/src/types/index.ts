export type UserRole = "ADMIN" | "BUSINESS_MANAGER" | "ANALYST";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type Decision = "APPROVE" | "REVIEW" | "BLOCK";
export type AlertSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type AlertStatus = "NEW" | "INVESTIGATING" | "CONFIRMED_FRAUD" | "FALSE_POSITIVE" | "RESOLVED";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface Transaction {
  id: string;
  transaction_id: string;
  customer_id: string;
  amount: number;
  currency: string;
  transaction_datetime: string;
  payment_method: string | null;
  ip_address: string | null;
  device_id: string | null;
  location: string | null;
  account_age_days: number;
  previous_transaction_count: number;
  transaction_status: string;
  risk_score: number;
  risk_level: RiskLevel;
  decision: Decision;
  anomaly_score: number;
  rule_score: number;
  risk_factors: string[];
  explanation: string | null;
  created_at: string;
}

export interface Alert {
  id: string;
  transaction_id: string;
  customer_id: string;
  severity: AlertSeverity;
  title: string;
  reason: string | null;
  status: AlertStatus;
  assigned_to: string | null;
  risk_score?: number | null;
  created_at: string;
  updated_at: string;
}

export interface Notification {
  id: string;
  alert_id: string | null;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface Customer {
  id: string;
  customer_id: string;
  name: string;
  email: string | null;
  account_age_days: number;
  risk_score: number;
  risk_level: RiskLevel;
  total_transactions: number;
  suspicious_transactions: number;
  devices_used: number;
  locations_used: number;
  previous_fraud_reports: number;
  created_at: string;
}

export interface CustomerRiskProfile {
  customer_id: string;
  name: string;
  risk_level: RiskLevel;
  risk_score: number;
  total_transactions: number;
  suspicious_transactions: number;
  devices_used: number;
  locations_used: number;
  previous_fraud_reports: number;
  last_updated: string;
}

export type NetworkNodeType = "customer" | "device" | "ip" | "transaction" | "location";

export interface NetworkNode {
  id: string;
  type: NetworkNodeType;
  label: string;
  risk_level?: string;
  amount?: number;
}

export interface NetworkEdge {
  source: string;
  target: string;
  type?: string;
}

export interface FraudNetworkGraphData {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  root_customer_id?: string;
  customer_count?: number;
  shared_device_count?: number;
  shared_ip_count?: number;
  linking_transaction_count?: number;
  truncated?: boolean;
}

export interface FraudRing {
  ring_id: string;
  size: number;
  customer_ids: string[];
  shared_device_count: number;
  shared_ip_count: number;
  total_suspicious_transactions: number;
  avg_risk_score: number;
  max_risk_level: RiskLevel;
}

export interface DashboardSummary {
  total_transactions: number;
  high_risk_transactions: number;
  medium_risk_transactions: number;
  fraud_alerts: number;
  confirmed_fraud: number;
  false_positives: number;
  average_risk_score: number;
}

export interface AdminDashboardSummary {
  total_transactions: number;
  high_risk_transactions: number;
  medium_risk_transactions: number;
  low_risk_transactions: number;
  blocked_transactions: number;
  under_review_transactions: number;
  fraud_alerts: number;
  new_alerts: number;
  investigating_alerts: number;
  confirmed_fraud: number;
  false_positives: number;
  false_positive_rate: number;
  average_risk_score: number;
  suspicious_customers: number;
}

export interface FraudTrendPoint {
  date: string;
  low: number;
  medium: number;
  high: number;
  confirmed: number;
  total: number;
}

export interface RiskDistributionItem {
  risk_level: RiskLevel;
  count: number;
}

export interface AlertStatusBreakdownItem {
  status: AlertStatus;
  count: number;
}

export interface SuspiciousCustomer {
  id: string;
  customer_id: string;
  name: string;
  risk_score: number;
  risk_level: RiskLevel;
  total_transactions: number;
  suspicious_transactions: number;
  devices_used: number;
  locations_used: number;
  previous_fraud_reports: number;
}

export interface SuspiciousFingerprint {
  value: string;
  transaction_count: number;
  customer_count: number;
  high_risk_count: number;
  avg_risk_score: number;
  last_seen: string;
  shared_across_customers: boolean;
  suspicion_score: number;
}

export interface Rule {
  id: string;
  name: string;
  description: string | null;
  rule_type: string;
  configuration: Record<string, number | string>;
  risk_weight: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InvestigationNote {
  id: string;
  alert_id: string;
  analyst_id: string;
  analyst_name: string | null;
  note: string;
  created_at: string;
}

export interface Feedback {
  id: string;
  alert_id: string;
  analyst_id: string;
  analyst_name: string | null;
  actual_result: "CONFIRMED_FRAUD" | "FALSE_POSITIVE";
  comments: string | null;
  created_at: string;
}

export interface CaseTransactionSummary {
  id: string;
  transaction_id: string;
  customer_id: string | null;
  amount: number;
  currency: string;
  transaction_datetime: string;
  payment_method: string | null;
  device_id: string | null;
  ip_address: string | null;
  location: string | null;
  transaction_status: string;
  risk_score: number;
  risk_level: RiskLevel;
  decision: Decision;
}

export interface CaseTransactionDetail extends CaseTransactionSummary {
  account_age_days: number;
  anomaly_score: number;
  rule_score: number;
  risk_factors: string[];
  triggered_rules: string[];
  explanation: string | null;
  created_at: string;
}

export interface CaseAlertSummary {
  id: string;
  transaction_id: string | null;
  customer_id: string | null;
  severity: AlertSeverity;
  title: string;
  reason: string | null;
  status: AlertStatus;
  created_at: string;
}

export interface CaseFingerprintUsage {
  value: string;
  transaction_count: number;
  first_seen: string;
  last_seen: string;
  device_type?: string | null;
  country?: string | null;
  city?: string | null;
}

export interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
}

export interface InvestigationCase {
  alert: CaseAlertSummary;
  customer: Customer;
  transaction: CaseTransactionDetail;
  risk_factors: string[];
  triggered_rules: string[];
  ai_explanation: string | null;
  transaction_history: CaseTransactionSummary[];
  related_transactions: CaseTransactionSummary[];
  devices: CaseFingerprintUsage[];
  ip_addresses: CaseFingerprintUsage[];
  locations: CaseFingerprintUsage[];
  related_alerts: CaseAlertSummary[];
  investigation_notes: InvestigationNote[];
}

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  action: string;
  details: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface ApiKey {
  id: string;
  business_name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  api_key: string;
}

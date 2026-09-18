export type AgentName = "architect" | "engineer" | "executor" | "healer" | "system";
export type AgentStatus = "idle" | "running" | "complete" | "error" | "skipped";
export type TestCategory =
  | "happy_path"
  | "edge_case"
  | "failure_mode"
  | "security"
  | "concurrency"
  | "non_functional";

export interface TestCase {
  id: string;
  title: string;
  category: TestCategory;
  priority: "critical" | "high" | "medium" | "low";
  preconditions: string[];
  steps: string[];
  assertions: string[];
  failure_modes: string[];
  tags: string[];
}

export interface TestResult {
  nodeid: string;
  outcome: "passed" | "failed" | "skipped" | "error";
  duration_ms: number;
  message: string;
}

export interface ExecutionSummary {
  passed: boolean;
  total: number;
  passed_count: number;
  failed_count: number;
  skipped_count: number;
  error_count: number;
  duration_ms: number;
  exit_code: number;
  stdout: string;
  stderr: string;
  traceback: string;
  results: TestResult[];
  junit_xml: string;
}

export interface AgentEvent {
  ts: number;
  agent: AgentName;
  status: AgentStatus | "log";
  message: string;
  detail: Record<string, unknown>;
}

export interface GenerateResponse {
  run_id: string;
  title: string;
  domain: string;
  status: string;
  provider: string;
  test_cases: TestCase[];
  sut_filename: string;
  test_filename: string;
  sut_code: string;
  pytest_code: string;
  execution: ExecutionSummary;
  heal_iterations: number;
  coverage_score: number;
  logs: string[];
  events: AgentEvent[];
  duration_ms: number;
  created_at: string;
}

export interface SampleSpec {
  id: string;
  title: string;
  spec: string;
}

export interface PipelineStep {
  id: AgentName;
  label: string;
  status: AgentStatus;
  message: string;
}

export const EMPTY_EXECUTION: ExecutionSummary = {
  passed: false,
  total: 0,
  passed_count: 0,
  failed_count: 0,
  skipped_count: 0,
  error_count: 0,
  duration_ms: 0,
  exit_code: 0,
  stdout: "",
  stderr: "",
  traceback: "",
  results: [],
  junit_xml: "",
};

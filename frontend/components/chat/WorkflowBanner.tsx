import Link from "next/link";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import type { WorkflowData } from "./types";

export function WorkflowBanner({ workflow }: { workflow: WorkflowData }) {
  if (!workflow.type && !workflow.reason) return null;

  const needsApproval = workflow.status === "pending_approval" || workflow.type === "approval_required";
  const title = needsApproval ? "Approval Required" : "Case Escalated";
  const variant = needsApproval ? "warning" : "danger";

  return (
    <Alert
      variant={variant}
      title={title}
      action={
        <Link href="/approvals">
          <Button variant="outline" size="sm">
            View Workflows
          </Button>
        </Link>
      }
    >
      {workflow.type && (
        <span>
          Workflow <strong>{workflow.type.replace(/_/g, " ")}</strong>
          {workflow.status ? ` (${workflow.status})` : ""}
          {workflow.queue ? ` → ${workflow.queue.replace(/_/g, " ")}` : ""}
          {workflow.risk_tier ? ` · risk ${workflow.risk_tier}` : ""}
          {workflow.reason ? ` — ${workflow.reason}` : ""}
        </span>
      )}
    </Alert>
  );
}

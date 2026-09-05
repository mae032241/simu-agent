"""Human-approval query routes for the single Root scheduler facade."""

from __future__ import annotations

from typing import Any

from ..schema.approval import HumanDecision

class RootApprovalRoutes:
    def approval_status(self, *, name: str) -> dict[str, Any]:
        binding = self._binding("approval", name)
        approval_id = binding.object_id
        status = self.approvals.status(approval_id)
        selected_option = None
        rationale = None
        if status.decision_ref is not None:
            decision = HumanDecision.model_validate_json(
                self.approvals.artifacts.read(status.decision_ref), strict=True
            )
            selected_option = decision.selected_option
            rationale = decision.rationale
        result = {
            **self._binding_value(binding),
            "status": status.status,
            "selected_option": selected_option,
            "rationale": rationale,
        }
        if (
            status.status == "pending"
            and status.review_path is not None
            and self.approval_base_url is not None
        ):
            result["review_url"] = (
                self.approval_base_url.rstrip("/") + status.review_path
            )
        return result

    def approval_list(self, *, status: str | None, limit: int) -> dict[str, Any]:
        items = []
        for binding in self.bindings.list(instance=self._instance_id(), namespace="approval"):
            item = self.approval_status(name=binding.name)
            if status is not None and item["status"] != status:
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return {"approvals": items}



__all__ = ["RootApprovalRoutes"]

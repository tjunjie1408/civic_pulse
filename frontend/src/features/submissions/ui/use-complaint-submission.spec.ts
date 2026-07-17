import { effectScope } from "vue"
import { describe, expect, it } from "vitest"

import type { ComplaintSubmissionResult } from "../application/complaint-port"
import type { ComplaintSubmissionRequest } from "../domain/complaint"
import { useComplaintSubmission } from "./use-complaint-submission"

const request: ComplaintSubmissionRequest = {
  text: "Blocked drain near the market",
  latitude: 3.07,
  longitude: 101.52,
  reportedAt: "2026-07-17T00:00:00Z",
  category: "blocked_drain",
  photoPath: "field-photo.jpg",
}

class ControllableSubmitComplaint {
  readonly calls: Array<{ request: ComplaintSubmissionRequest; key: string }> = []
  readonly responses: Array<(result: ComplaintSubmissionResult) => void> = []

  execute(candidate: ComplaintSubmissionRequest, key: string, signal: AbortSignal): Promise<ComplaintSubmissionResult> {
    void signal
    this.calls.push({ request: candidate, key })
    return new Promise((resolve) => this.responses.push(resolve))
  }
}

function createSubmission() {
  const useCase = new ControllableSubmitComplaint()
  const keys = ["key-1", "key-2"]
  const scope = effectScope()
  const submission = scope.run(() => useComplaintSubmission(useCase, () => keys.shift() ?? "key-fallback"))
  if (submission === undefined) throw new Error("The submission composable must be scoped")
  return { useCase, submission, scope }
}

describe("useComplaintSubmission", () => {
  it("reuses one idempotency key for a failed retry and generates a new key after success", async () => {
    const { useCase, submission, scope } = createSubmission()

    const first = submission.submit(request)
    useCase.responses[0]?.({ ok: false, error: { kind: "network" } })
    await first
    expect(submission.state.value.kind).toBe("failed")

    const retry = submission.retry()
    useCase.responses[1]?.({
      ok: true,
      submission: {
        complaint: { complaintId: "complaint-1", ...request },
        created: true,
        replayed: false,
        relationshipDecisions: [],
        incidentTransition: { previousIncidentSnapshotIds: [], currentIncidentSnapshotIds: [] },
        incidents: [],
        priorities: [],
      },
    })
    await retry
    expect(useCase.calls.map((call) => call.key)).toEqual(["key-1", "key-1"])
    expect(submission.state.value.kind).toBe("succeeded")

    const next = submission.submit(request)
    useCase.responses[2]?.({ ok: false, error: { kind: "network" } })
    await next
    expect(useCase.calls[2]?.key).toBe("key-2")
    scope.stop()
  })
})

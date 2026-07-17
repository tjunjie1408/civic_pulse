import { describe, expect, it } from "vitest"

import { incidentDetailPath, parseAppRoute } from "./app-route"

describe("app route", () => {
  it("parses a snapshot detail route without changing the opaque ID", () => {
    expect(parseAppRoute("/incidents/snapshot%2Fwith%20space")).toEqual({
      kind: "incident-detail",
      snapshotId: "snapshot/with space",
    })
  })

  it("falls back to the queue for malformed or unrelated paths", () => {
    expect(parseAppRoute("/")).toEqual({ kind: "queue" })
    expect(parseAppRoute("/incidents/")).toEqual({ kind: "queue" })
    expect(parseAppRoute("/incidents/a/b")).toEqual({ kind: "queue" })
    expect(parseAppRoute("/incidents/%E0%A4%A")).toEqual({ kind: "queue" })
  })

  it("encodes snapshot IDs only in the URL boundary", () => {
    expect(incidentDetailPath("snapshot/with space")).toBe(
      "/incidents/snapshot%2Fwith%20space",
    )
  })
})

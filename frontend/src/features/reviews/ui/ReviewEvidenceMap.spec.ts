import { mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import { reviewDetailFixture } from "../testing/review-fixtures"
import ReviewEvidenceMap from "./ReviewEvidenceMap.vue"

describe("ReviewEvidenceMap", () => {
  it("renders neutral complaint points and a relationship line without incident overlays", () => {
    const wrapper = mount(ReviewEvidenceMap, { props: { detail: reviewDetailFixture } })

    expect(wrapper.get("[data-review-evidence-map]").attributes("role")).toBe("img")
    expect(wrapper.findAll("[data-review-evidence-point]")).toHaveLength(2)
    expect(wrapper.text()).toContain("Neutral evidence map")
    expect(wrapper.find("[data-review-evidence-map]").attributes("data-heatmap")).toBeUndefined()
    expect(wrapper.find("[data-review-evidence-map]").attributes("data-radius-metres")).toBeUndefined()
    expect(wrapper.text()).not.toContain("affected radius")
  })
})

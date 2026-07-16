import { mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import App from "./App.vue"

describe("App shell", () => {
  it("provides the CivicPulse incident operations landmarks", () => {
    const wrapper = mount(App)
    const banner = wrapper.find("header")

    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain("CivicPulse")
    expect(wrapper.get("h1").text()).toBe("Incident operations")
    expect(wrapper.find("main").exists()).toBe(true)
  })
})

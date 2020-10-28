import { mount } from "@vue/test-utils";
import App from "../components/App.vue";

describe("Mounted App", () => {
  const wrapper = mount(App);
  test("has the expected html structure", () => {
    expect(wrapper.element).toMatchSnapshot();
  })
});


import Vue from 'vue';
import { expect } from 'chai';
import { shallowMount } from "@vue/test-utils";
import App from "../src/js/components/App.vue";

describe('App.vue', () => {
    // beforeEach(() => {
    //   component = shallowMount(App);
    // });
    describe('app', () => {
      let component = shallowMount(App);
      it("should render app on mount", () => {
        expect(component.find("#app").exists()).to.be.true;
      });
    })
})
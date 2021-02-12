<template>
    <div id="app">
        <div id="loadingIndicator" class="loader" v-show="isLoading()"></div>
        <header-section></header-section>
        <main>
            <!--empty and content populated dynamically-->
            <domain-section v-bind:content="domainContent"></domain-section>
            <error></error>
        </main>
        <debug-section></debug-section>
        <footer-section></footer-section>
    </div>
</template>
<script>
    import Vue from 'vue';
    import "custom-event-polyfill";
    import bootstrap from "bootstrap";
    import $ from 'expose-loader?exposes[]=$&exposes[]=jQuery!jquery';
    import "bootstrap/dist/css/bootstrap.min.css";
    import "../style/app.less";
    import Error from "./Error.vue";
    import DomainSection from "./DomainSection.vue";
    import HeaderSection from "./Header.vue";
    import FooterSection from "./Footer.vue";
    import DebugSection from "./DebugSection.vue";
    import AppData from "../data/data.js";
    import BaseMethods from "../js/Base.js";
    import {sendRequest} from "../js/Utility.js";

    Vue.prototype.$http = sendRequest;

    export default {
        components: {
            Error,
            DomainSection,
            HeaderSection,
            FooterSection,
            DebugSection
        },
        mixins: [BaseMethods],
        errorCaptured(Error, Component, info) {
            console.error("Error: ", Error, " Component: ", Component, " Message: ", info);
            return false;
        },
        errorHandler(err, vm) {
            this.dataError = true;
            var errorElement = document.getElementById("errorMessage");
            if (errorElement) {
                errorElement.innerHTML = "Error occurred initializing Vue instance.";
            }
            console.warn("Vue instance threw an error: ", vm, this);
            console.error("Error thrown: ", err);
        },
        data() {
            return {
                loading: true,
                initialized: false,
                debugMode: false,
                ...AppData};
        }
    }
</script>

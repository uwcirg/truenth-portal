<template>
    <div id="app">
        <div id="loadingIndicator" class="loader" v-show="isLoading()"></div>
        <header-section></header-section>
        <main>
            <!--<intro-section v-bind:content="introContent"></intro-section>-->
            <!--empty and content populated dynamically-->
            <domain-section v-bind:content="domainContent"></domain-section>
            <!-- TODO will there be a resource section? if so have a separate template section -->
            <error></error>
        </main>
        <footer-section></footer-section>
    </div>
</template>
<script>
    import Vue from 'vue';
    import "custom-event-polyfill";
    import bootstrap from "bootstrap";
    import $ from 'expose-loader?exposes[]=$&exposes[]=jQuery!jquery';
    //import $ from 'expose-loader';
    import "bootstrap/dist/css/bootstrap.min.css";
    import "../../style/app.less";
    import Error from "./Error.vue";
    import DomainSection from "./DomainSection.vue";
    import HeaderSection from "./Header.vue";
    import FooterSection from "./Footer.vue";
    //import IntroSection from "./IntroSection.vue";
    import AppData from "../../data/data.js";
    import BaseMethods from "../Base.js";
    import {sendRequest} from "../Utility.js";

    Vue.prototype.$http = sendRequest;

    export default {
        components: {
            Error,
            DomainSection,
            HeaderSection,
            FooterSection,
            //IntroSection
        },
        mixins: [BaseMethods],
        errorCaptured(Error, Component, info) {
           // console.error("Error: ", Error, " Component: ", Component, " Message: ", info);
            return false;
        },
        errorHandler(err, vm) {
            this.dataError = true;
            var errorElement = document.getElementById("errorMessage");
            if (errorElement) {
                errorElement.innerHTML = "Error occurred initializing Vue instance.";
            }
          //  console.warn("Vue instance threw an error: ", vm, this);
          //  console.error("Error thrown: ", err);
        },
        data() {
            return {
                loading: true,
                initialized: false,
                ...AppData};
        }
    }
</script>

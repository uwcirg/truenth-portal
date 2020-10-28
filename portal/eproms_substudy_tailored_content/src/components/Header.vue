<!-- portal wrapper banner -->
<template>
    <header :id="sectionId" ref="header" v-bind:class="{active : loaded}">
        <div class="content" v-html="content"></div>
    </header>
</template>
<script>
    import Vue from "vue";
    import {getWrapperJS} from "../js/Utility.js";
    export default {
        mounted() {
            Vue.nextTick(() => {
                this.$http(this.getAppObj().portalWrapperURL)
                .then(response => {
                        this.content = response;
                        Vue.nextTick(() => {
                            getWrapperJS(`#${this.sectionId}`);
                            setTimeout(function() {
                                this.loaded = true;
                            }.bind(this), 300);
                    });
                }).catch(e => {
                    this.content = `Error loading portal wrapper ${e}`;
                    this.loaded = true;
                });
            });
        },
        methods: {
            getAppObj() {
                return this.$parent;
            },
        },
        data() {
            return {
                sectionId: "headerSection",
                content: "",
                loaded: false
            }
        }
    };
</script>


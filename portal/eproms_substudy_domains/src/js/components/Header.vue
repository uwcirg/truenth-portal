<template>
    <header :id="sectionId" ref="header" v-bind:class="{active : loaded}">
        <div class="content" v-html="content"></div>
    </header>
</template>
<script>
    import {sendRequest, getWrapperJS} from "../Utility.js";
    export default {
        components: {
        },
        mounted: function() {
            let self = this;
            Vue.nextTick(function() {
                sendRequest(self.getAppObj().portalWrapperURL)
                .then(
                    response => {
                        self.content = response;
                        setTimeout(function() {
                            getWrapperJS(`#${self.sectionId}`);
                        }, 50);
                        setTimeout(function() {
                            self.loaded = true;
                        }, 350);
                }).catch(e => {
                    self.content = `Error loading portal wrapper ${e}`;
                    self.loaded = true;
                });
            });
        },
        methods: {
            getAppObj: function() {
                return this.$parent;
            },
        },
        data: function() {
            return {
                sectionId: "headerSection",
                content: "",
                loaded: false
            }
        }
    };
</script>

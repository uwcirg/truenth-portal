<!-- portal footer -->
<!-- we need this right? -->
<template>
    <footer :id="sectionId" ref="footer" v-bind:class="{active : loaded}">
        <div class="content" v-html="content"></div>
    </footer>
</template>
<script>
    import {sendRequest} from "../Utility.js";
    export default {
        components: {
        },
        mounted: function() {
            let self = this;
            Vue.nextTick(function() {
                sendRequest(self.getAppObj().portalFooterURL)
                .then(
                    response => {
                        self.content = response;
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
                sectionId: "footerSection",
                content: "",
                loaded: false
            }
        }
    };
</script>

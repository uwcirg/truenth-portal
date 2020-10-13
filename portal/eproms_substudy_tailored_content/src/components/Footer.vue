<!-- portal footer -->
<template>
    <footer :id="sectionId" ref="footer" v-bind:class="{active : loaded}">
        <div class="content" v-html="content"></div>
    </footer>
</template>
<script>
    export default {
        mounted() {
            this.$http(this.getAppObj().portalFooterURL)
            .then(
                response => {
                    this.content = response;
                    Vue.nextTick(() => {
                        setTimeout(function() {
                            this.loaded = true;
                        }.bind(this), 350);
                    })
            }).catch(e => {
                this.content = `Error loading portal wrapper ${e}`;
                this.loaded = true;
            });
        },
        methods: {
            getAppObj() {
                return this.$parent;
            },
        },
        data() {
            return {
                sectionId: "footerSection",
                content: "",
                loaded: false
            }
        }
    };
</script>

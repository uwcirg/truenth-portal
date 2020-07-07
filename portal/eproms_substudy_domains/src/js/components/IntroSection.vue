<!--
    this is the landing page
-->
<template>
    <section id="introSection" ref="intro" v-bind:class="{active : getAppObj().isCurrentView('intro'), main: true}">
        <!--TODO remove this -->
        <div>THIS IS WELCOME PAGE</div>
        <div v-html="content" v-bind:class="{active : content, 'body-content': true}"></div>
    </section>
</template>
<script>
    export default {
        props: {
            content: {
                type: String,
                required: true
            }
        },
        components: {
        },
        methods: {
            getAppObj: function() {
                return this.$parent;
            }
        }
    };
</script>

<!--this is the domain page -->
<template>
    <section id="domainSection" ref="domain" v-bind:class="{active : getAppObj().isCurrentView('domain') && content, main: true}">
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
        methods: {
            getAppObj() {
                return this.$parent;
            }
        }
    };
</script>

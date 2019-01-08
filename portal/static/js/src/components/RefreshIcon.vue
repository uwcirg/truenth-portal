<template>
    <!-- PSA Tracker component -->
    <span class="glyphicon glyphicon-refresh refresh" aria-hidden="true" v-on:click='$emit("refresh")' v-bind:title="title"></span>
</template>
<script>
    export default {
        props: ["title"]
    }
</script>
<template> <!-- PSA Tracker component -->
    <select v-bind:id='id' class='form-control filter-control' v-on:change='$emit("changeevent", $event)'><option value='' class='select-option'>{{prompt}}</option><option v-bind:value='item' v-for='(item, index) in items' v-bind:selected='item == selectedvalue' :key='index'>{{item}}</option></select>
</template>
<script>
    export default {
        props: ["id", "prompt", "selectedvalue", "items"]
    }
</script>

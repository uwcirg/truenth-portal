<template>
    <aside id="errorMessage" v-bind:class="{active: getAppObj().hasError()}">
        <div class="close" @click="getAppObj().resetError()">X</div>
        <div class="body">
            <!-- display generic message to user, but error details can be viewed in console -->
            <div v-if="getAppObj().errorMessage" class="error-message content">Error retrieving data, see console for detail</div>
        </div>
    </aside>
</template>
<script>
    export default { 
        methods: {
            getAppObj() {
                return this.$parent;
            },
        }
    };
</script>

<template>
    <aside>
        <div id="errorMessage" v-bind:class="{active: getAppObj().hasError()}">
            <div class="body">
                <div v-if="getAppObj().errorMessage" v-html="getAppObj().errorMessage" class="error-message content"></div>
            </div>
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

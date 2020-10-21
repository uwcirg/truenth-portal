<template>
    <aside>
        <div id="debugContainer" v-bind:class="{active: getAppObj().isDebugMode()}">
            <h5>Development Tool</h5>
            <label>Change Country Code</label>
            <select id="countryCodeSelector">
                <option value="">-- Select --</option>
                <option v-for="item in getAppObj().getEligibleCountryCodes()" :key="item.code" :value="item.code" v-text="item.name"></option>
            </select>
        </div>
    </aside>
</template>
<script>
    export default { 
        mounted() {
            document.querySelector("#countryCodeSelector").addEventListener("change", (e) => {
                if (!e.target.value) return;
                this.getAppObj().setResourcesByCountry(e.target.value);
            });
        },
        methods: {
            getAppObj() {
                return this.$parent;
            },
        }
    };
</script>

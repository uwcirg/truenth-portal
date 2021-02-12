<template>
    <aside>
        <div id="debugContainer" v-bind:class="{active: getAppObj().isDebugMode()}">
            <div class="close" @click="getAppObj().unsetDebugMode()">X</div>
            <h5>Development Tool</h5>
            <div class="content">
                <div class="item">
                    <label class="title">Change Country Code</label>
                    <select id="countryCodeSelector">
                        <option value="">-- Select --</option>
                        <option v-for="item in getAppObj().getEligibleCountryCodes()" :key="item.code" :value="item.code" v-text="item.name"></option>
                    </select>
                </div>
                <div class="item">
                    <label class="title">Invoke Triggers</label>
                    <div v-for="item in getAppObj().getDefaultDomains()" :key="item + '_checkbox'">
                        <input type="checkbox" name="chkTrigger" class="trigger-checkbox" :value="item"></input>
                        <label v-text="item"></label>
                    </div>
                    <div><button @click="getAppObj().submitTestTriggers()">Submit Test Triggers</button></div>
                </div>
            </div>
        </div>
    </aside>
</template>
<script>
    export default { 
        mounted() {
            let countryCodeSelector =  document.querySelector("#countryCodeSelector");
            if (!countryCodeSelector) return;
            countryCodeSelector.addEventListener("change", (e) => {
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


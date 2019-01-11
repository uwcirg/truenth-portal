import Vue from "vue";
import PsaTracker from "./components/PsaTracker.vue";

new Vue({ /*global Vue*/
    el: "#mainPsaApp",
    render: h => h(PsaTracker)
}).$mount("#mainPsaApp"); 


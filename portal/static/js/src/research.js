import Vue from "vue";
import Research from "./components/Research.vue";
(function() {
    const researchContentElementId = "#researchContentContainer";
    new Vue({ /*global Vue*/
        el: researchContentElementId,
        render: h => h(Research)
    }).$mount(researchContentElementId); 
})();



import Vue from "vue";
import LongitudinalReport from "./components/LongitudinalReport.vue";
window.onload = function () {
    (function() {
        const contentElementId = "#longitudinalReportContainer";
        new Vue({ /*global Vue*/
            el: contentElementId,
            render: h => h(LongitudinalReport)
        }).$mount(contentElementId); 
    })();
};

import Vue from "vue";
import AssessmentReport from "./components/AssessmentReport.vue";
(function() {
    const assessmentContentElementId = "#assessmentReportContentContainer";
    new Vue({ /*global Vue*/
        el: assessmentContentElementId,
        render: h => h(AssessmentReport)
    }).$mount(assessmentContentElementId); 
})();





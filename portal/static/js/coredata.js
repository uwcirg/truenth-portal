var subjectId = $("#coreDataUserId").val(), currentUserId, tnthAjax = window.portalModules.tnthAjax, SYSTEM_IDENTIFIER_ENUM = window.portalModules.SYSTEM_IDENTIFIER_ENUM;
$(document).ready(function(){
    if ($("#userRace").length > 0 || $("#userEthnicity").length > 0) {
        tnthAjax.getDemo(subjectId);
        $("#userEthnicity input, #userRace input").on("click", function() {
            var demoArray = {};
            demoArray.resourceType = "Patient";
            demoArray.extension = [];
            if ($("#userEthnicity").length > 0) {
                var ethnicityFields = $("#userEthnicity input:checked");
                if (ethnicityFields.length > 0) {
                    var ethnicityIDs = ethnicityFields.map(function() {
                        return {
                            code: $(this).val(),
                            system: "http://hl7.org/fhir/v3/Ethnicity"
                        };
                    }).get();
                    demoArray.extension.push({
                        "url": SYSTEM_IDENTIFIER_ENUM.ethnicity,
                        "valueCodeableConcept": {"coding": ethnicityIDs}
                    });
                }
            }
            if ($("#userRace").length > 0) {
                var raceFields = $("#userRace input:checkbox:checked");
                if (raceFields.length > 0) {
                    var raceIDs = raceFields.map(function() {
                        return {
                            code: $(this).val(),
                            system: "http://hl7.org/fhir/v3/Race"
                        };
                    }).get();
                    demoArray.extension.push({
                        "url": SYSTEM_IDENTIFIER_ENUM.race,
                        "valueCodeableConcept": {"coding": raceIDs}
                    });
                }
            }
            if (demoArray.extension.length > 0) {
                tnthAjax.putDemo(subjectId, demoArray);
            }
        });
    }
    // Class for both "done" and "skip" buttons
    $(".continue-btn").on("click", function(event){
        event.preventDefault();
        $(this).attr("disabled", true);
        $(".loading-indicator").show();
        try {
            window.location.replace($("#procReturnAddress").val());
        } catch(e) {
            //report error if invalid return address is used here
            tnthAjax.reportError(subjectId, $("procAPIUrl").val(), e.message, true);
            $(this).attr("disabled", false);
            $(".loading-indicator").hide();
            $(".error-continue").text(e.message);
        };
    });
    tnthAjax.getPortalFooter(subjectId, false, "core_data_footer");
});